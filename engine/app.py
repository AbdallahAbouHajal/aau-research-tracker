#!/usr/bin/env python3
"""AAU Research Tracker -- the local app. Standard library only, python 3.9+.

    ./Launch AAU Tracker.command          double-click
    /usr/bin/python3 app.py               127.0.0.1:8770, opens a browser
    /usr/bin/python3 app.py --port 9100
    /usr/bin/python3 app.py --headless-run     one run, no UI (launchd uses this)

It serves the approved interface and drives the real pipeline behind it. The
interface is never edited here: it reads three constants and this fills them.

Endpoints
    GET  /                        the interface
    GET  /api/state               the whole view-model, from real data
    POST /api/run/start           {mode, scope, years} -> {run}
    GET  /api/run/status?run=     six-stage progress, log and findings
    POST /api/run/stop            ask the current run to stop
    POST /api/faculty/add         {url} | {name, auid, college} -> add to roster
    POST /api/faculty/dismiss     {name}  not faculty; stop suggesting them
    POST /api/faculty/resolve     {name, auid}  pin an ambiguous AU-ID
    POST /api/faculty             {csv}  import a roster CSV
    POST /api/export              {kind: xlsx|pptx} -> {path}
    POST /api/schedule            {enabled, weekday, hour}
"""
import argparse
import json
import os
import re
import sys
import threading
import time
import traceback
import urllib.parse
import webbrowser
from http.server import ThreadingHTTPServer, BaseHTTPRequestHandler

ROOT = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(ROOT, "core"))

import census as X            # noqa: E402
import faculty as FAC         # noqa: E402
import resolve as RES         # noqa: E402
import fetch as FETCH         # noqa: E402
import classify as CLS        # noqa: E402
import runs as RUNS           # noqa: E402
import viewmodel as VM        # noqa: E402
import profile_ids as PID     # noqa: E402

# The built interface. AAU_UI lets a container point at its own copy, since
# the design repo is not shipped inside the image.
UI = os.environ.get("AAU_UI") or os.path.join(
    ROOT, "ui", "index.html")
if not os.path.exists(UI):
    UI = os.path.join(ROOT, "..", "AAU_Tracker_Site", "docs", "index.html")
DATA = os.path.join(ROOT, "data")
DISMISSED = os.path.join(DATA, "not_faculty.json")

# The six stages the interface draws, in its own words.
STAGES = ["Read the faculty roster", "Find each person in Scopus",
          "Collect the papers", "Check the extra papers found",
          "Sort faculty from students", "Build the census and compare"]

JOBS, LOCK = {}, threading.Lock()
_CACHE = {"vm": None, "at": 0}


# ------------------------------------------------------------------ helpers
def _json(h, obj, code=200):
    body = json.dumps(obj, default=str).encode()
    h.send_response(code)
    h.send_header("Content-Type", "application/json; charset=utf-8")
    h.send_header("Content-Length", str(len(body)))
    h.send_header("Cache-Control", "no-store")
    h.end_headers()
    h.wfile.write(body)


def _body(h):
    n = int(h.headers.get("Content-Length") or 0)
    if not n:
        return {}
    try:
        return json.loads(h.rfile.read(n).decode("utf-8", "replace"))
    except Exception:
        return {}


def _dismissed():
    if not os.path.exists(DISMISSED):
        return set()
    try:
        return {X.name_key(n) for n in json.load(open(DISMISSED))}
    except Exception:
        return set()


def view(force=False):
    """The view-model, cached briefly -- a run invalidates it."""
    if force or not _CACHE["vm"] or time.time() - _CACHE["at"] > 20:
        # Prefer the newest run: its figures are what the dashboard should
        # show, not the census export the tracker started from.
        rid = None
        try:
            rid = RUNS.latest_id()
        except Exception:
            pass
        vm = VM.build(run_id=rid)
        if rid:
            blob = RUNS.load(rid) or {}
            rs = blob.get("stats") or {}
            if rs.get("total_papers"):
                vm["stats"]["papers"] = rs["total_papers"]
            vm["stats"]["swept_in"] = rs.get("faculty_sweep_added", 0)
            vm["stats"]["rejected"] = rs.get("faculty_sweep_rejected", 0)
            vm["stats"]["years"] = (blob.get("options") or {}).get("years") \
                or rs.get("years") or []
            vm["run"] = rid
            vm["delta"] = blob.get("delta") or {}
        skip = _dismissed()
        for a in vm["authors"]:
            if a.get("suggest") and X.name_key(a["name"]) in skip:
                a["suggest"] = False
        vm["suggestions"] = [a for a in vm["authors"] if a.get("suggest")]
        vm["stats"]["suggested"] = len(vm["suggestions"])
        _CACHE["vm"], _CACHE["at"] = vm, time.time()
    return _CACHE["vm"]


# ---------------------------------------------------------------- the run
def start_run(options):
    run_id = RUNS.new_id()
    job = {"run": run_id, "running": True, "done": False, "error": None,
           "stage": 0, "pct": [0] * 6, "log": [], "findings": [],
           "started": time.time(), "options": options, "stop": False,
           "stats": {}}
    with LOCK:
        JOBS[run_id] = job

    def log(msg):
        with LOCK:
            job["log"].append(str(msg))
        X.log("[%s] %s" % (run_id, msg))

    def stage(n, pct=100):
        with LOCK:
            for i in range(n):
                job["pct"][i] = 100
            job["pct"][n] = max(job["pct"][n], min(100, int(pct)))
            job["stage"] = n

    def find(text, kind="ok"):
        with LOCK:
            job["findings"].append({"text": text, "kind": kind})

    def work():
        try:
            years = options.get("years") or FETCH.window()
            years = [int(y) for y in years]

            # 1 -- the roster
            stage(0, 40)
            blob = FAC.load()
            people = (blob or {}).get("people") or []
            version = (blob or {}).get("version", "")
            stage(0, 100)
            log("roster %s: %d people" % (version or "none", len(people)))
            find("The roster loaded cleanly: %d people across %d colleges."
                 % (len(people), len({p.get("college") for p in people
                                      if p.get("college")})))

            # 2 -- names to Scopus author records
            stage(1, 30)
            tiers = RES.resolve_chain(people, log=log)
            resolved = sum(1 for p in people if p.get("scopus_auid"))
            acad = [p for p in people
                    if str(p.get("staff_type", "")).lower().startswith("acad")]
            n_rev = sum(1 for p in people
                        if str(p.get("auid_tier", "")).startswith("review"))
            stage(1, 100)
            find("%d of the %d academics were found in Scopus."
                 % (sum(1 for p in acad if p.get("scopus_auid")), len(acad))
                 + (" %d need a decision on the Roster screen." % n_rev
                    if n_rev else ""),
                 "warn" if n_rev else "ok")

            # 3 + 4 -- collect, then gate the extras
            got = FETCH.run(faculty=people, years=years, log=log, stage=stage)
            st = got["stats"]
            find("The publication window came back with %d papers."
                 % st.get("af_id_unique", 0))
            if st.get("faculty_sweep_rejected"):
                find("%d extra papers were thrown out because no author on "
                     "them printed an Al Ain University address."
                     % st["faculty_sweep_rejected"], "bad")

            # 5 -- faculty or student, and which college
            stage(4, 20)
            slots = RUNS.build_slots(got["papers"], log=log)
            cl = CLS.classify(slots, people, list_version=version)
            stage(4, 100)
            find("%d author rows are faculty, %d are students or outside "
                 "faculty." % (cl.get("faculty", 0),
                               cl.get("student_external", 0)))

            # 6 -- write it, compare it, and look for people we are missing
            stage(5, 25)
            roster = RUNS.roster(slots)
            dlt = RUNS.delta(run_id, got["papers"], roster)
            stage(5, 60)
            sug = CLS.suggest_additions(slots, people)
            skip = _dismissed()
            sug = [s for s in sug if X.name_key(s.get("name", "")) not in skip]
            RUNS.save(run_id, {"stats": {**st, **cl}, "faculty_version": version,
                               "papers": got["papers"], "slots": slots,
                               "roster": roster, "delta": dlt,
                               "suggestions": sug, "options": options})
            stage(5, 100)
            if sug:
                find("%d people printed an AAU address but are not on the "
                     "roster. They are waiting on the Roster screen."
                     % len(sug), "warn")
            if options.get("scope") == "compare":
                n = len(dlt.get("new_papers") or [])
                find("Since the last run: %s."
                     % ("%d new papers" % n if n else "nothing changed"))
            with LOCK:
                job["stats"] = {**st, **cl, "people": len(roster),
                                "suggestions": len(sug), "tiers": tiers}
            log("saved run %s" % run_id)
            view(force=True)
        except Exception as exc:
            with LOCK:
                job["error"] = "%s: %s" % (type(exc).__name__, exc)
            log("ERROR " + traceback.format_exc()[-900:])
        finally:
            with LOCK:
                job["running"] = False
                job["done"] = True
                job["ended"] = time.time()

    threading.Thread(target=work, daemon=True).start()
    return run_id


# -------------------------------------------------------- add a researcher
def add_researcher(payload):
    """From an aau.ac.ae page, or directly from a name the run suggested."""
    url = (payload.get("url") or "").strip()
    name = (payload.get("name") or "").strip()
    auid = re.sub(r"\D", "", str(payload.get("auid") or ""))

    if url and not payload.get("confirm") and not payload.get("force"):
        # The slug is the only name we have before the page is read, and
        # verify() needs one to check the AU-ID is filed under this person.
        if not name:
            m = re.search(r"/staff/([^/?#]+)", url)
            name = (m.group(1).replace("-", " ").replace(".", " ").title()
                    if m else "")
        got = PID.resolve({"name": name, "profile_url": url})
        if not got.get("auid"):
            page = PID.scrape(url)
            nm = name
            if not nm:
                m = re.search(r"/staff/([^/?#]+)", url)
                nm = (m.group(1).replace("-", " ").title() if m else "")
            return {"found": False, "url": url, "name": nm,
                    "why": got.get("tier"), "page": {
                        "declared": page.get("declared"),
                        "publications": len(page.get("eids") or [])
                                        + len(page.get("titles") or [])}}
        nm = name
        if not nm:
            m = re.search(r"/staff/([^/?#]+)", url)
            nm = (m.group(1).replace("-", " ").title() if m else "")
        return {"found": True, "url": url, "name": nm, "auid": got["auid"],
                "tier": got.get("tier"), "verify": (got.get("ev") or {}).get("verify")}

    # confirmed -- write them into the roster
    blob = FAC.load() or {"people": [], "version": ""}
    people = blob.get("people") or []
    if not name and url:
        m = re.search(r"/staff/([^/?#]+)", url)
        name = (m.group(1).replace("-", " ").title() if m else "")
    if not name:
        raise ValueError("no name")
    key = X.name_key(name)
    for p in people:
        if X.name_key(p.get("name", "")) == key:
            if auid:
                p["scopus_auid"] = auid
                p["auid_tier"] = "manual"
            p["profile_url"] = p.get("profile_url") or url
            FAC.save(people, source="app", note="updated " + name)
            view(force=True)
            return {"added": False, "updated": True, "name": name}
    people.append({
        "name": name, "raw_name": name, "name_key": key,
        "college": payload.get("college") or "", "title": payload.get("title") or "",
        "email": "", "profile_url": url, "staff_type": "academic",
        "is_academic": True, "scopus_auid": auid,
        "auid_tier": "manual" if auid else "none:no-scopus-record",
        "auid_candidates": [], "added_in_app": True,
    })
    FAC.save(people, source="app", note="added " + name)
    view(force=True)
    return {"added": True, "name": name, "auid": auid, "roster": len(people)}


def dismiss(name):
    cur = []
    if os.path.exists(DISMISSED):
        try:
            cur = json.load(open(DISMISSED))
        except Exception:
            cur = []
    if name not in cur:
        cur.append(name)
    os.makedirs(DATA, exist_ok=True)
    json.dump(cur, open(DISMISSED, "w"), indent=1)
    view(force=True)
    return {"dismissed": name, "total": len(cur)}


# ------------------------------------------------------------------ handler
class Handler(BaseHTTPRequestHandler):
    server_version = "AAUTracker/2.0"

    def log_message(self, fmt, *args):
        pass

    def _ui(self):
        path = os.path.abspath(UI)
        if not os.path.exists(path):
            return self.send_error(500, "interface not built: run build.py")
        body = open(path, "rb").read()
        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        parts = urllib.parse.urlparse(self.path)
        path = parts.path
        q = {k: v[0] for k, v in urllib.parse.parse_qs(parts.query).items()}
        try:
            if path in ("/", "/index.html"):
                return self._ui()
            if path == "/api/state":
                vm = view()
                return _json(self, {
                    "colleges": vm["colleges"], "authors": vm["authors"],
                    "papers": vm["papers"], "stats": vm["stats"],
                    "suggestions": vm["suggestions"],
                    "run": vm.get("run"),
                    "delta": vm.get("delta") or {},
                    "schedule": RUNS.schedule_state(),
                    "runs": RUNS.recent(5),
                })
            if path == "/api/run/status":
                with LOCK:
                    job = dict(JOBS.get(q.get("run") or "", {}))
                if not job:
                    return _json(self, {"running": False, "unknown": True})
                job["stages"] = [{"label": STAGES[i], "pct": job["pct"][i]}
                                 for i in range(6)]
                job["log"] = job["log"][-40:]
                return _json(self, job)
            if path == "/api/results":
                return _json(self, RUNS.results(q.get("run")) or {})
            if path == "/api/delta":
                b = RUNS.load(q.get("run")) or {}
                return _json(self, b.get("delta") or {})
            return self.send_error(404)
        except Exception:
            return _json(self, {"error": traceback.format_exc()[-500:]}, 500)

    def do_POST(self):
        path = urllib.parse.urlparse(self.path).path
        b = _body(self)
        try:
            if path == "/api/run/start":
                return _json(self, {"run": start_run(b)})
            if path == "/api/run/stop":
                with LOCK:
                    j = JOBS.get(b.get("run") or "")
                    if j:
                        j["stop"] = True
                return _json(self, {"stopping": True})
            if path == "/api/faculty/add":
                return _json(self, add_researcher(b))
            if path == "/api/faculty/dismiss":
                return _json(self, dismiss(b.get("name") or ""))
            if path == "/api/faculty/resolve":
                blob = FAC.load() or {"people": []}
                people = blob.get("people") or []
                key = X.name_key(b.get("name") or "")
                aid = re.sub(r"\D", "", str(b.get("auid") or ""))
                for p in people:
                    if X.name_key(p.get("name", "")) == key:
                        p["scopus_auid"] = aid
                        p["auid_tier"] = "manual"
                        p["auid_candidates"] = []
                FAC.save(people, source="app", note="resolved " + (b.get("name") or ""))
                view(force=True)
                return _json(self, {"ok": True})
            if path == "/api/faculty":
                rows = FAC.parse_csv(b.get("csv") or "")
                FAC.save(rows["people"], source="csv", note="imported")
                view(force=True)
                return _json(self, {"count": len(rows["people"]),
                                    "problems": rows.get("problems", [])})
            if path == "/api/export":
                p = RUNS.export(b.get("run") or RUNS.latest_id(),
                                kind=(b.get("kind") or "xlsx"))
                return _json(self, {"path": p})
            if path == "/api/schedule":
                RUNS.set_schedule(bool(b.get("enabled")),
                                  int(b.get("weekday", 1)),
                                  int(b.get("hour", 7)))
                return _json(self, RUNS.schedule_state())
            return self.send_error(404)
        except Exception as exc:
            return _json(self, {"error": "%s: %s" % (type(exc).__name__, exc),
                                "trace": traceback.format_exc()[-500:]}, 500)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--port", type=int, default=8770)
    ap.add_argument("--host", default="127.0.0.1",
                    help="0.0.0.0 in a container; localhost otherwise")
    ap.add_argument("--no-open", action="store_true")
    ap.add_argument("--headless-run", action="store_true")
    a = ap.parse_args()

    if a.headless_run:
        rid = start_run({"mode": "refresh", "scope": "compare"})
        while True:
            with LOCK:
                j = JOBS[rid]
                if j["done"]:
                    print("\n".join(j["log"][-20:]))
                    sys.exit(1 if j["error"] else 0)
            time.sleep(1)

    srv = ThreadingHTTPServer((a.host, a.port), Handler)
    url = "http://%s:%d/" % ("127.0.0.1" if a.host == "0.0.0.0"
                             else a.host, a.port)
    print("AAU Research Tracker  ->  %s     (ctrl-c to stop)" % url)
    if not a.no_open and a.host == "127.0.0.1":
        threading.Timer(0.7, lambda: webbrowser.open(url)).start()
    try:
        srv.serve_forever()
    except KeyboardInterrupt:
        print("\nstopped")


if __name__ == "__main__":
    main()
