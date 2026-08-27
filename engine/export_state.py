#!/usr/bin/env python3
"""Write the whole view-model to a JSON file the published page can read.

GitHub Pages serves files, not processes -- so the engine cannot listen there.
It does not need to: the engine RUNS on GitHub Actions, on GitHub's own
machines, and leaves its answer here as a file. The page fetches that file and
shows real data with no server involved.

    python3 export_state.py                       -> ../AAU_Tracker_Site/docs/data/state.json
    python3 export_state.py --run                 -> do a real Scopus run first
    python3 export_state.py --out path/state.json
"""
import argparse
import json
import os
import sys
import time

ROOT = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(ROOT, "core"))

import viewmodel as VM        # noqa: E402
import runs as RUNS           # noqa: E402
import census as X            # noqa: E402

DEFAULT_OUT = os.path.join(ROOT, "..", "AAU_Tracker_Site", "docs", "data",
                           "state.json")


def build(run_id=None):
    rid = run_id or (RUNS.latest_id() if hasattr(RUNS, "latest_id") else None)
    vm = VM.build(run_id=rid)

    blob = (RUNS.load(rid) or {}) if rid else {}
    rs = blob.get("stats") or {}
    if rs.get("total_papers"):
        vm["stats"]["papers"] = rs["total_papers"]
    vm["stats"]["swept_in"] = rs.get("faculty_sweep_added", 0)
    vm["stats"]["rejected"] = rs.get("faculty_sweep_rejected", 0)
    vm["stats"]["years"] = (blob.get("options") or {}).get("years") or \
        rs.get("years") or []

    sug = [a for a in vm["authors"] if a.get("suggest")]
    return {
        "generated": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "run": rid,
        "colleges": vm["colleges"],
        "authors": vm["authors"],
        "papers": vm["papers"],
        "stats": dict(vm["stats"], suggested=len(sug)),
        "suggestions": sug,
        "delta": blob.get("delta") or {},
        "findings": blob.get("findings") or [],
        "source": "github-actions" if os.environ.get("GITHUB_ACTIONS")
                  else "local",
    }


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default=DEFAULT_OUT)
    ap.add_argument("--run", action="store_true",
                    help="do a real Scopus run before exporting")
    ap.add_argument("--years", default="",
                    help="comma-separated, e.g. 2025,2026")
    a = ap.parse_args()

    if a.run:
        import app as APP
        years = [int(y) for y in a.years.split(",") if y.strip()] or None
        rid = APP.start_run({"mode": "refresh", "scope": "compare",
                             "years": years})
        print("run %s started" % rid, flush=True)
        while True:
            with APP.LOCK:
                job = APP.JOBS[rid]
                done, err = job["done"], job["error"]
                stage, pct = job["stage"], list(job["pct"])
            if done:
                break
            print("  stage %d/6  %s" % (stage + 1,
                                        " ".join("%d%%" % p for p in pct)),
                  flush=True)
            time.sleep(10)
        if err:
            print("run failed: %s" % err, file=sys.stderr)
            sys.exit(1)
        print("run finished", flush=True)

    blob = build()
    out = os.path.abspath(a.out)
    os.makedirs(os.path.dirname(out), exist_ok=True)
    with open(out, "w", encoding="utf-8") as fh:
        json.dump(blob, fh, ensure_ascii=False, separators=(",", ":"))
    s = blob["stats"]
    print("wrote %s (%.0f KB)" % (out, os.path.getsize(out) / 1024))
    print("  %s papers | %s authors, %s on the roster | %s suggested additions"
          % (s.get("papers"), s.get("authors"), s.get("faculty"),
             s.get("suggested")))


if __name__ == "__main__":
    main()
