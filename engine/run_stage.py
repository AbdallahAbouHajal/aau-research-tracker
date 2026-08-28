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
    ap.add_argument("--from", dest="date_from", default="",
                    help="YYYY-MM-DD; a day-level window")
    ap.add_argument("--to", dest="date_to", default="",
                    help="YYYY-MM-DD")
    ap.add_argument("--scope", default="compare")
    ap.add_argument("--out", default="")
    a = ap.parse_args()

    n = a.stage
    b = load()
    t0 = time.time()
    print("== stage %d/6  %s" % (n, STAGES[n - 1]), flush=True)

    if n == 1:
        df, dt = (a.date_from or "").strip(), (a.date_to or "").strip()
        if df or dt:
            lo = int((df or "1900")[:4]); hi = int((dt or "2100")[:4])
            years = list(range(lo, hi + 1))
        else:
            years = [int(y) for y in a.years.split(",") if y.strip()] \
                or FETCH.window()
        blob = FAC.load() or {}
        people = blob.get("people") or []
        if not people:
            raise SystemExit("no roster: ship engine/data/roster.json")
        b = {"run": RUNS.new_id(), "years": years, "scope": a.scope,
             "date_from": df, "date_to": dt,
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
                        routes="a", date_from=b.get("date_from") or None,
                        date_to=b.get("date_to") or None)
        b["papers"] = got["papers"]
        b["stats"] = got["stats"]
        b["findings"].append({
            "text": "The publication window came back with %d papers."
                    % got["stats"].get("af_id_unique", 0), "kind": "ok"})
        log("%d papers under the university tag" % len(got["papers"]))

    elif n == 4:
        got = FETCH.run(faculty=b["people"], years=b["years"], log=log,
                        routes="b", papers=b.get("papers") or {},
                        stats=b.get("stats") or {},
                        date_from=b.get("date_from") or None,
                        date_to=b.get("date_to") or None)
        b["papers"] = got["papers"]
        b["stats"] = got["stats"]
        rej = got["stats"].get("faculty_sweep_rejected") or 0
        add = got["stats"].get("faculty_sweep_added") or 0
        if add:
            b["findings"].append({
                "text": "%d papers were added that the university tag had "
                        "missed." % add, "kind": "ok"})
        if rej:
            # This line read like a weakness in the census. It is the opposite,
            # and the wording was the problem: these papers were never in the
            # count. Asking Scopus for everything a faculty member wrote returns
            # their work at every institution they have ever been at -- Anan
            # Jarab has 53 in the window and 30 print Al Ain University. The
            # gate is what stops the other 23 being imported, which is exactly
            # the mistake that produced a retracted 568-paper claim once. So
            # say what was checked, what was kept, and that the total above is
            # unaffected.
            b["findings"].append({
                "text": "%d more papers were checked and NOT counted: they came "
                        "up under a faculty member's Scopus record but no author "
                        "on them printed an Al Ain University address. The "
                        "%d above does not include them."
                        % (rej, len(b.get("papers") or {})),
                "kind": "info",
                "why": "A search by author returns everything that person has "
                       "published anywhere, including work from a previous "
                       "university. Only papers that actually print an AAU "
                       "address are admitted, so these were examined and left "
                       "out. Nothing here was ever added to the census and "
                       "then removed."})
        log("+%d accepted, %d rejected at the gate" % (add, rej))

    elif n == 5:
        slots = RUNS.build_slots(b["papers"], log=log)
        # Reading every paper's institutions takes about a second per paper,
        # and doing it here held the whole run -- and therefore the whole
        # dashboard -- for thirteen minutes. It is a separate job now, so the
        # figures publish at once and the collaboration screen fills in behind
        # them. What that job needs is written out here: which papers still
        # want institutions, and which AAU colleges are on each.
        try:
            import network as NET
            have = sorted({s_["eid"] for s_ in slots
                           if (s_.get("raw_affiliation") or "").strip()})
            cols = {}
            for s_ in slots:
                if s_.get("eid") and s_.get("college"):
                    cols.setdefault(s_["eid"], [])
                    if s_["college"] not in cols[s_["eid"]]:
                        cols[s_["eid"]].append(s_["college"])
            hand = {"run": b["run"], "printed": have, "colleges": cols,
                    "papers": {e: {"sid": str(p_.get("scopus_id") or "")}
                               for e, p_ in b["papers"].items()}}
            # NOT a dotfile: actions/upload-artifact excludes hidden files
            # by default, so ".handoff.json" was written, reported, and
            # then silently not uploaded -- the institutions job found
            # nothing and "succeeded" in nine seconds.
            hp = os.environ.get("AAU_HANDOFF") or os.path.join(ROOT, "handoff.json")
            with open(hp, "w", encoding="utf-8") as fh:
                json.dump(hand, fh, separators=(",", ":"))
            log("%d papers already carry their authors' addresses; %d wait on "
                "the institutions job"
                % (len(have), len(b["papers"]) - len(have)))
        except Exception as exc:
            log("could not write the hand-off: %s" % str(exc)[:70])
        cl = CLS.classify(slots, b["people"], list_version=b.get("version", ""))
        b["slots"] = slots
        b["cl"] = cl
        b["findings"].append({
            "text": "%d author rows are faculty, %d are students or outside "
                    "faculty." % (cl.get("faculty", 0),
                                  cl.get("student_external", 0)), "kind": "ok"})
        # Say it when the picture is partial. Full co-author lists exist only
        # for the papers in the census export; beyond it the roster's own
        # people are still counted, from Scopus author IDs, but students and
        # outside co-authors on those papers are simply not knowable with
        # these API keys. A total that looks complete over a breakdown that
        # is not is the failure mode worth naming out loud.
        full = len({s["eid"] for s in slots if not s.get("from_sweep")})
        allp = len(b["papers"])
        if full < allp:
            b["findings"].append({
                "text": "Full co-author lists cover %d of the %d papers. On "
                        "the other %d, faculty are counted from their Scopus "
                        "author IDs, but students and outside co-authors are "
                        "not known \u2014 Elsevier does not serve co-author "
                        "lists to these keys."
                        % (full, allp, allp - full), "kind": "warn"})
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
                                    "scope": b.get("scope"),
                                    "date_from": b.get("date_from"),
                                    "date_to": b.get("date_to")}})
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
