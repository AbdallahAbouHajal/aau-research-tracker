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
    rows = harvest()
    if "--no-verify" not in sys.argv:
        rows = verify(rows)
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
