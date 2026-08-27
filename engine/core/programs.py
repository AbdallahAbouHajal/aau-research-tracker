"""Which programme each person teaches on, from AAU's own college sites.

The main staff directory files people by college and nothing finer -- the
`department` column comes back empty for all 209 rows. But each college runs
its own subsite whose academic-staff page carries a **Program:** filter, and
that filter is server-side: asking for
`https://<college>.aau.ac.ae/en/academic-staff?staff_program=<id>` returns only
the staff on that programme. So the mapping exists, published by AAU, and this
reads it rather than inferring anything.

A person can teach on more than one programme -- Ayman Odeh is on both Software
Engineering and Computer Science -- so this is many-to-many, and programme
paper counts are whole-counted exactly as college counts are: a paper is
credited to every programme represented on it, and the totals therefore sum to
more than the paper count. The interface says so.

    python3 -m core.programs            # harvest and write data/programs.json
    python3 -m core.programs --show     # print what was harvested
"""
import json
import os
import re
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import census as X                                     # noqa: E402

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(ROOT, "data", "programs.json")

UA = {"User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/151 Safari/537.36"}

# subdomain -> the roster's own spelling of the college, so the two join
COLLEGES = [
    ("engineering", "College of Engineering"),
    ("pharmacy", "College of Pharmacy"),
    ("law", "College of Law"),
    ("education", "College of Education, Humanities and Social Sciences"),
    ("business", "College of Business"),
    ("communication", "College of Communication and Media"),
    ("dentistry", "College of Dentistry"),
    ("nursing", "College of Nursing"),
]

_OPT = re.compile(r'<option value="(\d+)"[^>]*>\s*([^<]+?)\s*</option>')
_SLUG = re.compile(r'/(?:[a-z\-]*academic-staff|staff)/(?:staff/)?'
                   r'([A-Za-z0-9\-\._]+)')
# The staff pages carry a jQuery call to /en/staff/getPrograms, which the slug
# pattern happily matched -- so every programme came back one person too many,
# including programmes with nobody on them, which read as 1. Anything that is
# an endpoint rather than a person is dropped here.
_NOT_A_PERSON = {"getprograms", "getprogram", "search", "index", "list",
                 "ajaxsubmit", "getdepartments", "view", "en", "ar"}


def _slugs(page):
    return sorted({s for s in _SLUG.findall(page)
                   if s.lower() not in _NOT_A_PERSON})


def _get(url):
    try:
        raw = X.http(url, headers=UA, tag="aau-college", timeout=40,
                     accept_404=True)
    except Exception:
        return ""
    return (raw or b"").decode("utf-8", "replace")


def _staff_url(host):
    """Each college names its own staff page: engineering uses
    /en/academic-staff, pharmacy uses /en/pharmacy-academic-staff. Read the
    link off the college's front page instead of guessing the path."""
    home = _get("https://%s.aau.ac.ae/en" % host)
    if not home:
        return ""
    for href, text in re.findall(r'href="([^"]+)"[^>]*>\s*([^<]{3,60}?)\s*<',
                                 home):
        if re.fullmatch(r"\s*Academic\s+Staff\s*", text, re.I):
            if href.startswith("/"):
                href = "https://%s.aau.ac.ae%s" % (host, href)
            return href
    return "https://%s.aau.ac.ae/en/academic-staff" % host


def _programs_on(host):
    """[(id, name)] from the college's own Program: filter."""
    url = _staff_url(host)
    page = _get(url) if url else ""
    if not page:
        return [], [], ""
    m = re.search(r'<select[^>]*name="staff_program"[^>]*>(.*?)</select>',
                  page, re.S)
    progs = _OPT.findall(m.group(1)) if m else []
    return progs, _slugs(page), url


def harvest(log=print, pause=0.4):
    """-> {colleges: {...}, programs: [...], by_slug: {slug: [program names]}}"""
    out = {"generated": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
           "colleges": {}, "programs": [], "by_slug": {}}
    for host, college in COLLEGES:
        progs, everyone, url = _programs_on(host)
        if not progs and not everyone:
            log("  %-14s no page" % host)
            continue
        log("  %-14s %d programmes, %d staff listed"
            % (host, len(progs), len(everyone)))
        # AAU runs two campuses and each college page can be filtered by
        # them. Two extra requests per college gives every person a campus,
        # which is cheaper and more useful than asking per programme.
        sep = "&" if "?" in url else "?"
        campuses = {}
        for cid, cname in (("0", "Al Ain"), ("1", "Abu Dhabi")):
            for sl in _slugs(_get("%s%scampus_id=%s" % (url, sep, cid))):
                campuses.setdefault(sl, []).append(cname)
        out.setdefault("campus", {}).update(campuses)
        out["colleges"][college] = {"host": host, "url": url,
                                    "staff": everyone, "programs": [],
                                    "al_ain": sum(1 for v in campuses.values()
                                                  if "Al Ain" in v),
                                    "abu_dhabi": sum(1 for v in campuses.values()
                                                     if "Abu Dhabi" in v)}
        log("      %-58s %s" % ("(campus split)",
            "%d Al Ain / %d Abu Dhabi"
            % (out["colleges"][college]["al_ain"],
               out["colleges"][college]["abu_dhabi"])))
        for pid, name in progs:
            sep = "&" if "?" in url else "?"
            page = _get("%s%sstaff_program=%s" % (url, sep, pid))
            slugs = _slugs(page)
            # An empty answer means the filter returned nobody, which is a
            # real answer for a new programme -- not a failure to record.
            rec = {"id": pid, "name": name, "college": college,
                   "staff": slugs}
            out["programs"].append(rec)
            out["colleges"][college]["programs"].append(name)
            for s in slugs:
                out["by_slug"].setdefault(s, []).append(name)
            log("      %-58s %d" % (name[:58], len(slugs)))
            time.sleep(pause)
    return out


def load():
    if not os.path.exists(OUT):
        return None
    try:
        return json.load(open(OUT, encoding="utf-8"))
    except Exception:
        return None


def main():
    if "--show" in sys.argv:
        b = load()
        if not b:
            print("nothing harvested yet"); return
        print("%d programmes across %d colleges, %d people mapped"
              % (len(b["programs"]), len(b["colleges"]), len(b["by_slug"])))
        for p in b["programs"]:
            print("  %-52s %-34s %d" % (p["name"][:52], p["college"][:34],
                                        len(p["staff"])))
        return
    b = harvest()
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    json.dump(b, open(OUT, "w", encoding="utf-8"), ensure_ascii=False,
              separators=(",", ":"))
    print("wrote %s: %d programmes, %d people mapped"
          % (OUT, len(b["programs"]), len(b["by_slug"])))


if __name__ == "__main__":
    main()
