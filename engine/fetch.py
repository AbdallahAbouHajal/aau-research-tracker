"""Fetch the corpus for a run: two routes, unioned.

Route A -- AF-ID(60105817) for the window. The institutional query; catches
everyone whose paper carries an AAU address.

Route B -- AU-ID(x) for every resolved faculty member. Catches papers where
Scopus did not attach the affiliation. Measured: Mosab Tabash returns 103
papers by AU-ID against the 99 the AF-ID route found, so route B is not
redundant.

Both go through the census's cached, key-rotating client, so a re-run of an
unchanged window costs nothing.
"""
import datetime
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import census as X

PAGE = 25  # hard maximum on these keys; 50+ returns HTTP 400


def window(years_back=1, today=None):
    """Rolling window: the current year and `years_back` before it."""
    y = (today or datetime.date.today()).year
    return list(range(y - years_back, y + 1))


def _entry(e, year_hint=None):
    affs = e.get("affiliation") or []
    if isinstance(affs, dict):
        affs = [affs]
    return {
        "eid": e.get("eid"),
        "scopus_id": (e.get("dc:identifier") or "").replace("SCOPUS_ID:", ""),
        "doi": X.norm_doi(e.get("prism:doi")),
        "title": e.get("dc:title"),
        "journal": e.get("prism:publicationName"),
        "issn": e.get("prism:issn"),
        "cover_date": e.get("prism:coverDate"),
        "year": int((e.get("prism:coverDate") or "0")[:4] or 0) or year_hint,
        "doctype": e.get("subtypeDescription"),
        "cited_by": int(e.get("citedby-count") or 0),
        "first_author": e.get("dc:creator"),
        "openaccess": e.get("openaccessFlag"),
        "doc_afids": [a.get("afid") for a in affs if a.get("afid")],
        "doc_affilnames": [a.get("affilname") for a in affs if a.get("affilname")],
    }


def _search(query, year_hint=None, cap=6000, log=None):
    """Paginate a Scopus query.

    sort=+eid is mandatory. Scopus is a live index: without a total order on a
    stable key, pagination both duplicates and DROPS records. An unsorted run
    once returned 1,330 rows containing only 1,293 unique EIDs.
    """
    first = X.scopus_get("/content/search/scopus",
                         {"query": query, "count": 1, "start": 0, "sort": "+eid"})
    total = int(first["search-results"]["opensearch:totalResults"])
    out, start = [], 0
    while start < min(total, cap):
        r = X.scopus_get("/content/search/scopus",
                         {"query": query, "count": PAGE, "start": start,
                          "sort": "+eid"})
        rows = r["search-results"].get("entry") or []
        if not rows or "error" in rows[0]:
            break
        out.extend(_entry(e, year_hint) for e in rows)
        start += PAGE
    return total, out


def _printed_aau(paper):
    """Did anyone on this paper actually print an Al Ain University address?

    Checks the Scopus document affiliation names first (cheap, already in
    hand), then OpenAlex's raw_affiliation_strings via the census badge --
    which requires the printed string, not a ROR link.
    Returns (ok, reason).
    """
    for nm in (paper.get("doc_affilnames") or []):
        if X.AAU_RE.search(nm or ""):
            return True, "scopus_affilname"
    doi = paper.get("doi")
    if not doi:
        return False, "no DOI and Scopus names no AAU affiliation"
    try:
        w = X.openalex("/works/doi:" + doi)
    except Exception:
        return False, "could not verify: no OpenAlex record"
    for a in (w.get("authorships") or []):
        ok, sig = X.badge(a)
        if ok and sig.get("string"):
            return True, "printed_affiliation"
    return False, "no author printed an Al Ain University address"


def run(faculty=None, years=None, log=print, stage=None,
        routes="ab", papers=None, stats=None,
        date_from=None, date_to=None):
    """Returns {'papers': {eid: paper}, 'stats': {...}}.

    `stage(n, pct)` is called as the two routes progress so a UI can show
    which of the six stages is working rather than a single spinner.
    """
    def _stage(n, pct):
        if stage:
            try:
                stage(n, pct)
            except Exception:
                pass
    # A day-level window. Scopus is queried by PUBYEAR -- the reliable filter
    # these keys have -- and every paper carries prism:coverDate, so the exact
    # range is applied to what comes back. Asking Scopus for a date range
    # directly needs syntax these keys do not all honour.
    if date_from or date_to:
        lo = int(str(date_from or "1900-01-01")[:4])
        hi = int(str(date_to or "2100-12-31")[:4])
        years = list(range(lo, hi + 1))
    years = years or window()
    faculty = faculty or []

    def _in_range(p):
        d = (p.get("cover_date") or "")[:10]
        if not d:
            return True                 # no date printed: keep, do not guess
        if date_from and d < str(date_from)[:10]:
            return False
        if date_to and d > str(date_to)[:10]:
            return False
        return True
    # `routes` lets the two halves run as separate steps: "a" is the
    # institution query, "b" is the per-author sweep behind the gate. A CI job
    # runs them as two named steps so progress is real rather than a spinner.
    papers = {} if papers is None else papers
    stats = {"years": years} if stats is None else stats
    stats["years"] = years

    # --- route A: the institution
    a_total = 0
    if "a" not in routes:
        pass
    else:
      _stage(2, 5)
      for i, y in enumerate(years):
        q = "AF-ID(%s) AND PUBYEAR IS %d" % (X.AAU_AFID, y)
        total, rows = _search(q, year_hint=y, log=log)
        a_total += total
        for p in rows:
            if p["eid"] and _in_range(p):
                papers.setdefault(p["eid"], p)
        log("  AF-ID %d: %d papers" % (y, total))
        _stage(2, int(90 * (i + 1) / max(1, len(years))))
        if date_from or date_to:
          stats["date_from"] = str(date_from or "")[:10]
          stats["date_to"] = str(date_to or "")[:10]
          log("  window narrowed to %s .. %s -> %d papers"
              % (stats.get("date_from") or "any", stats.get("date_to") or "any",
                 len(papers)))
      stats["af_id_reported"] = a_total
      stats["af_id_unique"] = len(papers)
      if a_total != len(papers):
          log("  !! AF-ID reported %d but %d unique EIDs -- pagination drift"
              % (a_total, len(papers)))
      if "b" not in routes:
          stats["total_papers"] = len(papers)
          return {"papers": papers, "stats": stats}

    # --- route B: the faculty sweep, GATED
    #
    # AU-ID(x) returns everything that person published ANYWHERE. Anan Jarab
    # has 53 papers in this window; only 30 print Al Ain University. Taking
    # the union blindly imports the other 23 and re-creates, in a new costume,
    # the OpenAlex mistake that produced the retracted 568-paper claim.
    #
    # Scopus cannot filter them: doc_afids is empty on all 1,330 papers, and
    # the affiliation array is truncated. So a swept paper is admitted only if
    # some author's PRINTED affiliation says Al Ain University. A bare ROR
    # link is explicitly not enough -- that is the retraction rule, encoded.
    ids = sorted({p["scopus_auid"] for p in faculty if p.get("scopus_auid")})
    before, added = len(papers), 0
    rejected = []
    lo = min(years)
    _stage(2, 100)
    for i, aid in enumerate(ids, 1):
        if i % 10 == 0 or i == len(ids):
            _stage(3, int(97 * i / max(1, len(ids))))
        if i % 40 == 0:
            log("  faculty sweep %d/%d (+%d new papers)" % (i, len(ids), added))
        try:
            _, rows = _search("AU-ID(%s) AND PUBYEAR > %d" % (aid, lo - 1), log=log)
        except Exception as exc:
            log("  sweep failed for AU-ID %s: %s" % (aid, str(exc)[:60]))
            continue
        for p in rows:
            if not (p["eid"] and p["year"] in years) or p["eid"] in papers:
                continue
            if not _in_range(p):
                continue
            ok, why = _printed_aau(p)
            if ok:
                p["found_via"] = "faculty_sweep"
                p["aau_evidence"] = why
                papers[p["eid"]] = p
                added += 1
            else:
                rejected.append({"eid": p["eid"], "doi": p.get("doi"),
                                 "title": (p.get("title") or "")[:110],
                                 "journal": p.get("journal"),
                                 "reason": why})
    _stage(3, 100)
    stats["faculty_sweep_rejected"] = len(rejected)
    stats["rejected_list"] = rejected      # so the workbook can show why
    stats["faculty_ids_swept"] = len(ids)
    stats["faculty_sweep_added"] = added
    stats["total_papers"] = len(papers)
    log("  faculty sweep over %d AU-IDs added %d papers the AF-ID query missed"
        % (len(ids), added))
    log("  corpus: %d papers (%d from AF-ID, %d from the sweep)"
        % (len(papers), before, added))
    if rejected:
        log("  rejected %d swept papers: no author printed an AAU affiliation"
            % len(rejected))
    return {"papers": papers, "stats": stats, "rejected": rejected}
