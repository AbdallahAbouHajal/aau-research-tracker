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
import programs as PROG                               # noqa: E402
import classify as CLS                                # noqa: E402

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


def _pk(r):
    """A paper's identity is its EID. The title is not an identity: it
    was empty on every published row, so counting distinct titles gave 1
    for anyone with any paper at all."""
    return (r[5] if len(r) > 5 and r[5] else r[0])


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
        # Element 5 is the EID. The interface reads 0..4 and ignores it; it
        # is here because counting papers deduplicated on the TITLE, and the
        # title was empty on every row -- so every programme in the published
        # data reported exactly 1 paper, and 47 of them said the same thing.
        out[aid].append([(s.get("title") or "").strip(),
                         (s.get("journal") or "").strip(),
                         int(s.get("year") or 0),
                         int(s.get("cited_by") or 0), "Indexed",
                         str(s.get("eid") or "")])
    for aid in out:
        out[aid].sort(key=lambda r: (-r[2], -r[3]))
    return out


def _papers_by_name(run_id):
    """name key -> papers, from the run's own author rows.

    Papers are looked up by Scopus author id, which is right when there is
    one. But someone whose id is still ambiguous -- Mohd Molham Sakkal has ten
    candidates waiting on the review screen -- has no id, so the lookup
    returned nothing while the header above it still claimed ten papers from
    the old census file. The run's rows carry the printed name too, and a name
    is enough to list what a person wrote even when it is not enough to pick
    their Scopus record.
    """
    out = collections.defaultdict(list)
    blob = (RUNS.load(run_id) or {}) if run_id else {}
    for s in (blob.get("slots") or []):
        k = X.name_key(s.get("author_name") or "")
        if not k:
            continue
        out[k].append([(s.get("title") or "").strip(),
                       (s.get("journal") or "").strip(),
                       int(s.get("year") or 0),
                       int(s.get("cited_by") or 0), "Indexed",
                       str(s.get("eid") or "")])
    for k in out:
        seen, rows = set(), []
        for r in sorted(out[k], key=lambda r: (-r[2], -r[3])):
            if r[5] and r[5] in seen:
                continue
            seen.add(r[5])
            rows.append(r)
        out[k] = rows
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
                   "Indexed",
                   (row.get("EID") or "").strip()]
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
    by_name = _papers_by_name(run_id)

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

    # AAU prints a Scopus id on most directory cards and a Google Scholar id
    # beside it. Someone with neither is not a failure of ours to find them --
    # the university lists no record -- and the roster should say which it is
    # rather than leaving a blank the reader has to interpret.
    _dir = {}
    try:
        _dp = os.path.join(DATA, "directory_ids.json")
        if os.path.exists(_dp):
            for _r in (json.load(open(_dp, encoding="utf-8")).get("people") or []):
                if _r.get("slug"):
                    _dir[_r["slug"].lower()] = _r
    except Exception:
        _dir = {}

    # ---- authors -----------------------------------------------------------
    # One row per PERSON, not per spelling. The census carries a record for
    # every way a name was printed, and several of them resolve to the same
    # roster person and the same Scopus AU-ID -- so Muhammad Ilyas shipped as
    # four separate members of Engineering, all four serving a byte-identical
    # publication list, and Engineering counted him four times. A Scopus
    # author id IS the identity; two rows carrying the same one are one person.
    taken, authors, papers_map = set(), [], {}
    seen_auid = {}
    for rec in sorted(people, key=lambda r: -(r.get("aau_papers") or 0)):
        name = rec.get("name") or ""
        if not name:
            continue
        hit = _roster_hit(name)
        auid = (hit or {}).get("scopus_auid", "")
        # Identity is the Scopus author id where there is one, and the name
        # otherwise -- without the second half, two census spellings of a
        # person with no resolved id stayed two people. Mahmoud Abu-Ghoush
        # shipped twice, both rows claiming the same twelve papers.
        ident = auid or ("name:" + X.name_key(name))
        if ident in seen_auid:
            first = seen_auid[ident]
            # Keep the fullest name and the best metrics; the papers come from
            # the run and are the same for both rows by construction.
            if len(name) > len(first["name"] or ""):
                first["name"] = name
            for fld, src in (("h", "h_index"), ("cites", "career_citations"),
                             ("corr", "n_corresponding")):
                first[fld] = max(first[fld] or 0, rec.get(src) or 0)
            if not first["slug"]:
                first["slug"] = _slug(rec.get("directory_url"), name)
            continue
        k = _key(name, taken)
        college = CLS.map_college((hit or {}).get("college")
                                  or rec.get("college") or "")
        authors.append({
            "key": k,
            "name": name,
            "college": college,
            "title": (hit or {}).get("title") or rec.get("directory_rank") or "",
            # From THIS run, deduplicated by EID. Reading the census file's
            # own `aau_papers` is what pinned every author's output to the
            # original census: the 536 rows summed to 2,020 under a headline
            # of 4,245 and no window could ever move them.
            "papers": len({_pk(r) for r in
                           ((by_auid.get(auid) or []) if auid
                            else (by_name.get(X.name_key(name)) or []))}),
            "h": rec.get("h_index") or 0,
            "cites": rec.get("career_citations") or 0,
            "corr": rec.get("n_corresponding") or 0,
            "auid": auid,
            "tag": "Faculty" if hit else "Student / external",
            "slug": _slug(rec.get("directory_url"), name),
            # From the roster record this author already matched, by the same
            # transliteration that got them their college. Keying on the name
            # or the slug instead loses everyone whose census spelling differs
            # -- "Khawlah M. AL-Tkhayneh" never meets "Khawlah Mitib
            # Al-Takhayneh", and she has two programmes.
            "programs": list((hit or {}).get("programs") or []),
            # Not on the roster, but publishing like senior staff. The rule
            # says they are "outside faculty" and that stands -- but Ghaleb El
            # Refae (AAU's chancellor, 50 papers) reading as a student is how
            # you learn the roster scrape missed someone. Flagged, not retagged.
            "suggest": bool(not hit and (rec.get("aau_papers") or 0) >= 5
                            and rec.get("ever_corresponding")),
        })
        seen_auid[ident] = authors[-1]
        rows = (by_auid.get(auid) or []) if auid \
            else (by_name.get(X.name_key(name)) or [])
        if rows:
            papers_map[k] = rows[:50]

    # Anyone on the roster who published in this window but is not in the
    # census file. That file is the ORIGINAL census and nothing rewrites it, so
    # 105 roster people with a Scopus id could never appear on the Authors
    # screen at all -- among them the Dean of Nursing, which is how a college
    # came to show 9 papers and 0 people. The roster is ground truth for who
    # belongs to AAU; a person it names who has papers in this run belongs on
    # the screen whether or not the first census happened to catch them.
    for r in roster:
        auid = r.get("scopus_auid") or ""
        if not auid or auid in seen_auid:
            continue
        if ("name:" + X.name_key(r.get("name") or "")) in seen_auid:
            continue
        rows = by_auid.get(auid) or []
        if not rows:
            continue
        k = _key(r.get("name") or auid, taken)
        authors.append({
            "key": k,
            "name": r.get("name") or "",
            "college": CLS.map_college(r.get("college") or ""),
            "title": r.get("title") or "",
            "papers": len({_pk(x) for x in rows}),
            "h": 0, "cites": 0, "corr": 0,
            "auid": auid,
            "tag": "Faculty",
            "slug": _slug(r.get("profile_url"), r.get("name") or ""),
            "suggest": False,
            "programs": list(r.get("programs") or []),
        })
        seen_auid[auid] = authors[-1]
        papers_map[k] = rows[:50]
    # And the roster's academics who published nothing in this window. They
    # were invisible: the screen is built from people who have papers, so
    # someone with no Scopus record simply was not there, and a reader could
    # not tell "no record" from "we could not find them". They appear with
    # zero papers and a note saying which it is.
    for r in roster:
        if not str(r.get("staff_type") or "").lower().startswith("acad"):
            continue
        u = r.get("profile_url") or ""
        sl = u.rstrip("/").rsplit("/", 1)[-1].lower() if "/staff/" in u else ""
        aid = r.get("scopus_auid") or ""
        if aid and aid in seen_auid:
            continue
        if ("name:" + X.name_key(r.get("name") or "")) in seen_auid:
            continue
        d_ = _dir.get(sl) or {}
        k = _key(r.get("name") or sl or "?", taken)
        authors.append({
            "key": k,
            "name": r.get("name") or "",
            "college": CLS.map_college(r.get("college") or ""),
            "title": r.get("title") or "",
            "papers": 0, "h": 0, "cites": 0, "corr": 0,
            "auid": aid,
            "tag": "Faculty",
            "slug": _slug(r.get("profile_url"), r.get("name") or ""),
            "suggest": False,
            "programs": list(r.get("programs") or []),
            "scholar": d_.get("google_scholar_id") or "",
            "listed_by_aau": bool(d_),
            "no_scopus": not aid,
            "why_no_papers": ("AAU lists no Scopus record for them"
                              if (not aid and d_) else
                              ("no papers in this window" if aid else
                               "not matched to a Scopus author record")),
        })
        seen_auid["name:" + X.name_key(r.get("name") or "")] = authors[-1]
    authors.sort(key=lambda a: -(a.get("papers") or 0))

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
    total_papers = len({_pk(r) for rows in by_auid.values() for r in rows})
    resolved = sum(1 for r in roster if r.get("scopus_auid"))
    academics = len(roster)
    review_n = sum(1 for r in roster
                   if str(r.get("auid_tier", "")).startswith("review"))

    # ---- programmes --------------------------------------------------------
    # AAU publishes these on each college's own subsite, and a person can teach
    # on several, so a paper is credited to every programme represented on it --
    # the same whole counting the colleges use, and the totals sum to more than
    # the paper count for the same reason.
    for a_ in authors:
        d_ = _dir.get((a_.get("slug") or "").lower()) or {}
        a_["scholar"] = d_.get("google_scholar_id") or ""
        a_["listed_by_aau"] = bool(d_)
        # Only meaningful for people the university actually lists.
        a_["no_scopus"] = bool(d_) and not (a_.get("auid") or d_.get("scopus_auid"))

    prog_blob = PROG.load() or {}
    by_slug = {k.lower(): v for k, v in (prog_blob.get("by_slug") or {}).items()}
    campus = {k.lower(): v for k, v in (prog_blob.get("campus") or {}).items()}
    # The roster now carries each person's programmes itself, written from
    # AAU's own directory and verified pair by pair. Read them from there
    # first: joining on the profile slug reached only 119 of 556 authors,
    # because a slug is missing wherever the census knows a person the
    # directory scrape did not.
    ros_progs = {}
    for r in roster:
        if not r.get("programs"):
            continue
        ros_progs[X.name_key(r.get("name") or "")] = r["programs"]
        u = r.get("profile_url") or ""
        if "/staff/" in u:
            ros_progs[u.rstrip("/").rsplit("/", 1)[-1].lower()] = r["programs"]
    for a in authors:
        sl = (a.get("slug") or "").lower()
        a["programs"] = (a.get("programs")
                         or ros_progs.get(sl)
                         or ros_progs.get(X.name_key(a.get("name") or ""))
                         or by_slug.get(sl, []))
        a["campus"] = campus.get(sl, [])

    programs = []
    a_by_slug = {}
    for a in authors:
        if a.get("slug"):
            a_by_slug.setdefault(a["slug"].lower(), a)
    # Citations of the papers themselves, not of the people. Career citations
    # across this roster are 113,467 while the window's own papers carry
    # 43,898 -- a card that mixes the two answers a question nobody asked.
    # Keyed by EID, so a paper shared inside a programme counts once.
    cit_by_eid = {}
    for rows_ in by_auid.values():
        for r_ in rows_:
            if len(r_) > 5 and r_[5]:
                cit_by_eid[r_[5]] = int(r_[3] or 0)

    for rec in (prog_blob.get("programs") or []):
        people_here = [a_by_slug[s.lower()] for s in rec.get("staff", [])
                       if s.lower() in a_by_slug]
        eids = set()
        for a in people_here:
            for row in (by_auid.get(a.get("auid") or "") or []):
                eids.add(_pk(row))
        programs.append({
            "name": rec["name"], "college": rec["college"],
            "people": len(people_here),
            "papers": len(eids),
            "citations": sum(cit_by_eid.get(e, 0) for e in eids),
            # h-index is career-defined and cannot be windowed, so it is the
            # one number on a card that is not this period, and it is labelled
            # as such. Zeros are excluded: those are people the census never
            # held, and averaging them in drags a programme toward nothing.
            "avg_h": (lambda hs: round(sum(hs) / len(hs), 1) if hs else 0)(
                [a.get("h") or 0 for a in people_here if (a.get("h") or 0) > 0]),
            "with_h": sum(1 for a in people_here if (a.get("h") or 0) > 0),
            "tagged": len(rec.get("staff") or []),
            # True when the tagging is MINE, not AAU's -- Dentistry and
            # Nursing run one programme each and tag nobody to it, so their
            # staff are assigned by inference. The card says so, because a
            # number the reader cannot tell apart from published data is
            # worse than no number.
            "assumed": bool(rec.get("assumed")),
        })

    # Which Al Ain people are on each paper, inverted from the SAME map the
    # author pages read -- but from all of it, not the fifty rows each page
    # shows. Inverting the capped list instead named 2,404 papers where the
    # uncapped one names far more: a person with 200 papers was contributing
    # fifty of them.
    paper_authors = {}
    for a_ in authors:
        if a_.get("tag") != "Faculty":
            continue
        nm = (a_.get("name") or "").strip()
        if not nm:
            continue
        col = (a_.get("college") or "").replace("College of ", "").strip()
        rows_ = ((by_auid.get(a_.get("auid") or "") or []) if a_.get("auid")
                 else (by_name.get(X.name_key(nm)) or []))
        for r_ in rows_:
            eid_ = r_[5] if len(r_) > 5 and r_[5] else ""
            if not eid_:
                continue
            lst = paper_authors.setdefault(eid_, [])
            if not any(x[0] == nm for x in lst):
                lst.append([nm, col, "roster"])

    # And anyone whose OWN PRINTED ADDRESS on the paper says Al Ain University,
    # roster or not. The roster decides who belongs to AAU; it does not get to
    # decide whose name appears on a paper they wrote. Measured on the current
    # corpus, this rule alone would name 1,224 papers where the roster rule
    # names 3,242 -- because Scopus serves per-author affiliations for only
    # 1,330 of 4,285 papers and refuses them for the rest (view=FULL, REF,
    # META_ABS, ENTITLED and search view=COMPLETE all 401 on these keys). So
    # the two are UNIONED, not swapped: 3,477 papers, and 188 name spellings
    # the roster misses -- Ghaleb ElRefae under a fresh AU-ID, Firas Ayasrah
    # printed two different ways.
    run_slots = (RUNS.load(run_id) or {}).get("slots") or [] if run_id else []
    for s_ in run_slots:
        if not s_.get("is_aau"):
            continue
        nm = (s_.get("author_name") or "").strip()
        eid_ = s_.get("eid") or ""
        if not nm or not eid_:
            continue
        col = (s_.get("college") or "").replace("College of ", "").strip()
        lst = paper_authors.setdefault(eid_, [])
        if not any(x[0] == nm for x in lst):
            lst.append([nm, col, "printed"])

    # Who works with whom, from the papers this run collected. Two people
    # who appear on the same paper have worked together; the count is how many
    # papers they share. This is AAU-internal by construction -- Scopus will
    # not serve co-author lists to these keys, so the only authors any paper
    # can name are the ones matched to the roster. External collaboration is
    # answered by institution on the Collaboration screen, which is a
    # different question and has its own data.
    pairs = collections.Counter()
    for eid_, lst in paper_authors.items():
        names_ = sorted({x[0] for x in lst})
        for i_ in range(len(names_)):
            for j_ in range(i_ + 1, len(names_)):
                pairs[(names_[i_], names_[j_])] += 1
    coauthors = collections.defaultdict(list)
    for (a1, a2), n_ in pairs.items():
        coauthors[a1].append([a2, n_])
        coauthors[a2].append([a1, n_])
    col_of = {}
    for a_ in authors:
        if a_.get("name"):
            col_of[a_["name"]] = (a_.get("college") or "").replace("College of ", "")
    out_co = {}
    for a_ in authors:
        nm_ = a_.get("name") or ""
        rows_ = sorted(coauthors.get(nm_) or [], key=lambda r: (-r[1], r[0]))
        if rows_:
            out_co[a_["key"]] = [[n_, c_, col_of.get(n_, "")] for n_, c_ in rows_[:14]]

    # Each college's own totals, for the dashboard's first level. Citations are
    # over the college's DISTINCT papers: summing its programmes' citations
    # would count a paper once per programme it touches, and five of
    # Communication's programmes share a single staff list.
    _col_eids = collections.defaultdict(set)
    for a_ in authors:
        c_ = a_.get("college")
        if not c_ or a_.get("tag") != "Faculty":
            continue
        rows_ = ((by_auid.get(a_.get("auid") or "") or []) if a_.get("auid")
                 else (by_name.get(X.name_key(a_.get("name") or "")) or []))
        for r_ in rows_:
            if len(r_) > 5 and r_[5]:
                _col_eids[c_].add(r_[5])
    for c_ in colleges:
        n_ = c_["name"]
        c_["citations"] = sum(cit_by_eid.get(e, 0) for e in _col_eids.get(n_, ()))
        mine_ = [p_ for p_ in programs if p_["college"] == n_]
        c_["programs"] = len(mine_)
        c_["staff"] = sum(p_.get("tagged") or 0 for p_ in mine_)

    return {
        "coauthors": out_co,
        "paper_authors": paper_authors,
        "programs": programs,
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
            # Coverage is against ACADEMIC staff, never the whole roster: the
            # roster carries 48 lab supervisors, secretaries and admin
            # assistants, who have no programme by definition. Measured
            # against everyone it reads 147/208 and looks like a gap in the
            # data; against academics it is 152/160. Dentistry and Nursing
            # tag nobody, so their staff are assigned to the single programme
            # each college runs and the card is marked `assumed`.
            "programs_total": len(prog_blob.get("programs") or []),
            "programs_tagged": sum(
                1 for r in roster
                if str(r.get("staff_type") or "").lower().startswith("acad")
                and _slug(r.get("profile_url"), "").lower() in by_slug),
            "programs_assumed": sum(1 for r in (prog_blob.get("programs") or [])
                                    if r.get("assumed")),
            # People AAU itself files under no programme, confirmed by walking
            # its directory filter rather than inferred from a gap in ours.
            "programs_unplaced_confirmed":
                len(prog_blob.get("unplaced_confirmed") or []),
            "academics_listed": sum(
                1 for r in roster
                if str(r.get("staff_type") or "").lower().startswith("acad")),
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
