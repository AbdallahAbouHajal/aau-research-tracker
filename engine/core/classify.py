"""Decide, for every author on every paper: is this AAU, and are they faculty?

Two independent questions, kept separate on purpose.

1. IS THIS PERSON AAU ON THIS PAPER?  Decided only by the affiliation printed
   on the paper, via the census's badge(). Scopus and the printed text decide;
   OpenAlex is never consulted here. That rule is what caught a 568-paper
   false claim built on OpenAlex's institution index.

2. ARE THEY FACULTY?  Decided only by the curated list. In the list -> Faculty,
   and their college comes from the list. Not in it -> Student / external.
   This replaces the census's low-confidence inference ("<=2 papers, never
   corresponding, absent from a scraped directory") with a fact about a roster.
"""
import collections
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import json

import census as X
import translit as TL

_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
_MAP_PATH = os.path.join(_ROOT, "config", "college_map.json")
_MAP = None
UNMAPPED = set()


def college_map():
    """Snap an inferred college onto one of AAU's real eight.

    college_of() can only return what the affiliation text says, so it emits
    "College of Computer and Information Sciences" (28 people) and splits
    Education from Humanities and Social Sciences -- which AAU runs as one
    college. Unmapped values are collected, not dropped, so the UI can ask.
    """
    global _MAP
    if _MAP is None:
        try:
            with open(_MAP_PATH) as fh:
                _MAP = json.load(fh).get("map", {})
        except Exception:
            _MAP = {}
    return _MAP


def map_college(c):
    if not c:
        return ""
    m = college_map()
    if c in m:
        return m[c]
    UNMAPPED.add(c)
    return c

FACULTY = "Faculty"
STUDENT = "Student / external"


def build_lookup(faculty):
    """name_key and surname+initial -> the faculty record."""
    by_key, by_init, by_auid = {}, {}, {}
    ordered = []
    for p in faculty:
        k = p.get("name_key") or X.name_key(p["name"])
        by_key.setdefault(k, p)
        for ik in (p.get("initial_keys") or X.initial_keys(p["name"])):
            by_init.setdefault(ik, p)
        if p.get("scopus_auid"):
            by_auid.setdefault(p["scopus_auid"], p)
        ordered.append(p)
    return {"key": by_key, "init": by_init, "auid": by_auid, "all": ordered}


def match_faculty(name, auid, lk):
    """-> (record|None, how). AU-ID is stronger than any name match."""
    if auid and auid in lk["auid"]:
        return lk["auid"][auid], "scopus_auid"
    k = X.name_key(name or "")
    if k and k in lk["key"]:
        return lk["key"][k], "name"
    for ik in X.initial_keys(name or ""):
        if ik in lk["init"]:
            return lk["init"][ik], "surname_initial"
    # Last resort: a transliteration variant. The roster says
    # "Khawlah Mitib Al-Takhayneh"; Scopus prints "Al-Tkhayneh, Khawlah M."
    # -- one vowel apart, and every match above fails. She has 41 papers.
    hits = [p for p in lk["all"] if TL.match(name or "", p["name"])]
    if len(hits) == 1:
        return hits[0], "transliteration"
    return None, ""


def classify(slots, faculty, list_version=""):
    """Annotate AAU-badged author rows with role and college.

    `slots` is one row per author per paper, each with author_name,
    raw_affiliation, and optionally scopus_auid.
    """
    lk = build_lookup(faculty)
    stats = collections.Counter()

    for s in slots:
        if not s.get("is_aau"):
            continue
        rec, how = match_faculty(s.get("author_name"), s.get("scopus_auid"), lk)
        if rec:
            s["role"] = FACULTY
            s["role_basis"] = "on the AAU faculty list (matched by %s)" % how
            s["role_confidence"] = "high"
            s["college"] = (rec.get("colleges") or [rec.get("college")])[0] or ""
            s["college_source"] = "faculty list"
            # Rows derived from AU-ID provenance have no printed name -- the
            # export is what carries names, and it does not cover these
            # papers. The roster match supplies it, which is the same source
            # the college comes from.
            if not s.get("author_name") and rec.get("name"):
                s["author_name"] = rec["name"]
            s["faculty_match"] = how
            stats["faculty"] += 1
        else:
            s["role"] = STUDENT
            s["role_basis"] = ("AAU affiliation on the paper, but not on the "
                               "faculty list")
            s["role_confidence"] = "high" if list_version else "low"
            # fall back to the printed affiliation for a college
            s["college"] = map_college(
                s.get("college") or X.college_of([s.get("raw_affiliation") or ""]))
            s["college_source"] = ("printed on the paper" if s["college"]
                                   else "not stated")
            s["faculty_match"] = ""
            stats["student_external"] += 1
        s["list_version"] = list_version
    return dict(stats)


def suggest_additions(slots, faculty, min_papers=3):
    """Unlisted people who look like faculty -- the list's self-repair.

    Someone with several papers, or who corresponded, is behaving like staff
    rather than like a student who appears once on a supervisor's paper.
    """
    lk = build_lookup(faculty)
    agg = collections.defaultdict(
        lambda: {"papers": 0, "corresponding": 0, "first": 0,
                 "name": "", "colleges": collections.Counter(), "auids": set()})
    for s in slots:
        if not s.get("is_aau") or s.get("role") == FACULTY:
            continue
        if match_faculty(s.get("author_name"), s.get("scopus_auid"), lk)[0]:
            continue
        k = X.name_key(s.get("author_name") or "")
        if not k:
            continue
        a = agg[k]
        a["papers"] += 1
        a["name"] = a["name"] or s.get("author_name")
        a["corresponding"] += int(bool(s.get("is_corresponding")))
        a["first"] += int(bool(s.get("is_first")))
        if s.get("college"):
            a["colleges"][s["college"]] += 1
        if s.get("scopus_auid"):
            a["auids"].add(s["scopus_auid"])

    out = []
    for k, a in agg.items():
        if a["papers"] >= min_papers or a["corresponding"] >= 1:
            out.append({
                "name": a["name"], "name_key": k, "papers": a["papers"],
                "corresponding": a["corresponding"], "first_author": a["first"],
                "college": (a["colleges"].most_common(1) or [("", 0)])[0][0],
                "scopus_auid": sorted(a["auids"])[0] if a["auids"] else "",
                "why": ("%d papers" % a["papers"]) +
                       (", corresponding author" if a["corresponding"] else ""),
            })
    out.sort(key=lambda x: (-x["corresponding"], -x["papers"]))
    return out
