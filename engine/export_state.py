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
import exports as EX          # noqa: E402

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

    # A run recorded its own findings as it went. An older run did not, so
    # they are derived from the same figures the dashboard shows -- never
    # invented, and never the mockup sentences, which contradicted the tiles.
    found = blob.get("findings") or []
    if not found:
        st = vm["stats"]
        # Every college the roster covers, whether or not anyone in it has a
        # paper in this window -- Dentistry has staff and no papers, and is
        # still a college.
        n_col = st.get("colleges") or len(vm["colleges"])
        found = [{"text": "The roster holds %s people across %d colleges."
                          % (f"{st.get('roster_people', 0):,}", n_col),
                  "kind": "ok"},
                 {"text": "%s of them resolved to a Scopus author record."
                          % f"{st.get('resolved', 0):,}", "kind": "ok"}]
        if st.get("review"):
            found.append({"text": "%d names match more than one author record "
                                  "and are waiting on the Roster screen."
                                  % st["review"], "kind": "warn"})
        found.append({"text": "The window holds %s papers across %s people, "
                              "%s of them on the roster."
                              % (f"{st.get('papers', 0):,}",
                                 f"{st.get('authors', 0):,}",
                                 f"{st.get('faculty', 0):,}"), "kind": "ok"})
        if st.get("swept_in"):
            found.append({"text": "%d papers were added that the university "
                                  "tag had missed." % st["swept_in"],
                          "kind": "ok"})
        if st.get("rejected"):
            found.append({"text": "%d were thrown out because no author on "
                                  "them printed an Al Ain University address."
                                  % st["rejected"], "kind": "bad"})
        if sug:
            found.append({"text": "%d people printed an AAU address but are "
                                  "not on the roster." % len(sug),
                          "kind": "warn"})
    return {
        "generated": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "run": rid,
        "colleges": vm["colleges"],
        "programs": vm.get("programs") or [],
        "authors": vm["authors"],
        "papers": vm["papers"],
        "stats": dict(vm["stats"], suggested=len(sug)),
        "suggestions": sug,
        "delta": blob.get("delta") or {},
        "findings": found,
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
    ap.add_argument("--no-files", action="store_true",
                    help="skip the workbook, chart pack and deck")
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
    # The three downloadables, written beside state.json under a stable name
    # so the published page can link straight to them. Regenerated on every
    # run, so a file can never disagree with the dashboard above it.
    if not a.no_files:
        # …/docs/data/state.json -> …/docs/downloads. If --out points somewhere
        # without that shape the files are skipped rather than killing a run
        # that has already done all the work.
        d = os.path.abspath(os.path.join(os.path.dirname(out), "..",
                                         "downloads"))
        try:
            os.makedirs(d, exist_ok=True)
        except OSError as exc:
            print("  skipping the downloadable files: %s" % exc)
            d = None
    if not a.no_files and d:
        vm = VM.build(run_id=blob.get("run"))
        vm["stats"] = blob["stats"]
        # Each generator below is caught so a late failure cannot throw away a
        # run that has already done all the work. That is right, but it was
        # also silent: on CI all three raised ImportError every time, the run
        # reported success, and the previous machine's files stayed published
        # under a dashboard they no longer matched. Record what was actually
        # rebuilt so the page can refuse to present a stale file as current.
        failed = []
        try:
            xp = os.path.join(d, "AAU_Research_Tracker.xlsx")
            r = RUNS.export(blob.get("run") or RUNS.latest_id(), kind="xlsx")
            if isinstance(r, dict) and r.get("path"):
                import shutil
                shutil.copy(r["path"], xp)
                print("  workbook   %s (%.0f KB)" % (os.path.basename(xp),
                                                     os.path.getsize(xp) / 1024))
        except Exception as exc:
            print("  workbook failed: %s" % exc)
            failed.append(("workbook", str(exc)[:120]))
        try:
            zp, made = EX.chart_zip(vm, os.path.join(d, "AAU_Charts.zip"))
            for img in made:                       # also loose, for previewing
                import shutil
                shutil.copy(img, os.path.join(d, os.path.basename(img)))
            print("  chart pack %s (%d charts, %.0f KB)"
                  % (os.path.basename(zp), len(made),
                     os.path.getsize(zp) / 1024))
        except Exception as exc:
            print("  chart pack failed: %s" % exc)
            failed.append(("chart pack", str(exc)[:120]))
        try:
            pp = EX.deck(vm, os.path.join(d, "AAU_Research_Tracker.pptx"),
                         generated=blob["generated"][:10])
            print("  slide deck %s (%.0f KB)" % (os.path.basename(pp),
                                                 os.path.getsize(pp) / 1024))
        except Exception as exc:
            print("  slide deck failed: %s" % exc)
            failed.append(("slide deck", str(exc)[:120]))

        blob["exports"] = {"rebuilt": not failed,
                           "failed": [{"file": f, "why": w} for f, w in failed]}
        if failed:
            print("  WARNING: %d downloadable file(s) were NOT rebuilt and are "
                  "now older than the figures above them: %s"
                  % (len(failed), ", ".join(f for f, _ in failed)))
        with open(out, "w", encoding="utf-8") as fh:
            json.dump(blob, fh, ensure_ascii=False, separators=(",", ":"))

    s = blob["stats"]
    print("wrote %s (%.0f KB)" % (out, os.path.getsize(out) / 1024))
    print("  %s papers | %s authors, %s on the roster | %s suggested additions"
          % (s.get("papers"), s.get("authors"), s.get("faculty"),
             s.get("suggested")))


if __name__ == "__main__":
    main()
