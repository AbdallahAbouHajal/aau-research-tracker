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
    # A department belongs to an institution and is not one, so try the
    # address again without the parts that name one. "Department of Computer
    # Science, School Education Department, Government of Punjab" resolved to
    # the department and put it in the College of Engineering's top three.
    inst, country = CO.split_affiliation(raw)
    if inst and "department" in inst.lower():
        trimmed = ", ".join(t for t in raw.split(",")
                            if "department" not in t.lower())
        alt, _ = CO.split_affiliation(trimmed)
        if alt and "department" not in alt.lower():
            inst = alt
    if not inst:
        return "", country
    if not _ORG_WORD.search(inst):
        return "", country                   # a city, a country, a department
    if _PERSONISH.search(inst):
        return "", country                   # a surname and initials
    if country and canon(inst) == canon(country):
        return "", country
    return inst, country


def backfill_affiliations(papers, have_printed, log=print, budget_s=2400):
    """Ask Scopus for the institutions on papers whose authors' addresses we
    do not hold.

    The Search API reports ONE affiliation per paper -- measured over eight
    papers it said 1, 1, 1, 1, 1, 1, 1, 1 where the truth was 4, 1, 1, 5, 3,
    4, 1 and 14. That single number is why the collaboration screen could only
    speak for the third of the corpus covered by the census export.

    The abstract endpoint at view=META carries the full affiliation array, one
    request per paper, about a second each. It is not free, so: only papers
    that need it are asked for, the answers are cached durably -- a published
    paper's institution list does not change -- and the whole pass stops at a
    time budget and reports how far it got rather than running a job for an
    hour. Coverage is published either way, so a partial backfill is visible
    as a partial backfill.
    """
    import time
    todo = [e for e in papers if e not in have_printed
            and not papers[e].get("meta_affils")]
    if not todo:
        return 0
    log("  filling in institutions for %d papers the export does not cover"
        % len(todo))
    t0, done, failed = time.time(), 0, 0
    for i, eid in enumerate(todo, 1):
        if time.time() - t0 > budget_s:
            log("  stopped at the %d-minute budget: %d of %d filled in"
                % (budget_s // 60, done, len(todo)))
            break
        # The run store calls it scopus_id; the hand-off to the second
        # job calls it sid. Reading only one of them skipped every paper
        # in silence -- 2,955 iterations, no fetches, a tenth of a second.
        rec = papers[eid]
        sid = str(rec.get("scopus_id") or rec.get("sid") or "").strip()
        if not sid and eid.startswith("2-s2.0-"):
            sid = eid.split("2-s2.0-", 1)[1]          # last resort

        if not sid:
            continue
        try:
            d = X.scopus_get("/content/abstract/scopus_id/" + sid,
                             {"view": "META"})
        except Exception:
            failed += 1
            continue
        core = (d or {}).get("abstracts-retrieval-response") or {}
        aff = core.get("affiliation")
        aff = aff if isinstance(aff, list) else ([aff] if aff else [])
        papers[eid]["meta_affils"] = [
            {"name": a.get("affilname") or "",
             "country": a.get("affiliation-country") or ""}
            for a in aff if a and a.get("affilname")]
        done += 1
        if i % 200 == 0:
            log("    %d/%d (%.0f%% of the way, %.0fs elapsed)"
                % (i, len(todo), 100.0 * i / len(todo), time.time() - t0))
    log("  institutions filled in for %d papers (%d could not be fetched)"
        % (done, failed))
    return done


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

    # Papers the export does not reach: their institution list came from the
    # abstract endpoint, so they count exactly like the rest. Without this the
    # screen spoke for a third of the corpus.
    for eid, p in (papers or {}).items():
        if eid in printed:
            continue
        for a in (p.get("meta_affils") or []):
            nm = a.get("name") or ""
            if not nm or CO.is_aau(nm):
                continue
            per_paper[eid].setdefault(canon(nm), nm)
            c = a.get("country") or ""
            if c:
                countries[eid].setdefault(canon(c), c)
        if p.get("meta_affils"):
            printed.add(eid)

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
