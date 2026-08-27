"""Shared library for the AAU Author Census.

Cache-first HTTP, runtime Scopus key loading + rotation, name/DOI normalisers,
and the AAU affiliation badge rule.
"""
import hashlib, json, os, re, sys, time, unicodedata
import urllib.parse
import urllib.request
from functools import lru_cache

# Vendored from the AAU Author Census so the engine can run anywhere --
# a GitHub Actions runner has no ~/Downloads/AAU_Author_Census. The rule that
# decides who counts as AAU still lives in ONE file; this is that file.
ROOT = os.environ.get("AAU_ROOT") or os.path.dirname(
    os.path.dirname(os.path.abspath(__file__)))
CACHE = os.environ.get("AAU_CACHE") or os.path.join(ROOT, "cache")
DATA = os.environ.get("AAU_DATA") or os.path.join(ROOT, "data")
OUT = os.path.join(ROOT, "out")
STATE = os.path.join(ROOT, "state.json")
MAILTO = "abdallah.abouhajal@scifiniti.com"
UA = "Scifiniti-AAU-Census/1.0 (mailto:%s)" % MAILTO

AAU_ROR = "https://ror.org/023abrt21"
AAU_AFID = "60105817"
AAU_OPENALEX = "https://openalex.org/I161913731"

for _d in (CACHE, DATA, OUT):
    os.makedirs(_d, exist_ok=True)


# ---------------------------------------------------------------- state
def load_state():
    if os.path.exists(STATE):
        with open(STATE) as fh:
            return json.load(fh)
    return {"phases": {}, "counts": {}}


def save_state(st):
    tmp = STATE + ".tmp"
    with open(tmp, "w") as fh:
        json.dump(st, fh, indent=2, sort_keys=True)
    os.replace(tmp, STATE)


def mark_phase(name, **counts):
    st = load_state()
    st["phases"][name] = "done"
    st.setdefault("counts", {}).update(counts)
    save_state(st)
    return st


# ---------------------------------------------------------------- scopus keys
_KEYSRC = ("/Users/abdallahabouhajal/Desktop/Scifiniti/Codes/"
           "Reveiwers Valdiation/scopus_reviewer_app.py")
_KEYFILE = os.environ.get("SCOPUS_KEYS_FILE")
_keys_cache = None


def scopus_keys():
    """Read the 44 keys out of scopus_reviewer_app.py at runtime.

    Deliberately not re-hardcoded here: the pool is maintained in one place
    and copied into ~15 files already. Same pattern as Field Analysis/engine/verify.py.
    """
    global _keys_cache
    if _keys_cache is None and _KEYFILE and os.path.exists(_KEYFILE):
        # CI path: a JSON array written from the SCOPUS_KEYS secret.
        _keys_cache = [k for k in json.load(open(_KEYFILE))
                       if re.fullmatch(r"[0-9a-fA-F]{32}", str(k))]
        if not _keys_cache:
            raise RuntimeError("SCOPUS_KEYS_FILE held no valid keys")
    if _keys_cache is None:
        with open(_KEYSRC) as fh:
            src = fh.read()
        block = src.split("DEFAULT_API_KEYS = [", 1)[1].split("]", 1)[0]
        _keys_cache = re.findall(r'["\']([0-9a-fA-F]{32})["\']', block)
        if len(_keys_cache) < 10:
            raise RuntimeError("only found %d Scopus keys" % len(_keys_cache))
    return _keys_cache


_ki = [0]


# ---------------------------------------------------------------- http + cache
def _cache_path(url, tag=""):
    h = hashlib.sha256((tag + "|" + url).encode()).hexdigest()
    sub = os.path.join(CACHE, h[:2])
    os.makedirs(sub, exist_ok=True)
    return os.path.join(sub, h + ".json")


def http(url, headers=None, tries=4, timeout=60, tag="", use_cache=True,
         sleep=0.0, accept_404=False):
    """Cache-first GET. Returns bytes. Cached responses cost nothing on re-run."""
    cp = _cache_path(url, tag)
    if use_cache and os.path.exists(cp):
        with open(cp) as fh:
            blob = json.load(fh)
        if blob.get("err") and not accept_404:
            raise RuntimeError(blob["err"])
        return blob["body"].encode("utf-8", "replace")

    hdr = {"User-Agent": UA}
    if headers:
        hdr.update(headers)
    last = None
    for i in range(tries):
        try:
            req = urllib.request.Request(url, headers=hdr)
            body = urllib.request.urlopen(req, timeout=timeout).read()
            if use_cache:
                with open(cp, "w") as fh:
                    json.dump({"url": url, "body": body.decode("utf-8", "replace")}, fh)
            if sleep:
                time.sleep(sleep)
            return body
        except Exception as exc:  # noqa: BLE001
            last = exc
            code = getattr(exc, "code", None)
            if code == 404 and accept_404:
                if use_cache:
                    with open(cp, "w") as fh:
                        json.dump({"url": url, "err": "404", "body": ""}, fh)
                return b""
            if code in (400, 401, 403, 404) and i >= 1:
                break
            time.sleep(1.5 * (i + 1))
    raise RuntimeError("GET failed %s :: %s" % (url, str(last)[:200]))


def hjson(url, **kw):
    return json.loads(http(url, **kw))


def scopus_get(path, params, tries_per_key=3):
    """Scopus Search/Article with round-robin key rotation on 401/403/429."""
    keys = scopus_keys()
    url = "https://api.elsevier.com" + path + "?" + urllib.parse.urlencode(params)
    cp = _cache_path(url, "scopus")
    if os.path.exists(cp):
        with open(cp) as fh:
            return json.loads(json.load(fh)["body"])

    last = None
    for attempt in range(min(len(keys), 8)):
        k = keys[_ki[0] % len(keys)]
        _ki[0] += 1
        try:
            req = urllib.request.Request(
                url, headers={"X-ELS-APIKey": k, "Accept": "application/json",
                              "User-Agent": UA})
            body = urllib.request.urlopen(req, timeout=60).read()
            with open(cp, "w") as fh:
                json.dump({"url": url, "body": body.decode("utf-8", "replace")}, fh)
            time.sleep(0.12)
            return json.loads(body)
        except Exception as exc:  # noqa: BLE001
            last = exc
            code = getattr(exc, "code", None)
            if code in (401, 403, 429):
                time.sleep(0.4)
                continue
            if code == 400:
                break
            time.sleep(1.0)
    raise RuntimeError("scopus_get failed %s :: %s" % (url, str(last)[:200]))


def openalex(path, **params):
    params.setdefault("mailto", MAILTO)
    return hjson("https://api.openalex.org" + path + "?" + urllib.parse.urlencode(params),
                 sleep=0.12)


# ---------------------------------------------------------------- normalisers
def norm_doi(d):
    if not d:
        return ""
    d = str(d).strip().lower()
    d = re.sub(r"^https?://(dx\.)?doi\.org/", "", d)
    d = re.sub(r"^doi:\s*", "", d)
    return d.strip()


_TRANSLIT = [
    (r"\bmuhammad\b|\bmohamed\b|\bmohammed\b|\bmohd\b|\bmuhammed\b", "mohammad"),
    (r"\babdullah\b|\babdulla\b|\babdallh\b", "abdallah"),
    (r"\bahmed\b", "ahmad"),
    (r"\bibraheem\b", "ibrahim"),
    (r"\byousef\b|\byusuf\b|\byousuf\b", "yousif"),
    (r"\bhussein\b|\bhusain\b|\bhussein\b", "hussain"),
]


@lru_cache(maxsize=200000)
def norm_name(n):
    """Aggressive normaliser for matching people across sources.

    Handles Unicode hyphens (U+2010 appears in real OpenAlex data e.g.
    'Faris El-Dahiyat'), Arabic article variants (Al-/Al /El-/El ), and the
    common transliteration splits.
    """
    if not n:
        return ""
    s = unicodedata.normalize("NFKD", str(n))
    s = "".join(c for c in s if not unicodedata.combining(c))
    s = s.lower()
    s = re.sub(r"[‐-―−]", "-", s)      # unicode dashes -> ascii
    s = re.sub(r"[^a-z\s\-']", " ", s)
    s = re.sub(r"\b(al|el)[\s\-]+", "", s)            # drop the article entirely
    for pat, rep in _TRANSLIT:
        s = re.sub(pat, rep, s)
    s = re.sub(r"\s+", " ", s).strip()
    return s


def _strip_article(tok):
    """'elrefae' -> 'refae', matching 'el refae' which norm_name already split off.

    Guarded on remainder length so real names ('Elias', 'Alam') survive.
    This is deliberately fuzzy; ambiguous merges land in Review_Queue.
    """
    m = re.match(r"^(?:al|el)(.{4,})$", tok)
    return m.group(1) if m else tok


@lru_cache(maxsize=200000)
def name_key(n):
    """Order-insensitive token key, so 'Ghaleb A. El Refae' == 'Elrefae Ghaleb'."""
    toks = [_strip_article(t) for t in norm_name(n).replace("-", " ").split()
            if len(t) > 1]
    return " ".join(sorted(toks))


@lru_cache(maxsize=200000)
def initial_keys(n):
    """Every surname+initial reading of a name, as a frozenset.

    Scopus prints "Abouhait K." (surname first); OpenAlex prints
    "Khawla Abouhait" (given first). A single reading matches one convention
    and silently fails on the other -- which is how 1,978 of 2,020 author
    rows failed to find their own row in the Scopus export. Emitting both
    readings and intersecting is order-agnostic.
    """
    if not n:
        return frozenset()
    raw = str(n).strip()
    out = set()
    if "," in raw:
        sur, given = raw.split(",", 1)
        out.add(_ikey(sur, given))
    else:
        parts = [p for p in raw.split() if p]
        # Scopus writes "Al Meslamani A.Z." -- a multi-word surname followed by
        # initials. Anything that is pure initials at the end is the given name,
        # so everything before it is the surname, however many words that is.
        if len(parts) >= 2 and re.fullmatch(r"(?:[A-Za-z]\.){1,4}", parts[-1]):
            out.add(_ikey(" ".join(parts[:-1]), parts[-1]))
        if len(parts) >= 2:
            out.add(_ikey(parts[-1], " ".join(parts[:-1])))   # given ... surname
            out.add(_ikey(parts[0], " ".join(parts[1:])))     # surname given ...
            # multi-word surname read from the front, e.g. "Bany Salameh Haythem"
            out.add(_ikey(" ".join(parts[:2]), " ".join(parts[2:]) or parts[0]))
            out.add(_ikey(" ".join(parts[-2:]), " ".join(parts[:-2]) or parts[0]))
        elif parts:
            out.add(_ikey(parts[0], ""))
    return frozenset(k for k in out if k and not k.endswith("|"))


def _ikey(sur, given):
    sur = norm_name(sur).replace("-", " ").strip()
    sur = " ".join(_strip_article(t) for t in sur.split())
    g = norm_name(given).strip()
    return "%s|%s" % (sur, g[0]) if sur and g else ""


@lru_cache(maxsize=200000)
def initial_key(n):
    """Surname + first given initial, for matching across the two Scopus
    name formats.

    'Authors with affiliations' prints "Arafat M." while 'Author full names'
    prints "Arafat, Mosab" -- token equality never matches those, which is how
    real AAU authors on mega-collaboration papers were being missed. Both
    formats put the surname first, so surname + initial joins them.
    """
    if not n:
        return ""
    raw = str(n)
    if "," in raw:
        sur, given = raw.split(",", 1)
    else:
        parts = raw.split()
        sur, given = (parts[0], " ".join(parts[1:])) if len(parts) > 1 else (raw, "")
    sur = norm_name(sur).replace("-", " ").strip()
    sur = " ".join(_strip_article(t) for t in sur.split())
    gi = ""
    g = norm_name(given).strip()
    if g:
        gi = g[0]
    return "%s|%s" % (sur, gi) if sur else ""


# ---------------------------------------------------------------- the badge rule
# CRITICAL: 'Al Ain' alone must never match. United Arab Emirates University is
# physically located in Al Ain, so its affiliation strings read
# "..., Al Ain, United Arab Emirates". Requiring 'univ' to follow 'al ain'
# is what keeps the whole of UAEU out of this dataset.
# Accepts the unicode hyphens that appear in real publisher data ("Al‐Ain
# University" uses U+2010, not ASCII), and the reversed "University of Al Ain".
_DASH = r"[\s\-\u2010-\u2015\u2212]*"
AAU_RE = re.compile(
    r"al" + _DASH + r"ain" + _DASH + r"\s*univ"
    r"|univ\w*\s+of\s+al" + _DASH + r"ain"
    r"|\bal\s*alin\s+univ", re.I)

# Guard: strings that look AAU-ish but are a different institution.
# Institutions that sit in or near Al Ain and get mis-linked to AAU by
# OpenAlex because the city name matches. Verified on real slots: Liwa
# University authors were being badged AAU purely on a ROR link.
NOT_AAU_RE = re.compile(
    r"united\s+arab\s+emirates\s+univ|uae\s+univ|\buaeu\b"
    r"|\bliwa\s+univ", re.I)


def badge(authorship, doc_afids=None):
    """Decide whether ONE author on ONE paper carried an AAU affiliation.

    Returns (is_aau, signals) where signals records exactly which of the three
    independent tests fired -- every row must stay auditable.
    """
    sig = {"ror": False, "string": False, "scopus_afid": False}

    rors = [i.get("ror") for i in (authorship.get("institutions") or [])]
    if AAU_ROR in rors:
        sig["ror"] = True

    raws = authorship.get("raw_affiliation_strings") or []
    joined = " | ".join(raws)
    if AAU_RE.search(joined):
        sig["string"] = True

    if doc_afids and AAU_AFID in set(doc_afids):
        sig["scopus_afid"] = True

    # THE PRINTED AFFILIATION WINS.
    #
    # The doctor's rule is "المهم الaffiliation على الورقه" -- what counts is
    # what the paper printed.  OpenAlex sometimes resolves BOTH Al Ain
    # University and United Arab Emirates University from a string that names
    # only UAEU, because UAEU's address contains the city "Al Ain".  Observed
    # on real data: 5 slots carrying
    #   institutions = ['Al Ain University', 'United Arab Emirates University']
    #   raw          = 'United Arab Emirates University ... Al Ain'
    # Those authors are UAEU, not AAU.  When the printed text names UAEU and
    # never names AAU, that overrides the inferred ROR link.
    uaeu_only = bool(joined) and bool(NOT_AAU_RE.search(joined)) and \
        not AAU_RE.search(joined)
    if uaeu_only:
        sig["string"] = False
        sig["ror_overridden_by_printed_text"] = True
        is_aau = False
        return is_aau, sig

    # scopus_afid is document-level, not author-level: it is recorded as
    # evidence but never badges an author on its own.
    is_aau = sig["ror"] or sig["string"]
    return is_aau, sig


# AAU affiliation strings name the unit in at least six ways:
#   "College of Pharmacy"      "Faculty of Engineering"
#   "Communication & Media College"   "Department of Artificial Intelligence"
#   "Clinical Pharmacy Department"    "Collage of Law"  (a real typo in the data)
# Matching only "College of" left a third of the roster unassigned.
UNIT_RES = [
    re.compile(r"\b(?:college|collage|faculty|school)\s+of\s+([A-Za-z&\s,]{3,60})", re.I),
    re.compile(r"\b([A-Za-z&\s]{3,46}?)\s+(?:college|faculty)\b", re.I),
    re.compile(r"\bdep(?:artmen)?t\.?\s+of\s+([A-Za-z&\s]{3,46})", re.I),
    re.compile(r"\b([A-Za-z&\s]{3,46}?)\s+dep(?:artmen)?t\.?\b", re.I),
]

CANON = [
    # computing first: "Computer Science and Software Engineering" is a
    # computing department, and "engineer" would otherwise claim it.
    ("computer", "College of Computer and Information Sciences"),
    ("information tech", "College of Computer and Information Sciences"),
    ("artificial intelligence", "College of Computer and Information Sciences"),
    ("data scien", "College of Computer and Information Sciences"),
    ("cyber", "College of Computer and Information Sciences"),
    ("pharmac", "College of Pharmacy"),
    ("engineer", "College of Engineering"),
    ("education", "College of Education"),
    ("teach", "College of Education"),
    ("business", "College of Business"),
    ("account", "College of Business"),
    ("financ", "College of Business"),
    ("econom", "College of Business"),
    ("management", "College of Business"),
    ("market", "College of Business"),
    ("law", "College of Law"),
    ("legal", "College of Law"),
    ("shariah", "College of Law"),
    ("communicat", "College of Communication and Media"),
    ("media", "College of Communication and Media"),
    ("journal", "College of Communication and Media"),
    ("software", "College of Engineering"),
    ("civil", "College of Engineering"),
    ("electric", "College of Engineering"),
    ("mechanic", "College of Engineering"),
    ("architect", "College of Engineering"),
    ("nurs", "College of Health Sciences"),
    ("health scien", "College of Health Sciences"),
    ("public health", "College of Health Sciences"),
    ("nutrition", "College of Health Sciences"),
    ("dietet", "College of Health Sciences"),
    ("medicine", "College of Medicine and Health Sciences"),
    ("dentist", "College of Dentistry"),
    ("agricultur", "College of Agriculture and Veterinary Medicine"),
    ("veterinar", "College of Agriculture and Veterinary Medicine"),
    ("psycholog", "College of Education"),
    ("graduate studies", "College of Graduate Studies"),
    ("sociolog", "College of Humanities and Social Sciences"),
    ("arabic", "College of Humanities and Social Sciences"),
    ("english language", "College of Humanities and Social Sciences"),
    ("translation", "College of Humanities and Social Sciences"),
    ("literature", "College of Humanities and Social Sciences"),
    ("linguist", "College of Humanities and Social Sciences"),
    ("physics", "College of Arts and Sciences"),
    ("chemistry", "College of Arts and Sciences"),
    ("mathemat", "College of Arts and Sciences"),
    ("humanities", "College of Humanities and Social Sciences"),
    ("social scien", "College of Arts and Sciences"),
    ("art", "College of Arts and Sciences"),
    ("scien", "College of Arts and Sciences"),
]

# Words that look like a unit but are not one.
_NOT_UNIT = re.compile(
    r"^(the|and|of|research|center|centre|institute|campus|university|"
    r"al\s*ain|abu\s*dhabi|uae|united arab emirates|po box|p\.?o\.?|"
    r"postgraduate|diploma|librarian|liwa|head)\b", re.I)


def canon_college(raw):
    """Snap a captured unit fragment to the canonical AAU college."""
    if not raw:
        return ""
    t = re.sub(r"\s+", " ", raw).strip().lower()
    t = re.sub(r"\b(al[\s\-]*ain|abu dhabi|university|univ|campus|uae|"
               r"united arab emirates|p\.?o\.? box\s*\d*|\d+)\b", " ", t)
    t = re.sub(r"\s+", " ", t).strip(" ,&-.")
    if not t or _NOT_UNIT.match(t):
        return ""
    for key, name in CANON:
        if key in t:
            return name
    return ""


def _aau_segments(raws):
    """Keep only the parts of an affiliation that belong to AAU.

    Authors list several institutions in one string. Reading the unit out of
    the whole string attributes another university's department to AAU --
    observed on real rows, where "Department of Computer Engineering &
    Technology, Guru Nanak Dev University, Punjab | Al Ain University" was
    filing the author under AAU's College of Computer and Information
    Sciences on the strength of Guru Nanak's department.

    A segment counts only if it names AAU itself. Within a segment the unit
    normally precedes the university ("College of Pharmacy, Al Ain
    University"), so the text before the AAU mention is what gets read.
    """
    out = []
    for raw in (raws or []):
        for part in re.split(r"\s*\|\s*", raw):
            if not AAU_RE.search(part):
                continue
            m = AAU_RE.search(part)
            before = part[:m.start()]
            after = part[m.end():]
            # the unit is usually before the university name; a trailing
            # "Al Ain University, College of X" also happens
            out.append(before if before.strip(" ,-") else after)
    return out


def college_of(raws):
    """Best-effort college, read only from the AAU part of the affiliation."""
    segs = _aau_segments(raws)
    joined = " | ".join(s for s in segs if s)
    if not joined:
        return ""
    for rx in UNIT_RES:
        for m in rx.finditer(joined):
            c = canon_college(m.group(1))
            if c:
                return c
    # last resort: a bare discipline word sitting next to the AAU name.
    # Long keys match as a prefix ("pharmac" -> pharmacy/pharmaceutical);
    # short ones ("law", "art") need both boundaries or they fire on
    # "Lawrence" and "Article".
    for key, name in CANON:
        rx = (r"\b%s" % re.escape(key)) if len(key) > 6 else (r"\b%s\b" % re.escape(key))
        if re.search(rx, joined, re.I):
            return name
    return ""


def log(msg):
    sys.stderr.write("[%s] %s\n" % (time.strftime("%H:%M:%S"), msg))
    sys.stderr.flush()
