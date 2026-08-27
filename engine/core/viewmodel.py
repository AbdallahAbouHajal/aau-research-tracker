"""Turn the real census into the exact shapes the interface already expects.

The Claude Design interface reads three constants -- COLLEGE_DATA, AUTHORS and
PAPERS -- plus a handful of run figures. This module produces those shapes from
real data so the interface never has to change: the design stays byte-for-byte
what was approved, and only what flows into it becomes live.

Everything here is read-only. The affiliation rule lives in the census and is
not re-implemented: a person is AAU on a paper because the census said so.
"""
import collections
import csv
import json
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import census as X                                    # noqa: E402
import runs as RUNS                                   # noqa: E402
import translit as TL                                 # noqa: E402

csv.field_size_limit(10 ** 9)

# The eight real colleges, in the order the roster screen shows them, with the
# series colour each one carries throughout the interface.
# AAU's REAL eight, taken from the roster rather than from the mockup. The
# mockup split Education from Humanities and omitted Dentistry; the university
# runs Education-and-Humanities as ONE college and Dentistry is a real one. The
# census made the same mistake once, which is why the roster is ground truth.
COLLEGE_ORDER = [
    ("College of Education, Humanities and Social Sciences", "#0FA64F"),
    ("College of Engineering", "#0A7A3A"),
    ("College of Pharmacy", "#E0303F"),
    ("College of Business", "#14563A"),
    ("College of Law", "#6B8CAE"),
    ("College of Communication and Media", "#1F8A57"),
    ("College of Dentistry", "#C98B5E"),
    ("College of Nursing", "#8FB89E"),
]
_SHORT = {"College of Education, Humanities and Social Sciences":
          "Education & Humanities",
          "College of Engineering": "Engineering",
          "College of Pharmacy": "Pharmacy",
          "College of Business": "Business",
          "College of Law": "Law",
          "College of Communication and Media": "Communication",
          "College of Dentistry": "Dentistry",
          "College of Nursing": "Nursing"}


def _slug(url, name):
    if url and "/staff/" in url:
        return url.rstrip("/").rsplit("/", 1)[-1]
    return re.sub(r"[^a-z0-9]+", "-", (name or "").lower()).strip("-")


def _key(name, taken):
    """A short stable handle. The interface uses it as the selected-author id."""
    toks = [t for t in re.sub(r"[^A-Za-z ]", " ", name or "").split() if t]
    base = (toks[-1] if toks else "x").lower()
    k, n = base, 2
    while k in taken:
        k, n = "%s%d" % (base, n), n + 1
    taken.add(k)
    return k


# On GitHub Actions there is no local census: the repo ships a slim metrics
# file instead (derived figures only -- no emails, and not a bulk Scopus
# export, which carries licensing terms and has no business in a public repo).
DATA = os.environ.get("AAU_DATA") or os.path.join(
    os.path.dirname(os.path.abspath(__file__)), "..", "data")


def _people():
    slim = os.path.join(DATA, "people_metrics.json")
    if os.path.exists(slim):
        try:
            return json.load(open(slim, encoding="utf-8"))
        except Exception:
            pass
    p = X.census_file("people.json")
    if not os.path.exists(p):
        return []
    try:
        blob = json.load(open(p))
    except Exception:
        return []
    return blob if isinstance(blob, list) else list(blob.values())


def _papers_from_run(run_id):
    """AU-ID -> papers, taken from a run this engine just did.

    This is the path GitHub Actions uses: it has no export CSV, it has the
    papers it fetched from Scopus a minute ago, which are fresher anyway.
    """
    out = collections.defaultdict(list)
    blob = (RUNS.load(run_id) or {}) if run_id else {}
    for s in (blob.get("slots") or []):
        # the field is scopus_auid; reading "auid" silently produced an empty
        # map on CI and every college showed zero papers
        aid = str(s.get("scopus_auid") or s.get("auid") or "")
        if not aid:
            continue
        out[aid].append([(s.get("title") or "").strip(),
                         (s.get("journal") or "").strip(),
                         int(s.get("year") or 0),
                         int(s.get("cited_by") or 0), "Indexed"])
    for aid in out:
        out[aid].sort(key=lambda r: (-r[2], -r[3]))
    return out


def _papers_by_author():
    """AU-ID -> [[title, journal, year, cites, status], ...], newest first."""
    path = X.census_file("scopus_export.csv")
    out = collections.defaultdict(list)
    if not os.path.exists(path):
        return out
    named = re.compile(r"\((\d{6,})\)")
    with open(path, newline="", encoding="utf-8-sig") as fh:
        for row in csv.DictReader(fh):
            try:
                year = int(re.sub(r"\D", "", row.get("Year") or "0") or 0)
            except ValueError:
                year = 0
            rec = [(row.get("Title") or "").strip(),
                   (row.get("Source title") or "").strip(),
                   year,
                   int(re.sub(r"\D", "", row.get("Cited by") or "0") or 0),
                   "Indexed"]
            for aid in named.findall(row.get("Author full names") or ""):
                out[aid].append(rec)
    for aid in out:
        out[aid].sort(key=lambda r: (-r[2], -r[3]))
    return out


def build(roster_people=None, run_id=None):
    """-> the whole view-model the interface consumes."""
    if run_id is None:
        try:
            run_id = RUNS.latest_id()
        except Exception:
            run_id = None
    people = _people()
    by_auid = _papers_by_author() or _papers_from_run(run_id)

    # the roster the tracker resolved (152 of 160 carry an AU-ID)
    # The FULL roster, not only the 160 academics. Ghaleb El Refae is AAU's
    # chancellor with ~50 papers; he is administrative staff, so matching only
    # academics files him as "student or external" -- exactly the inference
    # error the curated roster exists to prevent.
    roster = roster_people
    if roster is None:
        here = os.path.dirname(os.path.abspath(__file__))
        import faculty as FAC
        blob = None
        shipped = os.path.join(DATA, "roster.json")
        if os.path.exists(shipped):
            try:
                blob = json.load(open(shipped, encoding="utf-8"))
            except Exception:
                blob = None
        blob = blob or FAC.load()
        roster = (blob or {}).get("people") or []
        res = os.path.join(here, "..", "data", "_resolved.json")
        if os.path.exists(res):
            done = {X.name_key(r["name"]): r for r in json.load(open(res))}
            for r in roster:                 # carry over resolved AU-IDs
                hit = done.get(X.name_key(r.get("name", "")))
                if hit:
                    r["scopus_auid"] = hit.get("scopus_auid", "")
                    r["auid_tier"] = hit.get("auid_tier", "")
    # Linking a census person to a roster person is the same first-name+last-name
    # problem the AU-ID resolver already solves. Reusing it matters: keyed on the
    # exact name, "Ghaleb A. El Refae" never meets roster "Ghaleb Awad El Refae"
    # and a professor with 50 papers is filed as a student.
    roster_names = {X.name_key(r.get("name", "")): r for r in roster}
    export_names = collections.defaultdict(set)     # AU-ID -> printed names
    _path = X.census_file("scopus_export.csv")
    if os.path.exists(_path):
        with open(_path, newline="", encoding="utf-8-sig") as fh:
            for row in csv.DictReader(fh):
                for chunk in (row.get("Author full names") or "").split(";"):
                    m = re.match(r"^(.*?)\s*\((\d{6,})\)\s*$", chunk.strip())
                    if m:
                        export_names[m.group(2)].add(m.group(1))

    def _roster_hit(nm):
        r = roster_names.get(X.name_key(nm))
        if r:
            return r
        for cand in roster:
            if TL.compatible(nm, cand.get("name", "")) or \
                    TL.compatible(cand.get("name", ""), nm):
                return cand
            aid = cand.get("scopus_auid")
            if aid and any(TL.compatible(nm, e) for e in export_names.get(aid, ())):
                return cand
        return None

    # ---- authors -----------------------------------------------------------
    taken, authors, papers_map = set(), [], {}
    for rec in sorted(people, key=lambda r: -(r.get("aau_papers") or 0)):
        name = rec.get("name") or ""
        if not name:
            continue
        hit = _roster_hit(name)
        auid = (hit or {}).get("scopus_auid", "")
        k = _key(name, taken)
        college = (hit or {}).get("college") or rec.get("college") or ""
        authors.append({
            "key": k,
            "name": name,
            "college": college,
            "title": (hit or {}).get("title") or rec.get("directory_rank") or "",
            "papers": rec.get("aau_papers") or 0,
            "h": rec.get("h_index") or 0,
            "cites": rec.get("career_citations") or 0,
            "corr": rec.get("n_corresponding") or 0,
            "auid": auid,
            "tag": "Faculty" if hit else "Student / external",
            "slug": _slug(rec.get("directory_url"), name),
            # Not on the roster, but publishing like senior staff. The rule
            # says they are "outside faculty" and that stands -- but Ghaleb El
            # Refae (AAU's chancellor, 50 papers) reading as a student is how
            # you learn the roster scrape missed someone. Flagged, not retagged.
            "suggest": bool(not hit and (rec.get("aau_papers") or 0) >= 5
                            and rec.get("ever_corresponding")),
        })
        rows = by_auid.get(auid) or []
        if rows:
            papers_map[k] = rows[:12]

    # ---- colleges ----------------------------------------------------------
    per = collections.Counter()
    pap = collections.Counter()
    rev = collections.Counter()
    for a in authors:
        if a["tag"] == "Faculty" and a["college"]:
            per[a["college"]] += 1
    for r in roster:
        c = r.get("college") or ""
        if c and str(r.get("auid_tier", "")).startswith("review"):
            rev[c] += 1
    # papers are credited to every college represented on them
    # runs.results() returns colleges as a LIST of rollup dicts, not a map.
    # Papers per college, best source first. A paper written across two
    # colleges counts for both (whole counting, as the census does), so these
    # sum to more than the paper count -- the interface says so on the chart.
    #
    #   1. the run's own rollup, when it has real figures
    #   2. the run's author rows, counting distinct EIDs per college
    #   3. the Scopus export, for a build with no run behind it
    res = RUNS.results(run_id) if run_id else None
    cols = (res or {}).get("colleges")
    if isinstance(cols, dict):
        cols = [dict(v, name=k) if isinstance(v, dict) else {"name": k, "papers": v}
                for k, v in cols.items()]
    for row in (cols or []):
        if isinstance(row, dict):
            nm = row.get("name") or row.get("college") or ""
            if nm:
                pap[nm] = row.get("papers") or row.get("n_papers") or 0

    if not sum(pap.values()) and run_id:
        blob = RUNS.load(run_id) or {}
        seen = collections.defaultdict(set)
        for sl in (blob.get("slots") or []):
            if sl.get("is_aau") and sl.get("college") and sl.get("eid"):
                seen[sl["college"]].add(sl["eid"])
        for c, e in seen.items():
            pap[c] = len(e)

    if not sum(pap.values()):
        seen = collections.defaultdict(set)
        for a in authors:
            if not a["college"] or not a["auid"]:
                continue
            for row in (by_auid.get(a["auid"]) or []):
                seen[a["college"]].add(row[0])
        for c, e in seen.items():
            pap[c] = len(e)

    colleges = [{"name": n, "people": per.get(n, 0), "papers": pap.get(n, 0),
                 "review": rev.get(n, 0), "color": col}
                for n, col in COLLEGE_ORDER]

    # ---- headline figures --------------------------------------------------
    total_papers = len({r[0] for rows in by_auid.values() for r in rows})
    resolved = sum(1 for r in roster if r.get("scopus_auid"))
    academics = len(roster)
    review_n = sum(1 for r in roster
                   if str(r.get("auid_tier", "")).startswith("review"))

    return {
        "colleges": colleges,
        "authors": authors,
        "papers": papers_map,
        "stats": {
            "papers": total_papers,
            "authors": len(authors),
            "faculty": sum(1 for a in authors if a["tag"] == "Faculty"),
            "roster_people": len(roster),
            "resolved": resolved,
            "academics": academics,
            "review": review_n,
            "suggested": sum(1 for a in authors if a.get("suggest")),
            # The colleges the ROSTER covers -- eight. Counting colleges that
            # have an author with a Scopus record instead gave seven, because
            # Dentistry's staff have no papers in the window. They are still a
            # college, and the university still has eight of them.
            "colleges": len({r.get("college") for r in roster
                             if r.get("college")}),
        },
        "short": _SHORT,
    }


def summary_line(vm):
    s = vm["stats"]
    return ("%d papers | %d authors, %d on the roster | %d of %d academics "
            "resolved | %d need a decision"
            % (s["papers"], s["authors"], s["faculty"], s["resolved"],
               s["academics"], s["review"]))
