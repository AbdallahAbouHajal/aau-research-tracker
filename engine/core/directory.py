"""AAU's own staff directory -- which publishes each person's Scopus author id.

The directory at aau.ac.ae/en/directory renders server-side and every person's
card carries, in its markup, a link of the form

    https://www.scopus.com/authid/detail.uri?authorId=36463516700

That is the answer to the question this project has been guessing at from the
start. Name matching gets "Mohd Molham Sakkal" wrong ten different ways and
put a natural-products chemist at the University of Nizwa on AAU's dentistry
staff; the university states the id outright. Where the directory gives one it
is taken as fact and no matcher is consulted.

    python3 -m core.directory           # harvest, write data/directory_ids.json
    python3 -m core.directory --show
"""
import collections
import json
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import census as X                                      # noqa: E402

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(ROOT, "data", "directory_ids.json")

UA = {"User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/151 Safari/537.36"}

BASE = "https://aau.ac.ae/en/directory"

# `list` codes read off the directory's own college dropdown, with the roster's
# spelling of each college so the two join without a mapping table.
COLLEGES = [
    ("1", "College of Business"),
    ("2", "College of Engineering"),
    ("3", "College of Law"),
    ("4", "College of Pharmacy"),
    ("5", "College of Education, Humanities and Social Sciences"),
    ("6", "College of Communication and Media"),
    ("33", "College of Dentistry"),
    ("34", "College of Nursing"),
]

_STAFF = re.compile(r'href="https://aau\.ac\.ae/en/staff/([A-Za-z0-9\-\._]+)"')
_SCOPUS = re.compile(r'authorId=(\d{6,})')
_NAME = re.compile(r'<h[34][^>]*>\s*(?:<a[^>]*>)?\s*([^<]{3,90}?)\s*(?:</a>)?\s*</h[34]>')


def _get(url):
    try:
        return X.http(url, headers=UA, tag="aau-directory", timeout=45,
                      accept_404=True).decode("utf-8", "replace")
    except Exception:
        return ""


def _people(html, college):
    """Pair each staff card with the Scopus id printed inside it.

    The id sits in the same card as the profile link, a few hundred bytes
    after it, so the card is bounded by the NEXT profile link. Searching the
    whole page instead would hand one person their neighbour's id.
    """
    out = []
    hits = list(_STAFF.finditer(html))
    for i, m in enumerate(hits):
        slug = m.group(1)
        end = hits[i + 1].start() if i + 1 < len(hits) else len(html)
        card = html[m.start():end]
        if len(card) > 4000:                 # not a card; a stray link
            card = card[:4000]
        sid = _SCOPUS.search(card)
        # The name sits just ABOVE the social links, so look back a little.
        back = html[max(0, m.start() - 2600):m.start()]
        names = _NAME.findall(back)
        name = names[-1].strip() if names else ""
        out.append({
            "slug": slug,
            "name": X.clean_name(name) if hasattr(X, "clean_name") else name,
            "college": college,
            "scopus_auid": sid.group(1) if sid else "",
            "profile_url": "https://aau.ac.ae/en/staff/" + slug,
        })
    return out


_PROG_SELECT = re.compile(r'<select[^>]*name="program"[^>]*>(.*?)</select>', re.S)
_OPTION = re.compile(r'<option[^>]*value="(\d+)"[^>]*>\s*([^<]+?)\s*</option>')


def programs_on(code, html=None, log=print):
    """[(id, name)] -- the programme filter the directory renders for a college."""
    if html is None:
        html = _get("%s?keyword=&campus=3&list=%s" % (BASE, code))
    m = _PROG_SELECT.search(html or "")
    if not m:
        return []
    return [(v, t) for v, t in _OPTION.findall(m.group(1))
            if v != "0" and t.strip().lower() != "program"]


def harvest_programs(log=print):
    """Which programme each person is filed under, from the DIRECTORY.

    DO NOT USE for programme membership. Kept only so nobody re-walks this.

    The directory's Program dropdown does not filter server-side. Measured:
    `?list=4&program=47` and `?list=4&program=5` come back SIX BYTES apart --
    the difference is which <option> carries `selected` -- and both list all
    43 Pharmacy staff in the same order. Across the six colleges running more
    than one programme, every programme returns an identical set. The
    filtering a browser shows is done by the page's own JavaScript after it
    loads; the cards carry no programme attribute for a fetch to read,
    /en/api/getProgram answers [], and the filter form is a plain GET with no
    action.

    core/programs.py harvests the COLLEGE SUBSITES instead, whose
    `staff_program=` filter is genuinely server-side: Pharmacy comes back as
    21 / 4 / 4 / 15 for its four programmes, and its Nutrition and Dietetics
    four are exactly the people the directory shows a human. That is the
    source of programme membership, and this function is not.
    """
    out = {"colleges": {}, "programs": [], "by_slug": {}}
    for code, college in COLLEGES:
        page = _get("%s?keyword=&campus=3&list=%s" % (BASE, code))
        progs = programs_on(code, page, log)
        if not progs:
            log("  %-52s no programme filter" % college)
            continue
        out["colleges"][college] = {"code": code,
                                    "programs": [t for _, t in progs]}
        log("  %-52s %d programmes" % (college, len(progs)))
        for pid, name in progs:
            ph = _get("%s?keyword=&campus=3&list=%s&program=%s"
                      % (BASE, code, pid))
            slugs = sorted({m.group(1) for m in _STAFF.finditer(ph or "")})
            out["programs"].append({"id": pid, "name": name,
                                    "college": college, "staff": slugs})
            for sl in slugs:
                out["by_slug"].setdefault(sl.lower(), []).append(name)
            log("      %-56s %d" % (name[:56], len(slugs)))
    return out


def verify(rows, log=print):
    """Check each published id actually resolves, and record what it holds.

    AAU's own statement outranks any matcher -- but it is typed by a person.
    Shirin AlAmoor's card carries 5861206300, ten digits, which returns
    nothing at all: a dropped digit. So an id is rejected only when Scopus has
    no such author, never merely because it has few AAU-tagged papers. That
    second rule matters: the directory's id for Niazur Rahman holds 15 papers
    and none tagged to AAU, while the id my matcher guessed holds 190 in
    natural-products chemistry at the University of Nizwa. Fewer AAU papers,
    and still obviously the right man.
    """
    import census as _X
    ok = bad = 0
    for r in rows:
        aid = r.get("scopus_auid")
        if not aid:
            continue
        try:
            q = _X.scopus_get("/content/search/scopus",
                              {"query": "AU-ID(%s)" % aid, "count": 1,
                               "sort": "+eid"})
            n = int(q["search-results"].get("opensearch:totalResults") or 0)
        except Exception:
            r["verified"] = None            # could not ask; keep the id
            continue
        r["papers_total"] = n
        r["verified"] = n > 0
        if n:
            ok += 1
        else:
            bad += 1
            log("      %-30s id %s resolves to nothing -- dropped"
                % (r.get("name") or r["slug"], aid))
            r["scopus_auid_rejected"] = aid
            r["scopus_auid"] = ""
    log("  verified %d ids, dropped %d that resolve to no author" % (ok, bad))
    return rows


def harvest(log=print):
    seen = {}
    for code, college in COLLEGES:
        html = _get("%s?keyword=&campus=3&list=%s" % (BASE, code))
        if not html:
            log("  %-52s no page" % college)
            continue
        rows = _people(html, college)
        with_id = sum(1 for r in rows if r["scopus_auid"])
        log("  %-52s %3d people, %3d with a Scopus id"
            % (college, len(rows), with_id))
        for r in rows:
            # A person listed under two colleges keeps the first, but never
            # loses an id to a listing that lacks one.
            cur = seen.get(r["slug"])
            if cur is None:
                seen[r["slug"]] = r
            elif not cur["scopus_auid"] and r["scopus_auid"]:
                cur["scopus_auid"] = r["scopus_auid"]
    return list(seen.values())


# A browser pass over the same directory, exported by hand, which carries what
# a fetch cannot reach: the programme list per person, and a Google Scholar id
# beside the Scopus one. 209 people, 143 Scopus ids, 145 Scholar ids.
_PEOPLE_CSV = os.path.join(ROOT, "data", "directory_people.csv")
_DEGREE_RE = re.compile(
    r"\s*,?\s*\b(Ph\.?\s?D|M\.?\s?Sc|MBA|MD|DDS|MA|M\.A)\.?\s*$", re.I)


def merge_people_csv(rows, roster, log=print):
    """Fold the browser export into the scraped rows, keyed by roster name.

    The CSV has no slug, so people are matched by name against the roster and
    the slug taken from there. Any id the scrape did not already hold is
    verified before it is accepted -- which is how the CSV's own copy of
    Shirin AlAmoor's ten-digit id, the same dropped digit AAU prints on her
    card, is refused for the second time.
    """
    if not os.path.exists(_PEOPLE_CSV) or not roster:
        return rows
    import csv as _csv
    import translit as _TL
    by_name = {X.name_key(p.get("name", "")): p for p in roster}

    def _find(n):
        p = by_name.get(X.name_key(n))
        if p:
            return p
        for q in roster:
            if _TL.compatible(q.get("name", ""), n) or _TL.compatible(n, q.get("name", "")):
                return q
        return None

    by_slug = {r["slug"].lower(): r for r in rows if r.get("slug")}
    added = scholars = refused = 0
    with open(_PEOPLE_CSV, newline="", encoding="utf-8-sig") as fh:
        for row in _csv.DictReader(fh):
            person = _find(_DEGREE_RE.sub("", (row.get("name") or "").strip()).strip())
            u = (person or {}).get("profile_url") or ""
            if "/staff/" not in u:
                continue
            sl = u.rstrip("/").rsplit("/", 1)[-1]
            rec = by_slug.get(sl.lower())
            if rec is None:
                rec = {"slug": sl, "name": person.get("name") or "",
                       "college": person.get("college") or "",
                       "scopus_auid": "",
                       "profile_url": u}
                rows.append(rec)
                by_slug[sl.lower()] = rec
            gs = (row.get("google_scholar_id") or "").strip()
            if gs and not rec.get("google_scholar_id"):
                rec["google_scholar_id"] = gs
                scholars += 1
            sid = (row.get("scopus_id") or "").strip()
            if not sid or rec.get("scopus_auid") == sid:
                continue
            if sid == rec.get("scopus_auid_rejected"):
                refused += 1
                continue
            try:
                q = X.scopus_get("/content/search/scopus",
                                 {"query": "AU-ID(%s)" % sid, "count": 1,
                                  "sort": "+eid"})
                n = int(q["search-results"].get("opensearch:totalResults") or 0)
            except Exception:
                continue
            if not n:
                rec["scopus_auid_rejected"] = sid
                refused += 1
                log("      %-30s csv id %s resolves to nothing -- refused"
                    % (rec.get("name") or sl, sid))
                continue
            if not rec.get("scopus_auid"):
                rec["scopus_auid"] = sid
                added += 1
                log("      %-30s + %s (%d papers)" % (rec.get("name") or sl, sid, n))
    log("  browser export: %d ids added, %d Scholar ids, %d refused"
        % (added, scholars, refused))
    return rows


def load():
    if not os.path.exists(OUT):
        return {}
    try:
        blob = json.load(open(OUT, encoding="utf-8"))
    except Exception:
        return {}
    return {r["slug"].lower(): r for r in (blob.get("people") or [])
            if r.get("slug")}


def main():
    if "--show" in sys.argv:
        b = load()
        print("%d people, %d with a Scopus id"
              % (len(b), sum(1 for r in b.values() if r.get("scopus_auid"))))
        return
    if "--programs" in sys.argv:
        import time as _t
        blob = harvest_programs()
        blob["generated"] = _t.strftime("%Y-%m-%dT%H:%M:%SZ", _t.gmtime())
        path = os.path.join(ROOT, "data", "directory_programs.json")
        json.dump(blob, open(path, "w", encoding="utf-8"),
                  ensure_ascii=False, separators=(",", ":"))
        print("wrote %s: %d programmes, %d people placed"
              % (path, len(blob["programs"]), len(blob["by_slug"])))
        return

    rows = harvest()
    if "--no-verify" not in sys.argv:
        rows = verify(rows)
    try:
        import faculty as _FAC
        rows = merge_people_csv(rows, (_FAC.load() or {}).get("people") or [])
    except Exception as exc:
        print("  browser export not merged: %s" % str(exc)[:80])
    ids = sum(1 for r in rows if r["scopus_auid"])
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    json.dump({"generated": __import__("time").strftime("%Y-%m-%dT%H:%M:%SZ",
                                                        __import__("time").gmtime()),
               "people": rows}, open(OUT, "w", encoding="utf-8"),
              ensure_ascii=False, indent=1)
    print("wrote %s: %d people, %d carry a Scopus id AAU published itself"
          % (OUT, len(rows), ids))


if __name__ == "__main__":
    main()
