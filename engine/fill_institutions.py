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

    python3 fill_institutions.py --handoff .handoff.json --out ../docs/data
"""
import argparse
import json
import os
import sys
import time

ROOT = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(ROOT, "core"))
sys.path.insert(0, os.path.join(ROOT, "vendor"))

import census as X          # noqa: E402
import network as NET       # noqa: E402


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--handoff", default=os.path.join(ROOT, ".handoff.json"))
    ap.add_argument("--out", default=os.path.join(ROOT, "..", "docs", "data"))
    ap.add_argument("--budget", type=int, default=3000)
    a = ap.parse_args()

    if not os.path.exists(a.handoff):
        print("no hand-off file; nothing to do")
        return
    hand = json.load(open(a.handoff, encoding="utf-8"))
    printed = set(hand.get("printed") or [])
    colleges = hand.get("colleges") or {}
    papers = {e: dict(v) for e, v in (hand.get("papers") or {}).items()}
    print("%d papers, %d already carry printed addresses" % (len(papers), len(printed)))

    # The paper's institution list never changes once published, so the cache
    # makes a repeat of the same window free.
    got = NET.backfill_affiliations(papers, printed, log=print, budget_s=a.budget)

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
    out = os.path.abspath(a.out)
    os.makedirs(out, exist_ok=True)
    path = os.path.join(out, "network.json")
    prev = {}
    if os.path.exists(path):
        try:
            prev = json.load(open(path, encoding="utf-8"))
        except Exception:
            prev = {}
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
