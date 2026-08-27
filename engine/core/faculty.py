"""The faculty list -- the tracker's ground truth, and the thing that makes
'student' a fact instead of a guess.

Collected by hand from aau.ac.ae (via Claude for Chrome), imported as CSV,
and stored as a dated version. Every run records which version it used, so a
classification can always be traced back to the roster that produced it.
"""
import csv
import io
import json
import os
import re
import sys
import unicodedata
from datetime import date

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import census as X

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DIR = os.path.join(ROOT, "data", "faculty")
os.makedirs(DIR, exist_ok=True)

# AAU's own directory lists exactly these. Anything else in the CSV is a
# spelling of one of them, or a mistake worth surfacing.
COLLEGES = [
    "College of Engineering",
    "College of Pharmacy",
    "College of Law",
    "College of Education, Humanities and Social Sciences",
    "College of Business",
    "College of Communication and Media",
    "College of Dentistry",
    "College of Nursing",
]
_CANON = [
    ("engineer", COLLEGES[0]), ("pharmac", COLLEGES[1]), ("law", COLLEGES[2]),
    ("education", COLLEGES[3]), ("humanities", COLLEGES[3]),
    ("social", COLLEGES[3]), ("business", COLLEGES[4]),
    ("communicat", COLLEGES[5]), ("media", COLLEGES[5]),
    ("dentist", COLLEGES[6]), ("nurs", COLLEGES[7]),
]
# 155 of 209 real rows arrive as "Qutaibah Althebyan, Ph.D". Left in place the
# degree defeats every name match, because Scopus never prints it.
_DEGREE = re.compile(
    r"\s*,?\s*\b(Ph\.?\s?D|M\.?\s?Sc|M\.?\s?A|MBA|DBA|M\.?\s?Ed|"
    r"MD|DDS|BDS|Pharm\.?D|M\.?Phil|Ed\.?D)\.?\s*$", re.I)
_TITLEY = re.compile(r"^\s*(Prof|Professor|Dr|Mr|Mrs|Ms|Eng)\.?\s+", re.I)


def clean_name(raw):
    """Strip degrees, honorifics and stray combining marks.

    One real row carries four Arabic kasra marks before the title
    ('\u0650\u0650\u0650\u0650Associate Professor'); the same class of
    invisible character turns up in names.
    """
    s = unicodedata.normalize("NFC", (raw or "").strip())
    s = "".join(c for c in unicodedata.normalize("NFD", s)
                if not unicodedata.combining(c) or c in "\u0640")
    s = unicodedata.normalize("NFC", s)
    prev = None
    while prev != s:                       # "Name, Ph.D, M.Sc"
        prev = s
        s = _DEGREE.sub("", s).strip(" ,")
    s = _TITLEY.sub("", s)
    return re.sub(r"\s+", " ", s).strip(" ,")


def clean_text(raw):
    s = unicodedata.normalize("NFD", (raw or "").strip())
    s = "".join(c for c in s if not unicodedata.combining(c))
    return re.sub(r"\s+", " ", unicodedata.normalize("NFC", s)).strip()


# A dean is reachable at Engineering@aau.ac.ae, but that is a role mailbox and
# must never be used to identify a person.
_ROLE_MAIL = re.compile(
    r"^(engineering|pharmacy|law|business|communication|dentistry|nursing|"
    r"education|cyber\w*|software\w*|[a-z]+_ad|info|admission\w*|registrar|"
    r"library|research|hr)@", re.I)

REQUIRED = ["name", "college"]
OPTIONAL = ["department", "title", "email", "profile_url", "staff_type"]


def canon_college(raw):
    """Snap a college label to AAU's official eight."""
    t = re.sub(r"\s+", " ", (raw or "")).strip().lower()
    if not t:
        return ""
    for key, name in _CANON:
        if key in t:
            return name
    return (raw or "").strip()


def parse_csv(text):
    """Read the CSV from Claude for Chrome. Returns (rows, problems)."""
    text = text.lstrip("﻿").strip()
    # tolerate the model wrapping it in a code fence
    text = re.sub(r"^```[a-zA-Z]*\n|```$", "", text).strip()
    if not text:
        return [], ["the file is empty"]

    rows, problems = [], []
    rdr = csv.DictReader(io.StringIO(text))
    have = [(h or "").strip().lower() for h in (rdr.fieldnames or [])]
    for col in REQUIRED:
        if col not in have:
            problems.append("missing required column: %s" % col)
    if problems:
        return [], problems

    seen = {}
    for i, raw in enumerate(rdr, 2):
        rec = {k: (raw.get(k) or raw.get(k.title()) or "").strip()
               for k in REQUIRED + OPTIONAL}
        rec["raw_name"] = rec["name"]
        rec["name"] = clean_name(rec["name"])
        rec["title"] = clean_text(rec.get("title"))
        if not rec["name"]:
            problems.append("row %d: no name" % i)
            continue
        col = canon_college(rec["college"])
        if not col:
            problems.append("row %d (%s): no college" % (i, rec["name"]))
        elif col not in COLLEGES:
            problems.append("row %d (%s): unrecognised college %r"
                            % (i, rec["name"], rec["college"]))
        rec["college"] = col
        rec["name_key"] = X.name_key(rec["name"])
        rec["initial_keys"] = sorted(X.initial_keys(rec["name"]))
        rec["is_academic"] = (rec.get("staff_type", "").lower() != "administrative")
        em = (rec.get("email") or "").strip().lower()
        rec["email"] = em
        rec["email_kind"] = ("role" if em and _ROLE_MAIL.match(em)
                             else ("personal" if em else ""))

        # a person listed twice (two colleges, or two pages) is one person
        prev = seen.get(rec["name_key"])
        if prev:
            # The AAU site cross-lists a few people under two colleges (Azza
            # Galal Ramadan appears under Pharmacy and Nursing, same email and
            # profile). The first listing is the real home; the second is a
            # courtesy listing. Keep both, but the first one leads.
            if rec["college"] and rec["college"] not in prev["colleges"]:
                prev["colleges"].append(rec["college"])
                prev["also_listed_in"] = prev["colleges"][1:]
            for f in OPTIONAL:
                if not prev.get(f) and rec.get(f):
                    prev[f] = rec[f]
            continue
        rec["colleges"] = [rec["college"]] if rec["college"] else []
        seen[rec["name_key"]] = rec
        rows.append(rec)

    return rows, problems


def save(rows, source="chrome", note=""):
    """Store a dated version and point `latest` at it."""
    stamp = date.today().isoformat()
    path = os.path.join(DIR, "%s.json" % stamp)
    n = 1
    while os.path.exists(path):
        n += 1
        path = os.path.join(DIR, "%s-%d.json" % (stamp, n))
    blob = {"version": os.path.basename(path)[:-5], "captured": stamp,
            "source": source, "note": note, "count": len(rows), "people": rows}
    with open(path, "w") as fh:
        json.dump(blob, fh, indent=1)
    with open(os.path.join(DIR, "latest.json"), "w") as fh:
        json.dump(blob, fh, indent=1)
    return blob


def load(version=None):
    path = os.path.join(DIR, "%s.json" % version) if version \
        else os.path.join(DIR, "latest.json")
    if not os.path.exists(path):
        return None
    with open(path) as fh:
        return json.load(fh)


def versions():
    out = []
    for f in sorted(os.listdir(DIR), reverse=True):
        if f.endswith(".json") and f != "latest.json":
            try:
                with open(os.path.join(DIR, f)) as fh:
                    b = json.load(fh)
                out.append({"version": b.get("version"), "captured": b.get("captured"),
                            "count": b.get("count"), "source": b.get("source")})
            except Exception:
                pass
    return out


def summary(blob):
    if not blob:
        return {"total": 0, "by_college": {}, "academic": 0}
    by = {}
    for p in blob["people"]:
        for c in (p.get("colleges") or [p.get("college")]):
            if c:
                by[c] = by.get(c, 0) + 1
    return {"total": len(blob["people"]), "by_college": by,
            "academic": sum(1 for p in blob["people"] if p.get("is_academic")),
            "version": blob.get("version"), "captured": blob.get("captured")}
