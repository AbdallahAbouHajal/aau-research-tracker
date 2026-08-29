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
import faculty as FAC         # noqa: E402

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
    # The review screen shipped with the designer's placeholder people in it --
    # a card for "Muhammad Ilyas" offering three invented Scopus records, and a
    # queue of seven names that do not exist. Nothing real ever reached it,
    # because the run published only a COUNT of how many needed a decision. The
    # queue itself goes out now, so the screen shows the people who are
    # genuinely ambiguous and the buttons act on them.
    review = []
    for r in (FAC.load() or {}).get("people") or []:
        if not str(r.get("auid_tier") or "").startswith("review"):
            continue
        review.append({
            "name": r.get("name") or "",
            "college": r.get("college") or "",
            "title": r.get("title") or "",
            "slug": (r.get("profile_url") or "").rstrip("/")
                    .rsplit("/", 1)[-1],
            "candidates": [{"auid": str(c.get("auid") or ""),
                            "papers": int(c.get("papers") or 0)}
                           for c in (r.get("auid_candidates") or [])
                           if c.get("auid")],
        })
    review.sort(key=lambda x: (-len(x["candidates"]), x["name"]))

    return {
        "generated": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "run": rid,
        "review": review,
        # Consumed by main() when it writes papers.json, then dropped: the
        # page never needs the whole inverted map, only each row's slice.
        "paper_authors": vm.get("paper_authors") or {},
        # Who each person writes with inside AAU, and how often. Small
        # enough to ride in state.json: 124 people, at most 14 each.
        "coauthors": vm.get("coauthors") or {},
        # Every EID in this run. The paper lists on the page are capped per
        # author, so diffing THOSE compares samples and not corpora: raising
        # the cap from 12 to 50 made the first real delta announce 1,117 new
        # papers on a window that had not changed at all. ~90 KB, and it is
        # the only way the comparison can be exact.
        "eids": sorted(_run_eids(rid)),
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


def _run_eids(rid):
    """Every paper EID in a run, for an exact run-to-run comparison."""
    try:
        blob = RUNS.load(rid) or {}
    except Exception:
        return set()
    out = set(blob.get("papers") or {})
    for sl in (blob.get("slots") or []):
        if sl.get("eid"):
            out.add(sl["eid"])
    return out


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
    # Written into papers.json below, never into state.json.
    _paper_authors = blob.pop("paper_authors", {})
    blob["paper_authors"] = _paper_authors
    os.makedirs(os.path.dirname(out), exist_ok=True)

    # The charts need the run's own paper list and the collaboration blob,
    # and both are in scope here -- but `vm` is not built until further
    # down, so they are stashed and attached when it is. Referencing `vm`
    # here cost a run: every chart that depends on either was skipped and
    # the pack shipped seven instead of eleven.
    _chart_extra = {}

    # Who AAU publishes with. Its own file for the same reason as the papers:
    # the Networking screen fetches it when opened and the dashboard needs only
    # the top ten, which ride along in state.json.
    try:
        import network as NET
        _rb = RUNS.load(blob.get("run")) or {}
        net = NET.build(_rb, blob.get("authors") or [])
        # The chart generator reads only colleges, stats and authors today, so
        # it can plot none of what this app has learned. These three are
        # already in scope here; attaching them is cheaper than re-deriving
        # them inside exports.py, and vm["papers"] is capped at fifty rows per
        # author so a per-year total built from it would undercount.
        _chart_extra["network"] = net
        _chart_extra["paper_rows"] = [
            {"eid": e, "year": int(p_.get("year") or 0),
             "cited_by": int(p_.get("cited_by") or 0),
             "college": None}
            for e, p_ in (_rb.get("papers") or {}).items()]
        _col_of = {}
        for sl in (_rb.get("slots") or []):
            if sl.get("eid") and sl.get("college"):
                _col_of.setdefault(sl["eid"], set()).add(sl["college"])
        for r_ in _chart_extra["paper_rows"]:
            r_["college"] = sorted(_col_of.get(r_["eid"], ()))
        np_ = os.path.join(os.path.dirname(out), "network.json")
        with open(np_, "w", encoding="utf-8") as fh:
            json.dump(dict(net, generated=blob["generated"], run=blob.get("run")),
                      fh, ensure_ascii=False, separators=(",", ":"))
        blob["network"] = {"coverage": net["coverage"],
                           "top": net["top"][:10]}
        print("  network   %s (%d partners, %.0f KB)"
              % (os.path.basename(np_), len(net["top"]),
                 os.path.getsize(np_) / 1024))
    except Exception as exc:
        print("  network file failed: %s" % exc)

    # Every paper in the run, as its own file. The dashboard says 4,245 and
    # until now there was nowhere to go and look at them. It is ~500KB, which
    # has no business in state.json -- the Papers screen fetches it the first
    # time it is opened and not before.
    try:
        rb = RUNS.load(blob.get("run")) or {}
        # Which Al Ain people are on each paper. Built by INVERTING the very
        # map the Authors screen uses, not by re-filtering the run's slots --
        # doing the latter made the two screens disagree, and Abdallah caught
        # it: Kareem Abdou's page listed a paper whose own row said it had no
        # Al Ain author, because his slot on it never picked up the Faculty
        # role. Inverted, the two cannot disagree: if a person's page shows a
        # paper, that paper names the person.
        # Computed in the view-model, off the uncapped author-to-papers map.
        # Rebuilding it here from blob["papers"] would read the fifty rows a
        # page displays and quietly name a third fewer papers.
        who = blob.get("paper_authors") or {}
        for v in who.values():
            v.sort(key=lambda x: x[0])
        rows = []
        for eid, p_ in (rb.get("papers") or {}).items():
            rows.append([
                (p_.get("title") or "").strip(),
                (p_.get("journal") or "").strip(),
                int(p_.get("year") or 0),
                int(p_.get("cited_by") or 0),
                (p_.get("doctype") or "").strip(),
                (p_.get("doi") or "").strip(),
                eid,
                1 if p_.get("found_via") == "faculty_sweep" else 0,
                who.get(eid) or [],
            ])
        rows.sort(key=lambda r: (-r[2], -r[3]))
        pp = os.path.join(os.path.dirname(out), "papers.json")
        with open(pp, "w", encoding="utf-8") as fh:
            json.dump({"generated": blob["generated"], "run": blob.get("run"),
                       "columns": ["title", "journal", "year", "cited_by",
                                   "type", "doi", "eid", "found_by_sweep",
                                   "aau_authors"],
                       "papers": rows},
                      fh, ensure_ascii=False, separators=(",", ":"))
        print("  papers    %s (%d papers, %.0f KB)"
              % (os.path.basename(pp), len(rows), os.path.getsize(pp) / 1024))
    except Exception as exc:
        print("  papers file failed: %s" % exc)

    # "Since the last run" was empty on every run ever published, and would
    # have stayed that way forever: RUNS.delta() compares against the run
    # store, engine/data/runs/ is .gitignored, and the workflow commits only
    # docs/. So every CI run began with an empty store, called itself the
    # first run ever, and reported nothing changed -- a week with forty new
    # papers and a week with revoked API keys rendered identically.
    #
    # The previous answer IS in the checkout though: it is the state.json
    # about to be overwritten. Diffing against that is what the screen has
    # always claimed to show.
    if (blob.get("delta") or {}).get("first_run") and os.path.exists(out):
        try:
            with open(out, encoding="utf-8") as fh:
                prev = json.load(fh)
        except Exception:
            prev = None
        if prev and prev.get("run") and prev.get("run") != blob.get("run"):
            def _eids(b):
                if b.get("eids"):
                    return set(b["eids"])
                # A census published before eids existed: fall back to the
                # sampled lists and say so, rather than inventing a diff.
                out_ = set()
                for rows in (b.get("papers") or {}).values():
                    for r in (rows or []):
                        if len(r) > 5 and r[5]:
                            out_.add(r[5])
                return out_

            def _titles(b):
                t = {}
                for rows in (b.get("papers") or {}).values():
                    for r in (rows or []):
                        if len(r) > 5 and r[5]:
                            t[r[5]] = {"title": r[0], "journal": r[1],
                                       "year": r[2]}
                return t

            now_e, was_e = _eids(blob), _eids(prev)
            exact = bool(blob.get("eids") and prev.get("eids"))
            now_t = _titles(blob)
            now_p = {a_["auid"]: a_ for a_ in (blob.get("authors") or [])
                     if a_.get("auid")}
            was_p = {a_["auid"] for a_ in (prev.get("authors") or [])
                     if a_.get("auid")}
            fresh = sorted(now_e - was_e)
            newp = [now_p[x] for x in now_p if x not in was_p]
            blob["delta"] = {
                "first_run": False,
                "since": prev.get("generated"),
                "new_papers": [dict(now_t.get(e, {}), eid=e) for e in fresh[:200]],
                "new_papers_total": len(fresh),
                "new_people": [{"name": p_.get("name"),
                                "college": p_.get("college"),
                                "papers": p_.get("papers")} for p_ in newp[:100]],
                "new_people_total": len(newp),
                "gone_papers": len(was_e - now_e),
                "returning": [], "updated": [],
                "compared_against": "the previously published census",
                # Without both sides carrying a full EID list the numbers are
                # a comparison of samples; the screen must not present that as
                # a count of new work.
                "exact": exact,
            }
            print("  delta against %s: +%d papers, +%d people, %d no longer "
                  "present%s"
                  % (str(prev.get("generated"))[:10], len(fresh), len(newp),
                     len(was_e - now_e),
                     "" if exact else "  (approximate: the previous census "
                                      "did not publish a full paper list)"))

    blob.pop("paper_authors", None)
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
        vm.update(_chart_extra)
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
