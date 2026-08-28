#!/usr/bin/env python3
"""Read every paper's institutions, after the run has already published.

Doing this inside the run held the dashboard for thirteen minutes for a
window nobody had asked for before. It is its own job now: the census
publishes at once, this fills the collaboration screen in behind it, and the
screen says it is waiting rather than presenting a partial answer as a whole
one.

It needs only what stage 5 wrote out -- which papers already carry their
authors' printed addresses, which AAU colleges are on each paper, and each
paper's Scopus id -- plus the published network.json to rebuild.

    python3 fill_institutions.py --handoff handoff.json --out ../docs/data
"""
import argparse
import json
import os
import subprocess
import sys
import time

ROOT = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(ROOT, "core"))
sys.path.insert(0, os.path.join(ROOT, "vendor"))

import census as X          # noqa: E402
import network as NET       # noqa: E402


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--handoff", default=os.path.join(ROOT, "handoff.json"))
    ap.add_argument("--out", default=os.path.join(ROOT, "..", "docs", "data"))
    ap.add_argument("--budget", type=int, default=3000)
    ap.add_argument("--checkpoints", action="store_true",
                    help="write and publish at each quarter, not only at the end")
    ap.add_argument("--publish", default="",
                    help="shell command run after each checkpoint write")
    a = ap.parse_args()

    if not os.path.exists(a.handoff):
        print("no hand-off file; nothing to do")
        return
    hand = json.load(open(a.handoff, encoding="utf-8"))
    printed = set(hand.get("printed") or [])
    colleges = hand.get("colleges") or {}
    papers = {e: dict(v) for e, v in (hand.get("papers") or {}).items()}
    print("%d papers, %d already carry printed addresses" % (len(papers), len(printed)))
    out = os.path.abspath(a.out)
    os.makedirs(out, exist_ok=True)
    path = os.path.join(out, "network.json")

    def rebuild_and_write(note=""):
        slots_ = []
        for eid_, cols_ in colleges.items():
            for c_ in cols_:
                slots_.append({"eid": eid_, "college": c_, "raw_affiliation": ""})
        net_ = NET.build({"papers": papers, "slots": slots_}, [], log=lambda *_: None)
        prev_ = {}
        if os.path.exists(path):
            try:
                prev_ = json.load(open(path, encoding="utf-8"))
            except Exception:
                prev_ = {}
        if ((prev_.get("coverage") or {}).get("printed") or 0) > net_["coverage"]["printed"]:
            return None                       # never go backwards
        net_["generated"] = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
        net_["run"] = hand.get("run") or prev_.get("run")
        with open(path, "w", encoding="utf-8") as fh:
            json.dump(net_, fh, ensure_ascii=False, separators=(",", ":"))
        return net_

    def checkpoint(i, total):
        net_ = rebuild_and_write()
        if not net_:
            return
        c_ = net_["coverage"]
        print("  checkpoint %d/%d: %d of %d papers carry institutions (%d%%)"
              % (i, total, c_["printed"], c_["papers"],
                 100 * c_["printed"] // max(1, c_["papers"])), flush=True)
        if a.publish:
            subprocess.run(["bash", "-c", a.publish], check=False)

    # Every paper, not only the ones the export does not cover. Asking about
    # all of them from one endpoint is what makes the coverage uniform: the
    # first split run rebuilt without the export's 1,330 and published 68%
    # where it should have said 99%, because this job has the paper list and
    # not the run store those addresses live in.
    every = max(1, len(papers) // 4) if a.checkpoints else 0
    got = NET.backfill_affiliations(papers, set(), log=print, budget_s=a.budget,
                                    on_progress=checkpoint, every=every)

    # Rebuild the collaboration view from both sources and republish it.
    slots = []
    for eid, cols in colleges.items():
        for c in cols:
            slots.append({"eid": eid, "college": c, "raw_affiliation": ""})
    for eid in printed:
        papers.setdefault(eid, {})
    blob = {"papers": papers, "slots": slots}
    # A paper whose addresses were already printed keeps them: re-deriving
    # them here would need the run store, which this job does not have, so
    # those papers are asked for too and answered from the same endpoint.
    net = NET.build(blob, [], log=print)
    prev = {}
    if os.path.exists(path):
        try:
            prev = json.load(open(path, encoding="utf-8"))
        except Exception:
            prev = {}
    # A job that can overwrite a good answer with an empty one is worse than
    # a job that does not run. This one did exactly that: it skipped every
    # paper on a key-name mismatch and published 0 partners over 1,723. It
    # refuses now, and says so loudly enough to fail the step.
    was = ((prev.get("coverage") or {}).get("printed") or 0)
    now = net["coverage"]["printed"]
    if prev and now < was:
        print("REFUSING to publish: coverage would fall from %d papers to %d. "
              "The existing file is better and is left alone." % (was, now),
              file=sys.stderr)
        raise SystemExit(1)
    net["generated"] = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
    net["run"] = hand.get("run") or prev.get("run")
    with open(path, "w", encoding="utf-8") as fh:
        json.dump(net, fh, ensure_ascii=False, separators=(",", ":"))
    c = net["coverage"]
    print("wrote %s: %d of %d papers carry institutions (%d%%), %d partners"
          % (path, c["printed"], c["papers"],
             100 * c["printed"] // max(1, c["papers"]), len(net["top"])))
    print("filled in %d papers this pass" % got)


if __name__ == "__main__":
    main()
