#!/usr/bin/env python3
"""Write what AAU's directory says into the roster itself.

The programme a person teaches on lived only in data/programs.json and was
joined to people at view time, so the roster -- the file that IS the ground
truth for who belongs to Al Ain University -- carried none of it. Anyone
reading the roster read a person with no programme, and only 119 of 556
authors ever picked one up through the join.

Sources, all four of them, in order of authority:

  data/directory_people.csv      one row per person: college, programmes,
                                 Scopus id, Google Scholar id  (the browser
                                 pass over aau.ac.ae/en/directory)
  data/programme_membership.csv  one row per person per programme, the same
                                 pass, used to cross-check the joined field
  data/programs.json             the college subsites' own filter, unioned in
  data/directory_ids.json        the ids, already verified against Scopus

Then it VERIFIES: every (person, programme) pair in the CSVs must be readable
back off the roster afterwards, and the script fails if any is not.

    python3 sync_roster.py            # write and verify
    python3 sync_roster.py --check    # verify only, change nothing
"""
import csv
import json
import os
import re
import sys
import time

ROOT = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(ROOT, "core"))
sys.path.insert(0, os.path.join(ROOT, "vendor"))

import census as X          # noqa: E402
import translit as TL       # noqa: E402

DATA = os.path.join(ROOT, "data")
ROSTER = os.path.join(DATA, "roster.json")
PEOPLE_CSV = os.path.join(DATA, "directory_people.csv")
PROG_CSV = os.path.join(DATA, "programme_membership.csv")
PROGRAMS = os.path.join(DATA, "programs.json")

_DEGREE = re.compile(r"\s*,?\s*\b(Ph\.?\s?D|M\.?\s?Sc|MBA|MD|DDS|MA|M\.A)\.?\s*$", re.I)

COLLEGE = {
    "Business": "College of Business",
    "Engineering": "College of Engineering",
    "Law": "College of Law",
    "Pharmacy": "College of Pharmacy",
    "Education/Humanities": "College of Education, Humanities and Social Sciences",
    "Communication": "College of Communication and Media",
    "Dentistry": "College of Dentistry",
    "Nursing": "College of Nursing",
}


def clean(n):
    return _DEGREE.sub("", (n or "").strip()).strip()


def prog_key(name):
    """"…Administration" and "…Administration (MBA)" are one programme."""
    n = re.sub(r"\([^)]*\)", " ", (name or "").lower())
    n = re.sub(r"[^a-z0-9 ]", " ", n)
    return re.sub(r"\s+", " ", n).strip()


def finder(people):
    by_key = {X.name_key(p.get("name", "")): p for p in people}

    def find(n):
        p = by_key.get(X.name_key(n))
        if p:
            return p
        for q in people:
            if TL.compatible(q.get("name", ""), n) or TL.compatible(n, q.get("name", "")):
                return q
        return None
    return find


def read_csv_programmes():
    """-> {cleaned name: [programme, ...]} from BOTH csv files, unioned."""
    want = {}
    if os.path.exists(PEOPLE_CSV):
        with open(PEOPLE_CSV, newline="", encoding="utf-8-sig") as fh:
            for r in csv.DictReader(fh):
                nm = clean(r.get("name"))
                for pr in (r.get("programmes") or "").split(";"):
                    pr = pr.strip()
                    if pr and pr.lower() != "none":
                        want.setdefault(nm, []).append(pr)
    if os.path.exists(PROG_CSV):
        with open(PROG_CSV, newline="", encoding="utf-8-sig") as fh:
            for r in csv.DictReader(fh):
                nm, pr = clean(r.get("name")), (r.get("programme") or "").strip()
                if pr and pr.lower() != "none":
                    want.setdefault(nm, []).append(pr)
    for nm in want:
        seen, out = set(), []
        for pr in want[nm]:
            k = prog_key(pr)
            if k not in seen:
                seen.add(k)
                out.append(pr)
        want[nm] = sorted(out)
    return want


def main():
    check_only = "--check" in sys.argv
    blob = json.load(open(ROSTER, encoding="utf-8"))
    people = blob["people"]
    find = finder(people)

    want = read_csv_programmes()
    print("%d people carry a programme in the CSV files" % len(want))

    # the college subsites, unioned in
    subs = {}
    if os.path.exists(PROGRAMS):
        pj = json.load(open(PROGRAMS, encoding="utf-8"))
        subs = {k.lower(): list(v) for k, v in (pj.get("by_slug") or {}).items()}
        print("%d people carry one on the college subsites" % len(subs))

    slug = lambda u: (u or "").rstrip("/").rsplit("/", 1)[-1].lower() \
        if "/staff/" in (u or "") else ""

    wrote = unmatched = 0
    added_people = []
    if not check_only:
        for p in people:
            got, seen = [], set()
            for src in (want.get(clean(p.get("name"))) or [],
                        subs.get(slug(p.get("profile_url"))) or []):
                for pr in src:
                    k = prog_key(pr)
                    if k not in seen:
                        seen.add(k)
                        got.append(pr)
            p["programs"] = sorted(got)
            p["n_programs"] = len(got)
            if got:
                wrote += 1
        # A person AAU's directory lists who is not on the roster is a person
        # the roster is missing -- the directory is the university's own
        # statement of who works there. The verify loop below is what found
        # these: Abdullah Abdullatif of Law and Ala'aldin Zahra of
        # Communication, both with programmes, one with a Scopus id.
        rows = {}
        if os.path.exists(PEOPLE_CSV):
            with open(PEOPLE_CSV, newline="", encoding="utf-8-sig") as fh:
                for r in csv.DictReader(fh):
                    rows[clean(r.get("name"))] = r
        for nm in sorted(want):
            if find(nm):
                continue
            r = rows.get(nm) or {}
            college = COLLEGE.get((r.get("college") or "").strip(), "")
            if not college:
                unmatched += 1
                continue
            people.append({
                "name": nm,
                "raw_name": r.get("name") or nm,
                "college": college,
                "colleges": [college],
                "title": "",
                "department": "",
                "email": "",
                "email_kind": "",
                "profile_url": "",
                "staff_type": "academic",
                "is_academic": True,
                "scopus_auid": (r.get("scopus_id") or "").strip(),
                "google_scholar_id": (r.get("google_scholar_id") or "").strip(),
                "auid_tier": ("high:aau-directory"
                              if (r.get("scopus_id") or "").strip()
                              else "none:no-scopus-record"),
                "auid_candidates": [],
                "name_key": X.name_key(nm),
                "initial_keys": sorted(X.initial_keys(nm)),
                "added_from": "aau directory",
                "programs": want[nm],
                "n_programs": len(want[nm]),
            })
            added_people.append(nm)
            find = finder(people)
        blob["version"] = time.strftime("%Y-%m-%d") + "-programmes"
        blob["programme_source"] = (
            "Programmes as AAU lists them: its directory read with a browser "
            "(the filter does not work over HTTP) unioned with each college "
            "subsite's own filter. Verified pair by pair against the CSVs.")
        json.dump(blob, open(ROSTER, "w", encoding="utf-8"),
                  ensure_ascii=False, indent=1)
        for nm in added_people:
            print("  added %s -- AAU lists them and the roster did not" % nm)
        print("wrote programmes onto %d of %d roster people "
              "(%d added from the directory, %d matched nobody)"
              % (wrote, len(people), len(added_people), unmatched))

    # ---- verify: every CSV pair must be readable back off the roster -------
    blob = json.load(open(ROSTER, encoding="utf-8"))
    people = blob["people"]
    find = finder(people)
    missing, checked = [], 0
    for nm, progs in want.items():
        p = find(nm)
        if not p:
            missing.append((nm, "not on the roster", ""))
            continue
        have = {prog_key(x) for x in (p.get("programs") or [])}
        for pr in progs:
            checked += 1
            if prog_key(pr) not in have:
                missing.append((nm, p.get("name"), pr))
    print("verified %d (person, programme) pairs from the CSVs" % checked)
    if missing:
        print("FAILED: %d pairs are not on the roster" % len(missing))
        for a, b, c in missing[:15]:
            print("   %-32s %-30s %s" % (a[:32], (b or "")[:30], c[:44]))
        raise SystemExit(1)
    print("every pair in the CSVs is on the roster")
    n = sum(1 for p in people if p.get("programs"))
    print("roster: %d of %d people carry at least one programme" % (n, len(people)))


if __name__ == "__main__":
    main()
