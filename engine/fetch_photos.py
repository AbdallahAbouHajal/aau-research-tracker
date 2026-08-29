#!/usr/bin/env python3
"""Collect the staff portraits AAU already publishes, and file them by slug.

Every roster person carries a `profile_url` like
`https://aau.ac.ae/en/staff/qutaibah-althebyan`, and every college runs a staff
listing whose cards carry that person's photograph. So the join needs no
matching at all: the slug in the URL the roster already holds IS the key. That
is why this is worth doing -- name matching would have been guesswork, and this
is AAU's own statement of who is who.

Two routes, cheapest first:

  1. Eight college listing pages, one request each, giving ~156 portraits.
  2. For anyone the listings miss, that person's own staff page.

The photograph on a staff page is identifiable: AAU's thumbnailer writes
`<base>_<W>_<H>_t_t_f.jpg` for uploaded portraits and `_t_t_t.png` for the
site's own menu artwork, so the suffix separates a person from a banner.

Stored at 192px WebP -- 3.8KB each, 0.59MB for all of them, against 2.7MB if
the 340px originals were kept. 192 covers a 96px avatar on a 2x screen, which
is the largest this interface draws one.

    python3 fetch_photos.py            # harvest, skipping what is already here
    python3 fetch_photos.py --force    # re-fetch everything
    python3 fetch_photos.py --check    # report coverage, write nothing
"""
import io
import json
import os
import re
import sys
import time
import urllib.request

ROOT = os.path.dirname(os.path.abspath(__file__))
SITE = os.path.dirname(ROOT)
OUT_DIR = os.path.join(SITE, "docs", "photos")
MANIFEST = os.path.join(SITE, "docs", "data", "photos.json")
ROSTER = os.path.join(ROOT, "data", "roster.json")

UA = {"User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                    "AppleWebKit/537.36 (KHTML, like Gecko) "
                    "Chrome/151 Safari/537.36"}

HOSTS = ["engineering", "pharmacy", "law", "education", "business",
         "communication", "dentistry", "nursing"]

SIZE = 192
# `_t_t_f.jpg` is an uploaded portrait; `_t_t_t.png` is site artwork. Without
# this the header's six menu images are harvested as though they were people.
PORTRAIT = re.compile(r'(/uploads/[^"\']*?thumbs/[^"\']*?_t_t_f\.(?:jpg|jpeg|png))',
                      re.I)


def get(url, binary=False, tries=3):
    for i in range(tries):
        try:
            req = urllib.request.Request(url, headers=UA)
            raw = urllib.request.urlopen(req, timeout=45).read()
            return raw if binary else raw.decode("utf-8", "replace")
        except Exception:
            if i == tries - 1:
                return b"" if binary else ""
            time.sleep(1.5 * (i + 1))
    return b"" if binary else ""


def staff_url(host):
    """Each college names its own staff page, so read the link rather than
    guess the path -- pharmacy uses /en/pharmacy-academic-staff."""
    home = get("https://%s.aau.ac.ae/en" % host)
    for href, text in re.findall(r'href="([^"]+)"[^>]*>\s*([^<]{3,60}?)\s*<',
                                 home):
        if re.fullmatch(r"\s*Academic\s+Staff\s*", text, re.I):
            if href.startswith("/"):
                return "https://%s.aau.ac.ae%s" % (host, href)
            return href
    return "https://%s.aau.ac.ae/en/academic-staff" % host


def from_listings(log=print):
    """{slug: image url} from the eight college listings."""
    out = {}
    for host in HOSTS:
        page = get(staff_url(host))
        if not page:
            log("  %-14s no page" % host)
            continue
        n = 0
        # One card per `item white-box`; inside it the <img> comes BEFORE the
        # link, so the block has to be split rather than pattern-matched
        # across the pair.
        for block in page.split('class="item white-box"')[1:]:
            block = block[:2500]
            img = PORTRAIT.search(block)
            slug = re.search(r'/staff/([A-Za-z0-9._-]+)', block)
            if img and slug and slug.group(1) not in out:
                out[slug.group(1)] = img.group(1)
                n += 1
        log("  %-14s %3d portraits" % (host, n))
        time.sleep(0.3)
    return out


def from_own_page(slug):
    """The listings miss a few people who still have a staff page."""
    page = get("https://aau.ac.ae/en/staff/%s" % slug)
    if not page:
        return ""
    m = PORTRAIT.search(page)
    return m.group(1) if m else ""


def absolute(u):
    return u if u.startswith("http") else "https://aau.ac.ae" + u


def save(url, slug, force=False, log=print):
    """-> filename written, or '' """
    name = "%s.webp" % re.sub(r"[^A-Za-z0-9._-]", "-", slug)
    path = os.path.join(OUT_DIR, name)
    if os.path.exists(path) and not force:
        return name
    raw = get(absolute(url), binary=True)
    if not raw or len(raw) < 500:
        return ""
    try:
        from PIL import Image
        im = Image.open(io.BytesIO(raw)).convert("RGB")
        # Square-crop from the centre before scaling: a few portraits are not
        # square, and letting the browser letterbox them makes one face float
        # in a grid of faces that all sit still.
        w, h = im.size
        s = min(w, h)
        im = im.crop(((w - s) // 2, (h - s) // 2, (w - s) // 2 + s,
                      (h - s) // 2 + s)).resize((SIZE, SIZE), Image.LANCZOS)
        im.save(path, "WEBP", quality=82, method=6)
    except ImportError:
        log("  Pillow is not installed: pip3 install pillow")
        raise
    except Exception as exc:
        log("  %-28s could not decode (%s)" % (slug, str(exc)[:40]))
        return ""
    return name


def roster_slugs():
    """[(slug, name, is_academic)] -- the roster's own statement of identity."""
    blob = json.load(open(ROSTER, encoding="utf-8"))
    out = []
    for p in blob.get("people") or []:
        u = (p.get("profile_url") or "").rstrip("/")
        out.append((u.rsplit("/", 1)[-1] if u else "",
                    p.get("name") or "", bool(p.get("is_academic"))))
    return out


def _norm(s):
    return re.sub(r"[^a-z]", "", (s or "").lower())


def match_by_name(people, found, log=print):
    """Five roster people carry no profile_url at all -- they were added by
    hand rather than read from the directory -- so the slug join cannot reach
    them. Two of them DO have a directory card; their photograph is simply
    unreachable by the key everyone else uses.

    This is the one place a name decides anything, so it is deliberately
    narrow: only people with no profile_url, only an exact match on the
    normalised full name or on first-plus-last, and the result is recorded
    separately so the manifest never presents a guess as AAU's own statement.
    """
    idx = {}
    for slug in found:
        idx.setdefault(_norm(slug.replace("-", " ").replace(".", " ")), slug)
    got = {}
    for slug, name, _acad in people:
        if slug or not name:
            continue
        hit = idx.get(_norm(name))
        if not hit:
            parts = [w for w in re.split(r"[^A-Za-z]+", name) if len(w) > 1]
            if len(parts) >= 2:
                hit = idx.get(_norm(parts[0] + parts[-1]))
        if hit:
            got[hit] = name
            log("  %-30s matched on name to %s" % (name[:30], hit))
    return got


def load_manifest():
    try:
        return json.load(open(MANIFEST, encoding="utf-8"))
    except Exception:
        return {}


def main():
    force = "--force" in sys.argv
    check = "--check" in sys.argv
    people = roster_slugs()
    acad = [p for p in people if p[2]]
    known = set(s for s, _, _ in people if s)

    print("== portraits AAU publishes")
    found = from_listings()
    print("  %d portraits across the listings" % len(found))

    # Anyone on the roster the listings missed, asked for directly. Only for
    # people the roster names, never a sweep of the whole site.
    gaps = sorted(s for s in known if s and s not in found)
    if gaps:
        print("== %d roster people the listings missed, asked directly" % len(gaps))
        for s in gaps:
            u = from_own_page(s)
            if u:
                found[s] = u
                print("  %-30s found on their own page" % s[:30])
            time.sleep(0.3)

    wanted = {s: u for s, u in found.items() if s in known}
    print("== %d portraits belong to someone on the roster" % len(wanted))

    by_name = match_by_name(people, found)
    if by_name:
        print("== %d more reached by name, having no profile_url" % len(by_name))
        for s in by_name:
            wanted[s] = found[s]

    prev = load_manifest()
    prev_n = len((prev.get("photos") or {}))
    if check:
        cov = sum(1 for s, _, a in acad if s in wanted)
        print("coverage: %d of %d academics (%.0f%%); manifest holds %d"
              % (cov, len(acad), 100.0 * cov / max(1, len(acad)), prev_n))
        return

    os.makedirs(OUT_DIR, exist_ok=True)
    photos, failed = {}, []
    for i, (slug, url) in enumerate(sorted(wanted.items()), 1):
        name = save(url, slug, force=force)
        if name:
            photos[slug] = name
        else:
            failed.append(slug)
        if i % 25 == 0:
            print("  %d/%d" % (i, len(wanted)))

    # The same guard fill_institutions carries: a transient failure at AAU's
    # end must never quietly replace a good manifest with a thin one.
    if prev_n and len(photos) < prev_n * 0.9:
        print("REFUSING to publish %d portraits over the %d already there -- "
              "that is a drop, not an update. Nothing was written."
              % (len(photos), prev_n))
        raise SystemExit(1)

    cov = sum(1 for s, _, a in acad if s in photos)
    # Anyone reached by name rather than by the roster's own link counts too,
    # but is named so the provenance stays visible.
    cov += sum(1 for s in by_name if s in photos)
    # The page joins on the census's own key, which is the DIRECTORY slug only
    # where a profile_url exists and a name-derived slug otherwise -- so a map
    # keyed by name is published beside the slug map. Exactly the shape
    # `ros_progs` in viewmodel.py already uses for programmes, and for the same
    # reason: a slug is missing wherever the census knows a person the
    # directory scrape did not.
    by_person = {}
    for slug, name in by_name.items():
        if slug in photos:
            by_person[name] = photos[slug]
    for slug, name, _a in people:
        if slug and slug in photos:
            by_person[name] = photos[slug]

    blob = {"generated": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
            "count": len(photos),
            "by_name": by_person,
            "matched_by_name": sorted(by_name),
            "academics_covered": cov,
            "academics_total": len(acad),
            "size": SIZE,
            "source": "https://aau.ac.ae -- each college's own academic-staff "
                      "listing, joined on the profile_url the roster already "
                      "holds",
            "photos": photos}
    os.makedirs(os.path.dirname(MANIFEST), exist_ok=True)
    with open(MANIFEST, "w", encoding="utf-8") as fh:
        json.dump(blob, fh, ensure_ascii=False, separators=(",", ":"))

    total = sum(os.path.getsize(os.path.join(OUT_DIR, f))
                for f in os.listdir(OUT_DIR) if f.endswith(".webp"))
    print("\nwrote %d portraits (%.2f MB) and %s"
          % (len(photos), total / 1e6, os.path.relpath(MANIFEST, SITE)))
    print("covers %d of %d academics (%.0f%%)"
          % (cov, len(acad), 100.0 * cov / max(1, len(acad))))
    if failed:
        print("could not fetch: %s" % ", ".join(failed[:8]))


if __name__ == "__main__":
    main()
