"""Who Al Ain University publishes with, from the affiliations papers print.

Two sources, and they are not equal:

  * Author rows carry `raw_affiliation` -- the address that author printed on
    that paper, in full. This is the honest source, and it is the only one that
    can say WHICH AAU college worked with WHICH outside institution, because
    the row also carries the college. It exists only for papers covered by the
    census export.
  * The Scopus search API returns an `affiliation` array per paper, but it is
    TRUNCATED: measured over 25 papers it returned one institution for 24 of
    them and two for the last. It cannot carry a collaboration graph. It does
    carry a country, which is worth having for papers the export does not
    reach, and nothing more is claimed from it.

So coverage is reported alongside every figure. A partnership count over a
third of the corpus is a real finding; presented as if it covered all of it,
it is a lie.

Counting is per PAPER, never per author row: five co-authors from Yarmouk on
one paper is one collaboration with Yarmouk, not five.
"""
import collections
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import census as X                                      # noqa: E402

# A comma-separated part that names an organisation rather than a department,
# a city or a state. Ordered: a university beats a college beats a centre, so
# "Department of Chemistry, Yarmouk University, Irbid, Jordan" resolves to
# Yarmouk University and not to the department.
_ORG_RANK = ("universit", "institut", "polytechn", "academy", "hospital",
             "college", "school", "centre", "center", "laborator",
             "foundation", "ministry", "authority", "clinic", "corporation")
_ORG = re.compile("|".join(_ORG_RANK), re.I)

# Anything this short is a state or a postcode fragment, not an institution.
_TOO_SHORT = 4


def _parts(s):
    return [t.strip() for t in (s or "").split(",") if t.strip()]


def split_affiliation(raw):
    """-> (institution, country). Either may be "" when it cannot be read."""
    p = _parts(raw)
    if not p:
        return "", ""
    country = p[-1] if len(p) > 1 else ""
    body = p[:-1] if len(p) > 1 else p
    cands = [t for t in body if len(t) > _TOO_SHORT and _ORG.search(t)]
    for want in _ORG_RANK:
        for c in cands:
            if want in c.lower():
                return c, country
    # No organisation word anywhere: the first long part is the best guess,
    # and a guess is better than dropping the row silently.
    for t in body:
        if len(t) > _TOO_SHORT:
            return t, country
    return "", country


def canon(name):
    """Fold spellings of one institution together -- and only those.

    "The University of Jordan" and "University of Jordan" are one place.
    "University of Bahrain" and "University College of Bahrain" are not, so
    the distinguishing words are kept: an earlier attempt that stripped
    "university" and "college" merged three different pharmacy schools.
    """
    n = (name or "").lower()
    n = re.sub(r"[^a-z0-9 ]", " ", n)
    n = re.sub(r"\buniv\b", "university", n)
    n = re.sub(r"\bthe\b", " ", n)
    n = re.sub(r"\s+", " ", n).strip()
    return n


def is_aau(text):
    return bool(X.AAU_RE.search(text or ""))


def build(papers, slots, log=print):
    """-> the collaboration view: partners per college, countries, coverage."""
    # paper -> the AAU colleges on it, and the outside institutions on it
    colleges = collections.defaultdict(set)
    partners = collections.defaultdict(dict)      # eid -> {canon: display}
    countries = collections.defaultdict(dict)
    seen_rows = collections.Counter()

    for s in slots:
        eid = s.get("eid")
        if not eid:
            continue
        if s.get("college"):
            colleges[eid].add(s["college"])
        raw = (s.get("raw_affiliation") or "").strip()
        if not raw:
            continue
        seen_rows[eid] += 1
        if is_aau(raw):
            continue
        inst, country = split_affiliation(raw)
        if inst and not is_aau(inst):
            partners[eid].setdefault(canon(inst), inst)
        if country and len(country) > 3:
            countries[eid].setdefault(canon(country), country)

    # Papers the export does not reach still have the paper-level list, which
    # is truncated -- used for COUNTRY only, and never for a partnership count.
    for eid, p in (papers or {}).items():
        if seen_rows.get(eid):
            continue
        for a in (p.get("doc_affilnames") or []):
            if a and not is_aau(a):
                countries[eid].setdefault(canon(a), a)

    detailed = set(seen_rows)
    total = len(papers or {}) or len(colleges)

    # ---- partners per college, counted once per paper ---------------------
    per_college = collections.defaultdict(lambda: collections.defaultdict(int))
    display = {}
    joint = collections.Counter()               # AAU college <-> AAU college
    for eid, cols in colleges.items():
        for k, name in (partners.get(eid) or {}).items():
            display.setdefault(k, name)
            for c in cols:
                per_college[c][k] += 1
        cl = sorted(c for c in cols if c)
        for i in range(len(cl)):
            for j in range(i + 1, len(cl)):
                joint[(cl[i], cl[j])] += 1

    out_colleges = {}
    for c, m in per_college.items():
        rows = sorted(m.items(), key=lambda kv: (-kv[1], display.get(kv[0], "")))
        out_colleges[c] = [{"name": display.get(k, k), "papers": n}
                           for k, n in rows]

    overall = collections.Counter()
    for eid, m in partners.items():
        for k in m:
            overall[k] += 1

    ctry = collections.Counter()
    for eid, m in countries.items():
        for k in m:
            ctry[k] += 1
    ctry_display = {}
    for m in countries.values():
        for k, v in m.items():
            ctry_display.setdefault(k, v)

    log("  collaboration: %d papers carry printed affiliations of %d (%.0f%%)"
        % (len(detailed), total, 100.0 * len(detailed) / max(1, total)))
    return {
        "coverage": {"detailed": len(detailed), "papers": total},
        "top": [{"name": display.get(k, k), "papers": n}
                for k, n in overall.most_common(40)],
        "by_college": out_colleges,
        "countries": [{"name": ctry_display.get(k, k), "papers": n}
                      for k, n in ctry.most_common(60)],
        "joint": [{"a": a, "b": b, "papers": n}
                  for (a, b), n in joint.most_common(40)],
    }
