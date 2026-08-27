"""Resolve a Scopus AU-ID from what the person's own AAU page declares.

The user's idea, and it beats every name-based tier -- for a reason worth
stating: it does not make the name comparison smarter, it makes the haystack
smaller. Muhammad Sarfraz has nine candidate AU-IDs among 9,364 exported
names; on one of his own papers he has one among five co-authors.

Three routes on an aau.ac.ae/en/staff/ page, best first:

  1. DECLARED   the "SC" icon links to scopus.com/authid/detail.uri?authorId=
                -- the person's own Scopus profile. Nothing beats a self-
                declared ID, but it is still verified, never trusted blind:
                a stale or mistyped link is a confident wrong answer.
  2. EID        "Selected Publications" links each cite a Scopus record
                (eid=2-s2.0-...). Fetch the abstract, read its author list,
                keep the author whose name fits. Several papers vote.
  3. TITLE      structured "Published in:" entries give a title, which is
                nearly a unique key -> one paper -> one short author list.

Routes 1 and 2 are cross-checked against each other. Agreement is the
strongest evidence available here; disagreement goes to review rather than
picking one, because both routes are the person's own claim about themselves.
"""
import collections
import html
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import census as X
import translit as TL

UA = {"User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/151 Safari/537.36"}

_AUTHID = re.compile(r"scopus\.com/authid/detail\.uri\?(?:[^\"']*&(?:amp;)?)?authorId=(\d{6,})", re.I)
_EID = re.compile(r"(2-s2\.0-\d{8,})")
_TITLE = re.compile(r"<h4>\s*<a[^>]*>\s*(.{20,200}?)\s*</a>\s*</h4>\s*<p>\s*Published in", re.S | re.I)


def page(url):
    """Raw HTML of an AAU staff page, or ""."""
    if not url or "/staff/" not in url:
        return ""
    try:
        raw = X.http(url, headers=UA, tag="staff", timeout=45, accept_404=True)
    except Exception:
        return ""
    return (raw or b"").decode("utf-8", "replace")


def scrape(url):
    """-> {"declared": [auid], "eids": [...], "titles": [...]}"""
    h = page(url)
    if not h:
        return {"declared": [], "eids": [], "titles": []}
    # ONLY the "SC" icon in the profile's own social box is this person's ID.
    # Selected Publications link every co-author to their Scopus profile too,
    # so scanning the whole page returned seven IDs for a single academic.
    box = re.search(r'class="social-box".*?</div>', h, re.S)
    own = _AUTHID.findall(box.group(0)) if box else []
    return {
        "declared": sorted(set(own)),
        "page_ids": sorted(set(_AUTHID.findall(h))),
        "eids": sorted(set(_EID.findall(h))),
        "titles": [html.unescape(re.sub(r"<[^>]+>", " ", t)).strip()
                   for t in _TITLE.findall(h)],
    }


def _authors_of_eid(eid):
    """-> [(auid, printed name)] for a paper -- FIRST AUTHOR ONLY.

    These keys cannot see a full author list: abstract view=FULL/REF and
    search view=COMPLETE all return 401, and META carries just dc:creator.
    So this votes only when the person is first author on their own cited
    paper. That is a real limit, not a bug -- it is why verify() below
    carries the weight instead of co-author matching.
    """
    try:
        j = X.scopus_get("/content/abstract/eid/" + eid, {"view": "META"}) or {}
    except Exception:
        return []
    core = ((j.get("abstracts-retrieval-response") or {}).get("coredata")) or {}
    grp = ((core.get("dc:creator") or {}).get("author")) or []
    if isinstance(grp, dict):
        grp = [grp]
    out = []
    for a in grp:
        aid = re.sub(r"\D", "", str(a.get("@auid") or ""))
        nm = (a.get("preferred-name") or {}).get("ce:indexed-name") or \
            a.get("ce:indexed-name") or ""
        if aid:
            out.append((aid, nm))
    return out


AAU_AF = "60105817"


def _count(query):
    try:
        j = X.scopus_get("/content/search/scopus",
                         {"query": query, "count": 1, "field": "eid",
                          "sort": "+eid"}) or {}
        return int((j.get("search-results") or {}).get(
            "opensearch:totalResults") or 0)
    except Exception:
        return -1


def verify(auid, name):
    """Does this AU-ID really belong to this person?

    Author Retrieval is locked, but the Search API answers the same question
    indirectly and more usefully: AUTHLASTNAME inside AU-ID() confirms the
    surname Scopus files the ID under, and AF-ID confirms the person has
    actually published from Al Ain University. A profile page linking a
    stale or mistyped ID fails both.
    """
    toks = [t for t in re.sub(r"[.,]", " ", name or "").split() if len(t) > 1]
    out = {"total": _count("AU-ID(%s)" % auid), "surname": "", "sur_hits": 0,
           "aau": _count("AU-ID(%s) AND AF-ID(%s)" % (auid, AAU_AF)),
           "recent": _count("AU-ID(%s) AND PUBYEAR > 2024" % auid)}
    # No usable name (the caller only had a URL): the AU-ID still gets its
    # paper counts, it just cannot be name-verified. Reported honestly as
    # unverified rather than crashing the request.
    if not toks:
        out["ok"] = out["total"] > 0 and out["aau"] > 0
        out["via"] = "aau-papers-only" if out["ok"] else ""
        return out
    cands = [toks[-1]]
    if len(toks) > 2:
        cands.append(" ".join(toks[-2:]))
        # Scopus glues the article: roster "Hussein Al Sarhan" is filed as
        # "Alsarhan, Hussein". Separated, glued and hyphenated all get tried.
        if toks[-2].lower() in ("al", "el", "abu", "abd", "bani", "bin", "ben"):
            cands += [toks[-2] + toks[-1], toks[-2] + "-" + toks[-1]]
    for cand in cands:
        h = _count('AU-ID(%s) AND AUTHLASTNAME("%s")' % (auid, cand))
        if h > out["sur_hits"]:
            out["sur_hits"], out["surname"] = h, cand
    # A surname query can miss for a reason that is not a wrong ID: Scopus
    # files "Hussein Al Sarhan" as "Al-Srehan, Hussein" -- a vowel-swapped
    # transliteration no exact match reaches. When the surname misses, fall
    # back to the given name, which is far more stable across variants, and
    # require AAU papers so the check still discriminates.
    # AUTHOR-NAME is looser than AUTHLASTNAME and catches variants the exact
    # surname index misses.
    if out["sur_hits"] == 0 and out["total"] > 0:
        for cand in cands:
            h = _count('AU-ID(%s) AND AUTHOR-NAME("%s")' % (auid, cand))
            if h > out["sur_hits"]:
                out["sur_hits"], out["surname"] = h, cand
                out["loose"] = True
    # Last resort: the given-name INITIAL. These keys resolve AUTHFIRST only
    # to an initial -- a full first name always returns 0 -- so this is a
    # weak signal and is accepted only alongside real AAU output.
    out["first"] = 0
    if out["sur_hits"] == 0 and toks and out["total"] > 0:
        out["first"] = _count('AU-ID(%s) AND AUTHFIRST("%s")'
                              % (auid, toks[0][0]))
    out["ok"] = out["total"] > 0 and (
        out["sur_hits"] > 0 or (out["first"] > 0 and out["aau"] > 0))
    out["via"] = ("surname-loose" if out.get("loose") else "surname") \
        if out["sur_hits"] else ("initial+aau" if out["ok"] else "")
    return out


def _authors_of_title(title):
    """Search Scopus for an exact title, then read that paper's authors."""
    t = re.sub(r'["\\]', " ", title).strip()
    if len(t) < 20:
        return []
    try:
        j = X.scopus_get("/content/search/scopus",
                         {"query": 'TITLE("%s")' % t, "count": 5,
                          "field": "eid,dc:title", "sort": "+eid"}) or {}
    except Exception:
        return []
    ents = ((j.get("search-results") or {}).get("entry")) or []
    want = X.norm_name(re.sub(r"[^A-Za-z0-9 ]", " ", t)).split()
    for e in ents[:3]:
        got = X.norm_name(re.sub(r"[^A-Za-z0-9 ]", " ",
                                 e.get("dc:title") or "")).split()
        # the search is fuzzy; require the titles to really be the same paper
        if want and len(set(want) & set(got)) >= max(4, int(len(want) * 0.7)):
            return _authors_of_eid(e.get("eid") or "")
    return []


def _name_of(auid):
    """The name Scopus prints for an AU-ID, via one of its papers."""
    try:
        j = X.scopus_get("/content/search/scopus",
                         {"query": "AU-ID(%s)" % auid, "count": 1,
                          "field": "eid", "sort": "+eid"}) or {}
        ents = ((j.get("search-results") or {}).get("entry")) or []
        if not ents:
            return "", 0
        total = int((j.get("search-results") or {}).get("opensearch:totalResults") or 0)
        for aid, nm in _authors_of_eid(ents[0].get("eid") or ""):
            if aid == str(auid):
                return nm, total
    except Exception:
        pass
    return "", 0


def resolve(person, max_docs=6):
    """-> dict with auid, tier, evidence. Never guesses between two claims."""
    url = person.get("profile_url") or person.get("aau_profile") or ""
    name = person.get("name") or ""
    found = scrape(url)
    ev = {"declared": found["declared"], "n_eids": len(found["eids"]),
          "n_titles": len(found["titles"]), "votes": {}, "checked": 0}

    # route 2/3 -- let the person's own papers vote for an AU-ID
    votes = collections.Counter()
    seen_names = {}
    for eid in found["eids"][:max_docs]:
        ev["checked"] += 1
        for aid, nm in _authors_of_eid(eid):
            if TL.compatible(name, nm):
                votes[aid] += 1
                seen_names.setdefault(aid, nm)
    if not votes:
        for t in found["titles"][:max_docs - ev["checked"] or 1]:
            ev["checked"] += 1
            for aid, nm in _authors_of_title(t):
                if TL.compatible(name, nm):
                    votes[aid] += 1
                    seen_names.setdefault(aid, nm)
    ev["votes"] = dict(votes)
    ev["names"] = seen_names

    declared = found["declared"]
    top = votes.most_common(1)[0][0] if votes else None

    if len(declared) == 1 and top and declared[0] == top:
        return dict(auid=top, tier="high:profile-declared+papers", ev=ev)
    if len(declared) == 1 and not votes:
        v = verify(declared[0], name)
        ev["verify"] = v
        if v["ok"] and v["aau"] > 0:
            return dict(auid=declared[0], tier="high:profile-declared+aau", ev=ev)
        if v["ok"]:
            return dict(auid=declared[0], tier="high:profile-declared", ev=ev)
        if v["total"] > 0:
            # the page links an ID filed under somebody else's surname
            return dict(auid=None, tier="review:declared-name-mismatch", ev=ev)
        return dict(auid=None, tier="review:declared-id-has-no-papers", ev=ev)
    if len(declared) == 1 and top and declared[0] != top:
        return dict(auid=None, tier="review:declared-vs-papers-disagree", ev=ev)
    if top and votes[top] >= 2:
        return dict(auid=top, tier="high:own-papers", ev=ev)
    if top:
        return dict(auid=top, tier="medium:own-paper-single", ev=ev)
    return dict(auid=None, tier="none:profile-has-no-scopus-link", ev=ev)
