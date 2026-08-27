"""Cache-aware transport. Forked from the census on purpose.

The census caches by URL hash with NO expiry -- correct for a one-shot study,
fatal for a weekly job. Next Monday's

    AF-ID(60105817) AND PUBYEAR IS 2026 &count=25&start=0&sort=+eid

is byte-identical to last Monday's, so it would return last Monday's answer
forever. The delta would be permanently empty and nothing would look broken.
That single fact is why this file exists.

Three tiers, because the right lifetime differs by what is being asked:

  A  volatile  Scopus searches -- the answer changes as Scopus indexes.
                Cached per RUN only, so a re-run inside one job is free but
                next week always refetches.
  B  durable   A published paper's author list does not change. Reuses the
                census's warm 168 MB cache; 1,330 papers are already in it.
  C  ttl       OpenAlex author metrics (h-index) drift slowly. 7 days.
"""
import hashlib
import json
import os
import sys
import time
import urllib.parse
import urllib.request

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import census as X

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
VOLATILE = os.path.join(ROOT, "data", "cache_runs")
TTLDIR = os.path.join(ROOT, "data", "cache_ttl")
for d in (VOLATILE, TTLDIR):
    os.makedirs(d, exist_ok=True)

TTL_DAYS = 7
STATS = {"hit": 0, "miss": 0, "volatile_hit": 0}


def _path(base, url, tag=""):
    h = hashlib.sha256((tag + "|" + url).encode()).hexdigest()
    sub = os.path.join(base, h[:2])
    os.makedirs(sub, exist_ok=True)
    return os.path.join(sub, h + ".json")


def _read(path, max_age_s=None):
    if not os.path.exists(path):
        return None
    if max_age_s is not None and (time.time() - os.path.getmtime(path)) > max_age_s:
        return None
    try:
        with open(path) as fh:
            return json.load(fh)["body"]
    except Exception:
        return None


def _write(path, body):
    tmp = path + ".tmp"
    with open(tmp, "w") as fh:
        json.dump({"body": body, "at": time.time()}, fh)
    os.replace(tmp, path)


def _get(url, headers=None, timeout=60, tries=4):
    last = None
    for i in range(tries):
        try:
            req = urllib.request.Request(url, headers=headers or {})
            return urllib.request.urlopen(req, timeout=timeout).read().decode(
                "utf-8", "replace")
        except Exception as exc:
            last = exc
            code = getattr(exc, "code", None)
            if code in (400, 401, 403, 404) and i >= 1:
                break
            time.sleep(1.2 * (i + 1))
    raise RuntimeError("GET failed %s :: %s" % (url, str(last)[:180]))


# ---------------------------------------------------------------- tier A
_ki = [0]


def scopus(path, params, run_id="adhoc"):
    """Scopus Search. Cached only inside one run, so weeks never collide."""
    url = "https://api.elsevier.com" + path + "?" + urllib.parse.urlencode(params)
    cp = _path(os.path.join(VOLATILE, str(run_id)), url, "scopus")
    hit = _read(cp)
    if hit is not None:
        STATS["volatile_hit"] += 1
        return json.loads(hit)

    keys = X.scopus_keys()
    last = None
    for _ in range(min(len(keys), 8)):
        k = keys[_ki[0] % len(keys)]
        _ki[0] += 1
        try:
            body = _get(url, {"X-ELS-APIKey": k, "Accept": "application/json",
                              "User-Agent": "Scifiniti-AAU-Tracker/1.0"})
            _write(cp, body)
            STATS["miss"] += 1
            time.sleep(0.12)
            return json.loads(body)
        except Exception as exc:
            last = exc
            if getattr(exc, "code", None) in (401, 403, 429):
                time.sleep(0.35)
                continue
            if getattr(exc, "code", None) == 400:
                break
    raise RuntimeError("scopus failed %s :: %s" % (url, str(last)[:180]))


# ---------------------------------------------------------------- tier B
def openalex_work(doi_or_id):
    """A published work's author list is immutable -> the census cache."""
    ident = doi_or_id if doi_or_id.startswith("http") else "doi:" + doi_or_id
    return X.openalex("/works/" + ident.rsplit("/", 1)[-1]
                      if ident.startswith("http") else "/works/" + ident)


# ---------------------------------------------------------------- tier C
def openalex_author(author_id, ttl_days=TTL_DAYS):
    """h-index and citations drift; refresh weekly, not never."""
    aid = author_id.rsplit("/", 1)[-1]
    url = "https://api.openalex.org/authors/%s?mailto=%s" % (aid, X.C.MAILTO)
    cp = _path(TTLDIR, url, "oa-author")
    hit = _read(cp, ttl_days * 86400)
    if hit is not None:
        STATS["hit"] += 1
        return json.loads(hit)
    body = _get(url, {"User-Agent": "Scifiniti-AAU-Tracker/1.0"})
    _write(cp, body)
    STATS["miss"] += 1
    time.sleep(0.12)
    return json.loads(body)


def gc(keep_runs=4):
    """Drop volatile caches beyond the last few runs."""
    if not os.path.isdir(VOLATILE):
        return 0
    runs = sorted(d for d in os.listdir(VOLATILE)
                  if os.path.isdir(os.path.join(VOLATILE, d)))
    dropped = 0
    for d in runs[:-keep_runs] if len(runs) > keep_runs else []:
        import shutil
        shutil.rmtree(os.path.join(VOLATILE, d), ignore_errors=True)
        dropped += 1
    return dropped
