"""Match Arabic names across transliteration spellings.

The roster says "Khawlah Mitib Al-Takhayneh"; Scopus prints "Al-Tkhayneh,
Khawlah M." One vowel apart, and every exact and initials match fails -- she
came out as a *suggested addition* with 41 papers while already on the list.

Vowels are the unstable part of Arabic transliteration: Takhayneh/Tkhayneh,
Mohammad/Muhammad/Mohamed, Hussain/Hussein, Abdallah/Abdullah. Consonants are
stable. So compare the consonant skeleton of the surname, keeping the first
letter (which is stable and stops 'Ali' colliding with 'Alwaely').

Deliberately strict, because a surname match plus a given initial is the whole
identity claim: same first letter, same skeleton, same given initial, and the
skeleton must be at least 3 characters -- short ones are too collidable.
"""
import os
import re
import sys
from functools import lru_cache

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import census as X



def _lev1(a, b):
    """True if a and b are within one edit. Cheap, no library.

    One edit is the right threshold, not two. Takhayneh/Tkhayneh differ by one
    inserted vowel -- the real case. Hussain/Hassan differ by two, and they are
    different names; at a threshold of two they would merge.
    """
    if a == b:
        return True
    la, lb = len(a), len(b)
    if abs(la - lb) > 1:
        return False
    if la == lb:                                   # one substitution
        return sum(1 for x, y in zip(a, b) if x != y) == 1
    if la > lb:                                    # one deletion from a
        a, b, la, lb = b, a, lb, la
    i = j = 0
    skipped = False
    while i < la and j < lb:
        if a[i] == b[j]:
            i += 1
            j += 1
        elif skipped:
            return False
        else:
            skipped = True
            j += 1
    return True


def _parts(name):
    """(surname, given-initial) for both name orders."""
    raw = (name or "").strip()
    out = []
    if "," in raw:
        sur, given = raw.split(",", 1)
        out.append((sur, given))
    else:
        toks = [t for t in raw.split() if t]
        if len(toks) >= 2:
            if re.fullmatch(r"(?:[A-Za-z]\.){1,4}", toks[-1]):
                out.append((" ".join(toks[:-1]), toks[-1]))
            out.append((toks[-1], " ".join(toks[:-1])))
            out.append((toks[0], " ".join(toks[1:])))
            if len(toks) >= 3:
                out.append((" ".join(toks[-2:]), " ".join(toks[:-2])))
        elif toks:
            out.append((toks[0], ""))
    return out


def _norm_sur(sur):
    """Normalise a surname to one comparable token.

    The Arabic article appears three ways in the same corpus: separated
    ("Al Meslamani"), hyphenated ("Al-Rabai'ah") and glued ("Alrabaiah").
    Strip it in all three forms, and drop apostrophes, which are pure noise
    ("Rabai'ah" / "Rabaiah", "Lo'ai" / "Loai").
    """
    s = X.norm_name(sur).replace("-", " ").replace("'", "").strip()
    toks = [t for t in s.split() if t not in ("al", "el")]
    out = []
    for t in toks:
        m = re.match(r"^(?:al|el)(.{4,})$", t)     # glued: alrabaiah -> rabaiah
        out.append(m.group(1) if m else t)
    return "".join(out)


@lru_cache(maxsize=100000)
def readings(name):
    """{(surname, given_initial)} across both name orders."""
    out = set()
    for sur, given in _parts(name):
        s = _norm_sur(sur)
        g = X.norm_name(given).strip()
        if len(s) >= 4 and g:
            out.add((s, g[0]))
    return frozenset(out)


def match(a, b):
    """Same person across transliteration spellings?

    Fires ONLY on a near-miss -- an exact surname match is already handled by
    initial_keys upstream. That matters: "Ahmad Ali" and "Ahmad Alwaely" both
    have a reading with surname "ahmad", so allowing the exact case here would
    merge two different people through the name-order ambiguity.

    So: given initial must agree, and the surnames must differ by exactly one
    edit. Surnames under five characters are excluded as too collidable.
    """
    for sa, ga in readings(a):
        for sb, gb in readings(b):
            if ga != gb:
                continue
            if sa == sb:
                # An exact surname match only counts when the surname is long
                # enough to be a surname. "Ahmad Ali" and "Ahmad Alwaely" both
                # yield a reading with surname "ahmad" (5) through the
                # name-order ambiguity; "abusharour" (10) is not that.
                if len(sa) >= 7:
                    return True
                continue
            if min(len(sa), len(sb)) >= 5 and _lev1(sa, sb):
                return True
    return False


def first_last(name):
    """(surname, first-given-name) using FIRST and LAST only.

    Middle names are what make Arabic names look ambiguous. "Mohammad Majed
    Al Ahmad" reduced to surname+initial is "ahmad|m", which collides with
    every Mohammad, Mahmoud and Mohamed whose surname is Ahmad -- 28 false
    candidates. Keeping the FULL first name and the LAST name instead gives
    "ahmad|mohammad", which is specific.

    Scopus prints "Sarfraz, Muhammad" and the roster says "Muhammad Sarfraz";
    both reduce to ("sarfraz", "muhammad"). One hit, no ambiguity.
    """
    raw = (name or "").strip()
    if not raw:
        return None
    if "," in raw:
        sur, given = raw.split(",", 1)
    else:
        toks = [t for t in raw.split() if t]
        if len(toks) < 2:
            return None
        # a trailing initials block means the surname is everything before it
        if re.fullmatch(r"(?:[A-Za-z]\.){1,4}", toks[-1]):
            sur, given = " ".join(toks[:-1]), toks[-1]
        else:
            sur, given = toks[-1], " ".join(toks[:-1])
    s_sur = _norm_sur(sur)
    g = [t for t in X.norm_name(given).split() if len(t) > 1]
    if not s_sur or not g:
        return None
    return (s_sur, g[0])


def fl_key(name):
    fl = first_last(name)
    return "%s|%s" % fl if fl else ""


def _givens(name):
    """Given-name tokens, in order, initials kept as single letters."""
    raw = (name or "").strip()
    if "," in raw:
        given = raw.split(",", 1)[1]
    else:
        toks = [t for t in raw.split() if t]
        given = " ".join(toks[:-1]) if len(toks) > 1 else ""
    given = re.sub(r"[.\-]", " ", given)
    return [t for t in X.norm_name(given).split() if t]


def _first_ok(a, b):
    """Do two given-name lists agree on the FIRST name?"""
    if not a or not b:
        return False
    x, y = a[0], b[0]
    if len(x) == 1 or len(y) == 1:       # an initial against a full name
        return x[0] == y[0]
    if x == y or _lev1(x, y):
        return True
    # "Abd" vs "Abdulrahman" -- a truncation, not a different name
    return (x.startswith(y) or y.startswith(x)) and min(len(x), len(y)) >= 4


def _sur_ok(a, b):
    sa, sb = _norm_sur(a), _norm_sur(b)
    if not sa or not sb:
        return False
    return sa == sb or (min(len(sa), len(sb)) >= 5 and _lev1(sa, sb))


def compatible(roster_name, scopus_name):
    """Could these be the same person? Surname AND first name must agree.

    The surname+initial tier alone produces 27 candidates for "Amira Shaaban
    Ahmed" because it matches every A-something Ahmad in 9,364 names. Requiring
    the FIRST name to agree as well is what makes a candidate list reviewable.
    """
    def _sur(n):
        n = (n or "").strip()
        if "," in n:
            return n.split(",", 1)[0]
        t = [x for x in n.split() if x]
        return t[-1] if t else ""
    if _sur_ok(_sur(roster_name), _sur(scopus_name)) \
            and _first_ok(_givens(roster_name), _givens(scopus_name)):
        return True
    # the roster may print the surname first: "Asim Ahmed Elnour Ahmed"
    # against Scopus "Ahmed Elnour, Asim"
    rt = [t for t in re.sub(r"[.,\-]", " ", roster_name or "").split() if t]
    if len(rt) > 2:
        for cut in (2, 3):
            if len(rt) > cut:
                alt = " ".join(rt[cut:]) + ", " + " ".join(rt[:cut])
                if _sur_ok(_sur(alt), _sur(scopus_name)) \
                        and _first_ok(_givens(alt), _givens(scopus_name)):
                    return True
    # A COMPOUND surname sitting in the middle of the roster name:
    # roster "Asim Ahmed Elnour Ahmed", Scopus "Ahmed Elnour, Asim".
    # Only for surnames of 2+ tokens -- a single "Ahmad" would otherwise
    # swallow "Mohammad Ahmad Ghattas", whose surname is Ghattas.
    s_toks = [t for t in X.norm_name(re.sub(r"[.\-]", " ", _sur(scopus_name))).split()
              if t not in ("al", "el")]
    if len(s_toks) >= 2 and set(s_toks) <= set(X.norm_name(rt and " ".join(rt) or "").split()):
        if _first_ok(_givens(roster_name)[:1] or rt[:1],
                     _givens(scopus_name)):
            return True
    return False
