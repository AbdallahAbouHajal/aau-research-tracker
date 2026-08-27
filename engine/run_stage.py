#!/usr/bin/env python3
"""Run ONE stage of a census run, then stop.

The six stages the interface draws are six real steps here, so a run on GitHub
Actions is six named workflow steps rather than one long opaque one. That is
what lets the published page show genuine progress: it asks GitHub which step
is running and lights the matching stage. Nothing is simulated.

    python3 run_stage.py 1 --years 2025,2026
    python3 run_stage.py 2
    ...
    python3 run_stage.py 6 --out ../docs/data/state.json

State carries between stages in one JSON file (AAU_STAGE_FILE, or a temp file
beside the engine), because each step is a fresh process on the same machine.
"""
import argparse
import json
import os
import sys
import time

ROOT = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(ROOT, "core"))

import census as X            # noqa: E402
import faculty as FAC         # noqa: E402
import resolve as RES         # noqa: E402
import fetch as FETCH         # noqa: E402
import classify as CLS        # noqa: E402
import runs as RUNS           # noqa: E402

STATE = os.environ.get("AAU_STAGE_FILE") or os.path.join(ROOT, ".stage.json")

STAGES = [
    "Read the faculty roster",
    "Find each person in Scopus",
    "Collect the papers",
    "Check the extra papers found",
    "Sort faculty from students",
    "Build the census and compare",
]


def load():
    if os.path.exists(STATE):
        with open(STATE, encoding="utf-8") as fh:
            return json.load(fh)
    return {}


def save(b):
    with open(STATE, "w", encoding="utf-8") as fh:
        json.dump(b, fh, separators=(",", ":"))


def log(m):
    print("   %s" % m, flush=True)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("stage", type=int, choices=range(1, 7))
    ap.add_argument("--years", default="")
    ap.add_argument("--scope", default="compare")
    ap.add_argument("--out", default="")
    a = ap.parse_args()

    n = a.stage
    b = load()
    t0 = time.time()
    print("== stage %d/6  %s" % (n, STAGES[n - 1]), flush=True)

    if n == 1:
        years = [int(y) for y in a.years.split(",") if y.strip()] \
            or FETCH.window()
        blob = FAC.load() or {}
        people = blob.get("people") or []
        if not people:
            raise SystemExit("no roster: ship engine/data/roster.json")
        b = {"run": RUNS.new_id(), "years": years, "scope": a.scope,
             "version": blob.get("version", ""), "people": people,
             "findings": []}
        b["findings"].append({
            "text": "The roster loaded cleanly: %d people across %d colleges."
                    % (len(people), len({p.get("college") for p in people
                                         if p.get("college")})),
            "kind": "ok"})
        log("%d people, window %s" % (len(people),
                                      ", ".join(map(str, years))))

    elif n == 2:
        people = b["people"]
        RES.resolve_chain(people, log=log)
        acad = [p for p in people
                if str(p.get("staff_type", "")).lower().startswith("acad")]
        got = sum(1 for p in acad if p.get("scopus_auid"))
        b["people"] = people
        b["findings"].append({
            "text": "%d of the %d academics were found in Scopus."
                    % (got, len(acad)), "kind": "ok"})
        log("%d of %d academics resolved" % (got, len(acad)))

    elif n == 3:
        got = FETCH.run(faculty=b["people"], years=b["years"], log=log,
                        routes="a")
        b["papers"] = got["papers"]
        b["stats"] = got["stats"]
        b["findings"].append({
            "text": "The publication window came back with %d papers."
                    % got["stats"].get("af_id_unique", 0), "kind": "ok"})
        log("%d papers under the university tag" % len(got["papers"]))

    elif n == 4:
        got = FETCH.run(faculty=b["people"], years=b["years"], log=log,
                        routes="b", papers=b.get("papers") or {},
                        stats=b.get("stats") or {})
        b["papers"] = got["papers"]
        b["stats"] = got["stats"]
        rej = got["stats"].get("faculty_sweep_rejected") or 0
        add = got["stats"].get("faculty_sweep_added") or 0
        if add:
            b["findings"].append({
                "text": "%d papers were added that the university tag had "
                        "missed." % add, "kind": "ok"})
        if rej:
            b["findings"].append({
                "text": "%d were thrown out because no author on them printed "
                        "an Al Ain University address." % rej, "kind": "bad"})
        log("+%d accepted, %d rejected at the gate" % (add, rej))

    elif n == 5:
        slots = RUNS.build_slots(b["papers"], log=log)
        cl = CLS.classify(slots, b["people"], list_version=b.get("version", ""))
        b["slots"] = slots
        b["cl"] = cl
        b["findings"].append({
            "text": "%d author rows are faculty, %d are students or outside "
                    "faculty." % (cl.get("faculty", 0),
                                  cl.get("student_external", 0)), "kind": "ok"})
        log("faculty %d | student or external %d"
            % (cl.get("faculty", 0), cl.get("student_external", 0)))

    elif n == 6:
        rid = b["run"]
        roster = RUNS.roster(b["slots"])
        dlt = RUNS.delta(rid, b["papers"], roster)
        sug = CLS.suggest_additions(b["slots"], b["people"])
        if sug:
            b["findings"].append({
                "text": "%d people printed an AAU address but are not on the "
                        "roster. They are waiting on the Roster screen."
                        % len(sug), "kind": "warn"})
        RUNS.save(rid, {"stats": {**b.get("stats", {}), **b.get("cl", {})},
                        "faculty_version": b.get("version", ""),
                        "papers": b["papers"], "slots": b["slots"],
                        "roster": roster, "delta": dlt, "suggestions": sug,
                        "findings": b["findings"],
                        "options": {"years": b["years"],
                                    "scope": b.get("scope")}})
        log("saved run %s" % rid)
        import export_state
        out = a.out or export_state.DEFAULT_OUT
        sys.argv = ["export_state.py", "--out", out]
        export_state.main()
        if os.path.exists(STATE):
            os.remove(STATE)
        print("== run %s complete" % rid, flush=True)
        return

    save(b)
    print("== stage %d done in %.0fs" % (n, time.time() - t0), flush=True)


if __name__ == "__main__":
    main()
