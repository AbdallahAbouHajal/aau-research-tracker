"""Resolve a Scopus AU-ID from the person's own publication list.

The user's idea, and it is stronger than every name-based tier.

AAU college profile pages list a staff member's publications by title. A title
is very nearly a unique key, so searching Scopus for it returns one paper --
and that paper's author list is roughly five names instead of the 9,771
AU-IDs in the export. Matching a name inside five candidates is a different
problem from matching it inside ten thousand.

That is why this beats the name tiers: it does not make the name comparison
better, it makes the haystack smaller. Muhammad Sarfraz has nine candidate
AU-IDs on name alone; on one of his own papers he has one.
"""
import html
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import census as X
import translit as TL

UA = {"User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/151 Safari/537.36"}
_PUB = re.compile(r'([A-Z][^|]{25,180}?)\s+Published in\s*:')
_LEAD = re.compile(r'^.*?(?:Full-text Available|Article|Conference Paper|Chapter)\s+')


def titles(profile_url):
    """Publication titles printed on an AAU college profile page."""
    if not profile_url or "/staff/" not in profile_url:
        return []
    try:
        raw = X.http(profile_url, headers=UA, tag="staff", timeout=40,
                     accept_404=True).decode("utf-8", "replace")
    except Exception:
        return []
    if not raw:
        return []
    t = re.sub(r"<script.*?</script>|<style.*?</style>", " ", raw, flags=re.S)
    t = html.unescape(re.sub(r"<[^>]+>", " ", t))
    t = re.sub(r"\s+", " ", t)
    out, seen = [], set()
    for m in _PUB.finditer(t):
        s = _LEAD.sub("", m.group(1).strip())
        if 20 < len(s) < 190 and s.lower() not in seen:
            seen.add(s.lower())
            out.append(s)
    return out


def _authors_of(title):
    """(auid, name) for every author on the paper with this exact title."""
    q = 'TITLE("%s")' % title[:120].replace('"', " ").replace("(", " ").replace(")", " ")
    try:
        r = X.scopus_get("/content/search/scopus",
                         {"query": q, "count": 5})["search-results"]
    except Exception:
        return []
    n = int(r.get("opensearch:totalResults", 0) or 0)
    if not n or n > 3:            # ambiguous title -- skip it
        return []
    eid = (r.get("entry") or [{}])[0].get("eid")
    if not eid:
        return []
    try:
        d = X.scopus_get("/content/abstract/eid/" + eid, {"view": "META"})
        cr = (d.get("abstracts-retrieval-response") or {}).get(
            "coredata", {}).get("dc:creator")
    except Exception:
        return []
    lst = cr.get("author") if isinstance(cr, dict) else cr
    if isinstance(lst, dict):
        lst = [lst]
    out = []
    for a in (lst or []):
        pn = a.get("preferred-name") or {}
        nm = pn.get("ce:indexed-name") or a.get("$") or ""
        aid = a.get("@auid") or ""
        if nm:
            out.append((aid, nm))
    return out


def resolve(person, export_index=None, max_titles=4):
    """-> (auid|None, evidence). Uses the person's own papers as the haystack."""
    for title in titles(person.get("profile_url", ""))[:max_titles]:
        cands = _authors_of(title)
        if not cands:
            continue
        hits = [(aid, nm) for aid, nm in cands
                if aid and (X.name_key(nm) == X.name_key(person["name"])
                            or X.initial_keys(nm) & X.initial_keys(person["name"])
                            or TL.match(nm, person["name"]))]
        if len(hits) == 1:
            return hits[0][0], {"via": "own publication",
                                "title": title[:120], "matched_as": hits[0][1]}
        # Scopus META returns only the first author on some records; if that
        # single name is our person, it is still a clean identification.
        if len(cands) == 1 and hits:
            return hits[0][0], {"via": "own publication (sole author listed)",
                                "title": title[:120], "matched_as": hits[0][1]}
    return None, None
