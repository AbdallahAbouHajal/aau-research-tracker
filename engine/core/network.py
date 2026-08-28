"""Who Al Ain University publishes with, counted so the answer survives scrutiny.

Built on the printed address of every author slot -- the only source that can
say WHICH college worked with WHICH institution. The paper-level affiliation
list Scopus returns is truncated to one or two names and cannot carry a
collaboration graph; core/collab.py records that measurement.

Three rules decide every number here.

**Count per paper, never per author row.** Five Yarmouk co-authors on one
paper is one paper with Yarmouk.

**Quarantine consortium papers.** A handful of papers list hundreds of
institutions -- global burden-of-disease studies and the like -- and they are
not collaborations in any sense a research office means. Measured on this
corpus the largest ordinary paper lists 11 institutions and the smallest
consortium one lists 110, so a threshold of 25 sits in an empty band 99 wide
and cuts nothing real. Those few papers carry about four fifths of all
(paper, institution) pairs; left in, they decide every ranking on the screen.
They are excluded from every count and reported separately, never hidden.

**Publish fractional credit beside the raw count.** A paper shared with three
institutions is not the same as one shared with thirty, and 1/n says so.

A partner needs at least three joint papers to be ranked; below that one
co-author's address is not a partnership.
"""
import collections
import os
import re
import sys
import unicodedata

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import census as X                                      # noqa: E402
import collab as CO                                     # noqa: E402
import classify as CLS                                  # noqa: E402

MEGA = 25            # institutions on one paper, above which it is a consortium
MIN_JOINT = 3        # joint papers before a partner is ranked

# "Al-Faryan M.A.S." is a person, and it ranked fourth among the College of
# Business's partners until this. A candidate with no organisation word that
# looks like a surname followed by initials is not an institution.
_PERSONISH = re.compile(r"(?:\b[A-Z]\.){2,}|\b[A-Z]\.[A-Z]")
_ORG_WORD = re.compile("|".join(CO._ORG_RANK), re.I)

_SUBS = {"univ": "university", "inst": "institute", "tech": "technology",
         "sci": "science", "natl": "national", "intl": "international",
         "dept": "department"}
_STOP = {"the", "of", "for", "at", "and", "a", "de", "der", "di"}


def canon(name):
    """Fold spellings of one institution together, and nothing else."""
    n = unicodedata.normalize("NFKD", name or "")
    n = "".join(c for c in n if not unicodedata.combining(c)).lower()
    n = n.replace("&", " and ")
    n = re.sub(r"[^a-z0-9]+", " ", n)
    toks = [_SUBS.get(t, t) for t in n.split() if t and t not in _STOP]
    # A trailing acronym of the words before it -- "... university uaeu".
    if len(toks) > 2 and 2 <= len(toks[-1]) <= 6 and toks[-1].isalpha():
        initials = "".join(t[0] for t in toks[:-1])
        if all(c in initials for c in toks[-1]):
            i = j = 0                        # in order, not merely present
            for c in toks[-1]:
                j = initials.find(c, i)
                if j < 0:
                    break
                i = j + 1
            else:
                toks = toks[:-1]
    return " ".join(toks)


def institution(raw):
    """-> (display name, country) for one printed address, or ("", country).

    An institution must NAME itself as one. collab.split_affiliation() falls
    back to the first long part when no organisation word is present, which is
    right for a rough count and wrong here: an address like "Amman, Jordan" or
    a bare "China" then yields the country as the institution, and the first
    run of this ranked Jordan, the United Arab Emirates and Saudi Arabia as Al
    Ain University's three largest partners. Countries are counted, on their
    own card, from the part of the address that actually is one.
    """
    inst, country = CO.split_affiliation(raw)
    if not inst:
        return "", country
    if not _ORG_WORD.search(inst):
        return "", country                   # a city, a country, a department
    if _PERSONISH.search(inst):
        return "", country                   # a surname and initials
    if country and canon(inst) == canon(country):
        return "", country
    return inst, country


def build(run_blob, authors, log=print):
    """-> the whole Networking view-model, or None when there is nothing to say."""
    slots = (run_blob or {}).get("slots") or []
    papers = (run_blob or {}).get("papers") or {}

    per_paper = collections.defaultdict(dict)      # eid -> {key: display}
    countries = collections.defaultdict(dict)
    colleges = collections.defaultdict(set)        # eid -> AAU colleges
    lead = collections.defaultdict(bool)           # eid -> an AAU author led it
    corr = collections.defaultdict(bool)
    printed = set()

    for s in slots:
        eid = s.get("eid")
        if not eid:
            continue
        if s.get("college"):
            # Through the same map the rest of the app uses, or the old
            # taxonomy leaks back in and a partner shows "9 colleges".
            colleges[eid].add(CLS.map_college(s["college"]))
        raw = (s.get("raw_affiliation") or "").strip()
        if not raw:
            continue
        printed.add(eid)
        if CO.is_aau(raw):
            if s.get("is_first"):
                lead[eid] = True
            if s.get("is_corresponding"):
                corr[eid] = True
            continue
        name, country = institution(raw)
        if name and not CO.is_aau(name):
            per_paper[eid].setdefault(canon(name), name)
        if country and len(country) > 3:
            countries[eid].setdefault(canon(country), country)

    sizes = {e: len(m) for e, m in per_paper.items()}
    mega = {e for e, n in sizes.items() if n > MEGA}
    ordinary = [n for e, n in sizes.items() if e not in mega]
    log("  %d papers print their authors' addresses of %d in the corpus"
        % (len(printed), len(papers) or len(printed)))
    log("  consortium papers (>%d institutions): %d; largest ordinary paper "
        "lists %d, smallest consortium %d"
        % (MEGA, len(mega), max(ordinary or [0]),
           min([sizes[e] for e in mega] or [0])))

    pairs_all = sum(sizes.values())
    pairs_mega = sum(sizes[e] for e in mega)
    partners_all = len({k for m in per_paper.values() for k in m})
    partners_ok = len({k for e, m in per_paper.items() if e not in mega for k in m})
    log("  those %d papers carry %d of %d institution pairs (%.0f%%); distinct "
        "partners %d -> %d once they are set aside"
        % (len(mega), pairs_mega, pairs_all,
           100.0 * pairs_mega / max(1, pairs_all), partners_all, partners_ok))

    display, raw_n, frac, led = {}, collections.Counter(), collections.Counter(), collections.Counter()
    by_college = collections.defaultdict(collections.Counter)
    college_led = collections.defaultdict(collections.Counter)
    pips = collections.defaultdict(set)
    for eid, m in per_paper.items():
        if eid in mega:
            continue
        share = 1.0 / max(1, len(m))
        for k, name in m.items():
            display.setdefault(k, name)
            raw_n[k] += 1
            frac[k] += share
            if lead.get(eid) or corr.get(eid):
                led[k] += 1
            for c in colleges.get(eid, ()):
                by_college[c][k] += 1
                pips[k].add(c)
                if lead.get(eid) or corr.get(eid):
                    college_led[c][k] += 1

    def rows(counter, ledc, limit, floor):
        out = []
        for k, n in counter.most_common():
            if n < floor:
                break
            out.append({"name": display.get(k, k), "papers": n,
                        "credit": round(frac.get(k, 0.0), 2),
                        "aau_led": ledc.get(k, 0),
                        "colleges": sorted(pips.get(k, ()))})
            if len(out) >= limit:
                break
        return out

    joint = collections.Counter()
    for eid, cols in colleges.items():
        if eid in mega:
            continue
        cl = sorted(c for c in cols if c)
        for i in range(len(cl)):
            for j in range(i + 1, len(cl)):
                joint[(cl[i], cl[j])] += 1

    ctry = collections.Counter()
    cdisp = {}
    for eid, m in countries.items():
        if eid in mega:
            continue
        for k, v in m.items():
            ctry[k] += 1
            cdisp.setdefault(k, v)

    return {
        "coverage": {"printed": len(printed), "papers": len(papers) or len(printed),
                     "mega": len(mega), "mega_pairs": pairs_mega,
                     "pairs": pairs_all, "threshold": MEGA,
                     "largest_ordinary": max(ordinary or [0]),
                     "smallest_mega": min([sizes[e] for e in mega] or [0]),
                     "partners_all": partners_all, "partners": partners_ok,
                     "min_joint": MIN_JOINT},
        "top": rows(raw_n, led, 40, MIN_JOINT),
        "by_college": {c: rows(m, college_led[c], 8, 2)
                       for c, m in by_college.items()},
        "shared": [r for r in rows(raw_n, led, 60, MIN_JOINT)
                   if len(r["colleges"]) >= 2][:24],
        "countries": [{"name": cdisp.get(k, k), "papers": n}
                      for k, n in ctry.most_common(30)],
        "joint": [{"a": a, "b": b, "papers": n} for (a, b), n in joint.most_common(28)],
    }
