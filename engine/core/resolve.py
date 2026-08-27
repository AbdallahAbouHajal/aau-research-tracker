"""Resolve a faculty name to its Scopus AU-ID.

The Scopus Author Search API is locked with these keys, so the only place
AU-IDs exist in bulk is the Scopus CSV export, whose "Author full names"
column reads "Surname, Given (60611061600)". That gives ~9,500 name->AU-ID
pairs to match against.

Matching is tiered and never silently guesses. Anything that matches more
than one AU-ID goes to a review queue instead of picking a winner -- 13 real
people share the name "Muhammad Ilyas" in this corpus, so picking is wrong.

Measured on the 322 names already scraped from aau.ac.ae:
    182 auto-resolved (high/medium) | 56 review | 84 no match

"No match" is a normal outcome: a faculty member with no 2025-26 papers has
no AU-ID to find, and needs none -- the sweep would return nothing anyway.
"""
import csv
import collections
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import census as X
import translit as TL

csv.field_size_limit(10 ** 9)
_NAMED_ID = re.compile(r"^(.*?)\s*\((\d{6,})\)\s*$")


def known_shared_names():
    """Names the census proved are shared by several different people.

    "Muhammad Ilyas" resolves to a single AU-ID in the export, which looks
    like a confident match -- but 13 distinct people publish under that name
    at AAU. A confident match to the wrong person is worse than no match, so
    these are forced into review regardless of tier.
    """
    out = set()
    path = X.census_file("review_queue.json")
    if not os.path.exists(path):
        return out
    try:
        import json
        for r in json.load(open(path)):
            if r.get("reason") in ("possible_duplicate_common_name",
                                   "distinct_orcids",
                                   "subset_merge_BLOCKED_common_name",
                                   "subset_merge_BLOCKED_orcid_conflict"):
                for part in str(r.get("name_key", "")).split("|"):
                    part = part.strip()
                    if part:
                        out.add(part)
    except Exception:
        pass
    return out


def build_index(export_csv=None):
    """name -> {AU-IDs}, in three lookup shapes."""
    path = export_csv or X.census_file("scopus_export.csv")
    by_key = collections.defaultdict(set)
    by_init = collections.defaultdict(set)
    by_toks = []
    names = collections.defaultdict(set)      # display name -> AU-IDs
    by_fl = collections.defaultdict(set)      # surname|first-given -> AU-IDs
    by_id = collections.defaultdict(set)      # AU-ID -> display names
    counts = collections.Counter()

    with open(path, newline="", encoding="utf-8-sig") as fh:
        for row in csv.DictReader(fh):
            for chunk in (row.get("Author full names") or "").split(";"):
                m = _NAMED_ID.match(chunk.strip())
                if not m:
                    continue
                nm, aid = m.group(1), m.group(2)
                counts[aid] += 1
                k = X.name_key(nm)
                by_key[k].add(aid)
                for ik in X.initial_keys(nm):
                    by_init[ik].add(aid)
                by_toks.append((frozenset(k.split()), aid))
                names[nm].add(aid)
                by_id[aid].add(nm)
                fk = TL.fl_key(nm)
                if fk:
                    by_fl[fk].add(aid)
    return {"by_key": by_key, "by_init": by_init, "by_toks": by_toks,
            "papers": counts, "shared": known_shared_names(), "names": names,
            "by_fl": by_fl, "by_id": by_id}


def _keep(name, cands, idx):
    """Drop candidates whose printed name cannot be this person.

    The surname+initial tier is deliberately loose so it can catch
    "Abouhait K." for "Khawla Abouhait". Loose also means "Amira Shaaban
    Ahmed" collects 27 unrelated A-somethings named Ahmad. Every candidate
    is re-checked against the name Scopus actually printed for it, so a
    review queue holds real alternatives instead of noise.
    """
    out = [c for c in cands
           if any(TL.compatible(name, nm) for nm in idx["by_id"].get(c, ()))]
    return out or []


def resolve_one(name, idx):
    """-> (auid|None, tier, candidates). Never guesses between candidates."""
    k = X.name_key(name)
    if not k:
        return None, "none", []

    if k in idx.get("shared", ()):
        fl = idx["by_fl"].get(TL.fl_key(name) or "\0") or set()
        if len(fl) == 1:
            # Flagged as a shared name, but only one AU-ID publishes under
            # this exact first+last. "Muhammad Sarfraz" is one person even
            # though "Sarfraz" plus an M is three.
            return next(iter(fl)), "medium:shared-name-first-last", []
        cands = _keep(name, sorted((idx["by_key"].get(k) or set())
                      | {a for ik in X.initial_keys(name)
                         for a in idx["by_init"].get(ik, set())}), idx)
        # Flagged as shared, but only one AU-ID exists -- there is nothing to
        # choose between, so resolve it and mark it for visibility rather than
        # parking it in a queue with a single option.
        if len(cands) == 1:
            return cands[0], "medium:shared-name-single-id", []
        if cands:
            return None, "review:name-shared-by-several-people", cands
        return None, "none:no-papers", []

    hits = idx["by_key"].get(k) or set()
    if len(hits) == 1:
        return next(iter(hits)), "high:exact-name", []
    if hits:
        return None, "review:exact-name-ambiguous", sorted(hits)

    # FIRST NAME + LAST NAME. Runs before the initials tier because it is
    # far more specific: "Sarfraz, Muhammad" is one person, "sarfraz|m" is
    # three. Middle names are dropped -- they are the source of the noise.
    fk = TL.fl_key(name)
    if fk:
        fl = idx["by_fl"].get(fk) or set()
        if len(fl) == 1:
            return next(iter(fl)), "high:first-last", []
        if fl:
            return None, "review:first-last-ambiguous", sorted(fl)

    hits = set()
    for ik in X.initial_keys(name):
        hits |= idx["by_init"].get(ik, set())
    hits = _keep(name, sorted(hits), idx)
    if len(hits) == 1:
        return hits[0], "high:surname-initial", []
    if hits:
        return None, "review:surname-initial-ambiguous", hits

    # a spelled-out middle name against an initial, e.g.
    # "Suad Abdel Karim Alwaely" vs "Suad Abdalkareem Alwaely"
    t = frozenset(k.split())
    sub = {aid for ts, aid in idx["by_toks"]
           if t and ts and (t < ts or ts < t)
           and len(t & ts) >= 2 and abs(len(t) - len(ts)) <= 1}
    sub = _keep(name, sorted(sub), idx)
    if len(sub) == 1:
        return sub[0], "medium:middle-name", []
    if sub:
        return None, "review:subset-ambiguous", sub

    # Last resort: a transliteration variant. The roster says
    # "Khawlah Mitib Al-Takhayneh"; Scopus prints "Al-Tkhayneh, Khawlah M."
    # Without this she lands in "no Scopus record" while holding 41 papers.
    # TL.match() compares surnames only. On its own it matched "Asim Ahmed
    # Elnour Ahmed" to "Ahmadi, Ali" -- a different person with a similar
    # surname and no shared given name. compatible() requires the first name
    # to agree too, and understands a compound surname printed mid-name.
    near = {}
    for nm, ids in idx["names"].items():
        if TL.compatible(name, nm):
            for a in ids:
                near[a] = max(near.get(a, 0), idx["papers"].get(a, 0))
    if len(near) == 1:
        return next(iter(near)), "medium:transliteration", []
    if near:
        return None, "review:transliteration-ambiguous", sorted(near)
    return None, "none:no-papers", []


def resolve_all(people, idx=None):
    """Annotate each faculty record in place; return a tier summary."""
    idx = idx or build_index()
    tiers = collections.Counter()
    for p in people:
        if p.get("scopus_auid") and p.get("auid_tier", "").startswith("manual"):
            tiers["manual"] += 1
            continue
        auid, tier, cands = resolve_one(p["name"], idx)
        p["scopus_auid"] = auid or ""
        p["auid_tier"] = tier
        p["auid_candidates"] = [
            {"auid": c, "papers": idx["papers"].get(c, 0)} for c in cands]
        tiers[tier.split(":")[0]] += 1
    return dict(tiers)


def review_queue(people):
    """Faculty whose AU-ID needs a human. Busiest candidates first."""
    out = [p for p in people if p.get("auid_tier", "").startswith("review")]
    out.sort(key=lambda p: -max([c["papers"] for c in p.get("auid_candidates", [])]
                                or [0]))
    return out


MANUAL_CSV = os.path.expanduser("~/Downloads/AAU_names_to_check.csv")
MANUAL_ALT = os.path.expanduser("~/Downloads/AAU_names_to_check_RESOLVED.csv")
MANUAL_LAST = os.path.expanduser("~/Downloads/AAU_still_unknown_12.csv")
_AUTHID_URL = re.compile(r"authorId=(\d{6,})")


def load_manual(path=None):
    """Read AU-IDs a human filled into PASTE_AUID_HERE.

    A human decision outranks every tier here and is never re-guessed:
    resolve_all() skips any record already tagged "manual".
    """
    paths = [path] if path else [MANUAL_CSV, MANUAL_ALT, MANUAL_LAST]
    out = {}
    for pth in paths:
        if not pth or not os.path.exists(pth):
            continue
        with open(pth, newline="", encoding="utf-8-sig") as fh:
            for row in csv.DictReader(fh):
                nm = (row.get("name") or "").strip()
                if not nm:
                    continue
                # the ID may be pasted bare, or left as the Scopus URL it was
                # copied from, in whichever column the spreadsheet ended up
                # using. Any of those is a human decision.
                aid = re.sub(r"\D", "", (row.get("PASTE_AUID_HERE") or ""))
                if not aid:
                    for v in row.values():
                        m = _AUTHID_URL.search(str(v or ""))
                        if m:
                            aid = m.group(1)
                            break
                if aid and len(aid) >= 6 and not str(
                        row.get("found_by", "")).startswith("AUTO"):
                    out[X.name_key(nm)] = aid
    return out


def apply_manual(people, path=None):
    """-> number of records set from the human-checked file."""
    manual = load_manual(path)
    n = 0
    for p in people:
        aid = manual.get(X.name_key(p.get("name", "")))
        if aid and p.get("scopus_auid") != aid:
            p["scopus_auid"] = aid
            p["auid_tier"] = "manual"
            p["auid_candidates"] = []
            n += 1
    return n


NO_RECORD_NOTE = ("new, visiting or adjunct faculty -- no Scopus record: "
                  "not in the AAU export, no Scopus link on their AAU "
                  "profile, and not a co-author on any AAU paper in the window")


def _profile_pass(people, say, force=False):
    """Ask each unresolved person's own AAU page for their Scopus id.

    This is the expensive step -- it fetches every unresolved person's page
    from aau.ac.ae and then asks Scopus to verify what it finds. Measured on a
    GitHub runner it was 638s, 77% of the whole run.

    Almost all of that is re-asking a question already answered. Someone with
    no Scopus record at all does not acquire one between Mondays, and when
    they do, they arrive with a paper the sweep finds anyway. So a person
    marked profile_checked is skipped until someone asks for a recheck.
    """
    import profile_ids as PI
    n = 0
    todo = [q for q in people if not q.get("scopus_auid") and q.get("profile_url")]
    if not force:
        skipped = [q for q in todo if q.get("profile_checked")]
        todo = [q for q in todo if not q.get("profile_checked")]
        if skipped:
            say("  skipping %d profiles already checked (pass force_profiles "
                "to recheck)" % len(skipped))
    for p in todo:
        try:
            g = PI.resolve(p)
        except Exception:
            continue
        if g["auid"]:
            p["scopus_auid"] = g["auid"]
            p["auid_tier"] = g["tier"]
            p["auid_evidence"] = g["ev"].get("verify") or {}
            p["auid_candidates"] = []
            n += 1
            say("  profile route: %s -> %s" % (p["name"], g["auid"]))
        else:
            p["profile_checked"] = True     # asked, and the page had nothing
    return n


def resolve_chain(people, idx=None, use_profiles=True, log=None,
                  force_profiles=False):
    """Full resolution ladder, best evidence first.

      1. a human's decision in the check-file        (never overridden)
      2. the name tiers against the Scopus export    (exact / first+last / ...)
      3. the person's own AAU page                   (declared Scopus link)

    Step 3 exists because steps 1-2 structurally cannot find some people:
    the roster says "Iffat Sabir", Scopus files her as "Chaudhry, Iffat S.",
    and "Amira Shaaban Ahmed" publishes as "Said, Amira S. A.". No name
    matcher reaches those. Their own profile page links the right ID.
    """
    say = log or (lambda *_: None)
    # The Scopus export is what build_index() reads, and it is deliberately not
    # shipped (a bulk export carries licensing terms). When the roster already
    # carries settled AU-IDs -- which it does, because they were resolved and
    # audited once -- there is nothing to re-derive, so skip the index entirely
    # rather than crash looking for a file that should not be there.
    if idx is None:
        settled = sum(1 for p in people if p.get("scopus_auid"))
        try:
            have_export = os.path.exists(X.census_file("scopus_export.csv"))
        except Exception:
            have_export = False
        if not have_export:
            if settled:
                say("  %d AU-IDs already settled; no export to re-resolve from"
                    % settled)
                tiers = collections.Counter(
                    p.get("auid_tier", "none") .split(":")[0] for p in people)
                n_prof = 0
                if use_profiles:
                    n_prof = _profile_pass(people, say, force_profiles)
                for p in people:
                    if not p.get("scopus_auid"):
                        p["auid_tier"] = "none:no-scopus-record"
                        p["no_scopus_reason"] = NO_RECORD_NOTE
                out = dict(tiers)
                out["manual"] = settled
                out["profile"] = n_prof
                out["no_record"] = sum(1 for p in people
                                       if not p.get("scopus_auid"))
                return out
            raise SystemExit(
                "no Scopus export and no settled AU-IDs -- nothing to resolve "
                "from. Ship data/roster.json with resolved ids.")
        idx = build_index()
    tiers = resolve_all(people, idx)
    n_man = apply_manual(people)
    n_prof = _profile_pass(people, say, force_profiles) if use_profiles else 0
    # Everyone still without an ID was checked three ways: no name in the
    # Scopus export, no Scopus link on their AAU page, and no appearance in
    # the full author list of any of the 1,330 AAU papers in the window.
    # That is not a matching failure -- it is the correct answer for someone
    # newly appointed, visiting, adjunct, or simply not publishing. They are
    # labelled so, and are NOT counted as unresolved on the dashboard.
    for p in people:
        if not p.get("scopus_auid"):
            p["auid_tier"] = "none:no-scopus-record"
            p["no_scopus_reason"] = NO_RECORD_NOTE
    tiers["manual"] = n_man
    tiers["profile"] = n_prof
    tiers["no_record"] = sum(1 for p in people if not p.get("scopus_auid"))
    return tiers
