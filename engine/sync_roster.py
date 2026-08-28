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
    adopted = {"college": 0, "scopus": 0, "scholar": 0, "name": 0}
    names = []
    conflicts = []
    if not check_only:
        # AAU's directory outranks the roster on everything it actually
        # states: which college someone is in, which programmes they teach,
        # their Scopus author id and their Google Scholar id. It says nothing
        # about titles, emails, profile links or whether a person is academic
        # or administrative, so those are kept -- 209 people have a title and
        # 208 an email that exist nowhere else. Replacing the file wholesale
        # would throw those away to gain nothing.
        rows_by_name = {}
        if os.path.exists(PEOPLE_CSV):
            with open(PEOPLE_CSV, newline="", encoding="utf-8-sig") as fh:
                for r in csv.DictReader(fh):
                    rows_by_name[clean(r.get("name"))] = r
        for nm, r in rows_by_name.items():
            p = find(nm)
            if not p:
                continue
            col = COLLEGE.get((r.get("college") or "").strip())
            if col and p.get("college") != col:
                # Azza Galal Ramadan is on the Pharmacy roster and the
                # Nursing subsite lists her too. The directory names one
                # college; it does not deny the other. So the directory's
                # becomes the primary and both are kept, because she really
                # does teach on programmes in each.
                was = p.get("college") or ""
                conflicts.append((p.get("name"), was, col))
                both = [c for c in ([col] + list(p.get("colleges") or [was]))
                        if c]
                seen, keep = set(), []
                for c in both:
                    if c not in seen:
                        seen.add(c)
                        keep.append(c)
                p["college"] = col
                p["colleges"] = keep
                adopted["college"] += 1
            # The directory's spelling of a name is the university's own,
            # so it wins where it differs. The one the roster was carrying is
            # kept beside it: the census matches on printed names and having
            # both spellings to match against loses nobody.
            csv_nm = clean(r.get("name"))
            if csv_nm and csv_nm != (p.get("name") or ""):
                names.append((p.get("name"), csv_nm))
                p.setdefault("also_known_as", [])
                for old in ([p.get("name")] + list(p.get("also_known_as") or [])):
                    if old and old != csv_nm and old not in p["also_known_as"]:
                        p["also_known_as"].append(old)
                p["name"] = csv_nm
                p["name_key"] = X.name_key(csv_nm)
                p["initial_keys"] = sorted(X.initial_keys(csv_nm))
                adopted["name"] += 1

            gs = (r.get("google_scholar_id") or "").strip()
            if gs and p.get("google_scholar_id") != gs:
                p["google_scholar_id"] = gs
                adopted["scholar"] += 1
            sid = (r.get("scopus_id") or "").strip()
            # An id AAU prints that resolves to no author is refused -- Shirin
            # AlAmoor's card drops a digit -- and that judgement was already
            # made and recorded, so it is honoured here rather than re-made.
            if sid and sid != p.get("scopus_auid_rejected") \
                    and p.get("scopus_auid") != sid:
                p["scopus_auid"] = sid
                p["auid_tier"] = "high:aau-directory"
                p["auid_candidates"] = []
                adopted["scopus"] += 1

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
        # Anyone the directory does not list stays, and is marked. Three of
        # them publish with an Al Ain address and were added from the
        # suggestions screen for exactly that reason -- Anan Jarab alone has
        # about thirty AAU papers. Dropping them to match the directory would
        # lose real output to gain tidiness.
        in_csv = {id(find(nm)) for nm in rows_by_name if find(nm)}
        kept = 0
        for p in people:
            if id(p) not in in_csv and not p.get("added_from"):
                p["not_in_directory"] = True
                kept += 1
        print("adopted from the directory: %d names, %d colleges, "
              "%d Scopus ids, %d Scholar ids"
              % (adopted["name"], adopted["college"], adopted["scopus"],
                 adopted["scholar"]))
        for was, now in names[:12]:
            print("  name: %-32s -> %s" % ((was or "")[:32], now))
        for nm, was, now in conflicts:
            print("  college changed: %-30s %s -> %s" % (nm[:30], was, now))
        print("%d people are not in the directory and are kept, marked" % kept)
        blob["version"] = time.strftime("%Y-%m-%d") + "-directory-adopted"
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
    # Not only the programmes: every field the directory states must be
    # readable back off the roster, or the roster and the university disagree
    # and nobody would know which to believe.
    fields = {"name": [0, 0], "college": [0, 0], "scopus": [0, 0],
              "scholar": [0, 0]}
    if os.path.exists(PEOPLE_CSV):
        with open(PEOPLE_CSV, newline="", encoding="utf-8-sig") as fh:
            for r in csv.DictReader(fh):
                nm = clean(r.get("name"))
                p = find(nm)
                if not p:
                    continue

                def agree(key, ok, detail=""):
                    fields[key][0 if ok else 1] += 1
                    if not ok:
                        missing.append((nm, key, detail))

                agree("name", p.get("name") == nm,
                      "%r vs %r" % (p.get("name"), nm))
                col = COLLEGE.get((r.get("college") or "").strip())
                agree("college", (not col)
                      or col in (p.get("colleges") or [p.get("college")]),
                      "%s vs %s" % (p.get("college"), col))
                sid = (r.get("scopus_id") or "").strip()
                agree("scopus", (not sid) or p.get("scopus_auid") == sid
                      or sid == p.get("scopus_auid_rejected"),
                      "%s vs %s" % (p.get("scopus_auid"), sid))
                gs = (r.get("google_scholar_id") or "").strip()
                agree("scholar", (not gs) or p.get("google_scholar_id") == gs)
    print("verified %d (person, programme) pairs from the CSVs" % checked)
    for k, (ok, no) in fields.items():
        print("  %-9s %d agree, %d disagree" % (k, ok, no))
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
