"""Bridge to the finished AAU Author Census pipeline.

The census in ~/Downloads/AAU_Author_Census stays the source of truth: it owns
the Scopus key rotation, the 168 MB warm cache, the AAU affiliation rule, the
name matching, and its own 40-test suite. Copying any of it here would fork the
rule that decides who counts as AAU -- the exact thing that has to stay single.

So this module only puts that package on sys.path and re-exports. If the census
moves, one constant changes.
"""
import os
import sys

CENSUS = os.environ.get(
    "AAU_CENSUS_DIR",
    "/Users/abdallahabouhajal/Downloads/AAU_Author_Census")
SCRIPTS = os.path.join(CENSUS, "scripts")

VENDOR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                      "vendor")
if not os.path.isdir(SCRIPTS):
    # No census checkout (a CI runner, or the university's own server): fall
    # back to the vendored copy of the same file. The affiliation rule is not
    # reimplemented anywhere -- this is the identical module.
    if os.path.isdir(VENDOR) and os.path.exists(os.path.join(VENDOR, "common.py")):
        SCRIPTS = VENDOR
    else:
        raise RuntimeError(
            "AAU Author Census not found at %s and no vendored copy in %s.\n"
            "Set AAU_CENSUS_DIR to its location." % (CENSUS, VENDOR))

if SCRIPTS not in sys.path:
    sys.path.insert(0, SCRIPTS)

import common as C  # noqa: E402

# --- the pieces the tracker actually uses -------------------------------
badge = C.badge                  # the AAU affiliation rule
name_key = C.name_key            # order-insensitive identity key
initial_keys = C.initial_keys    # surname+initial, both name orders
norm_name = C.norm_name
norm_doi = C.norm_doi
college_of = C.college_of
scopus_get = C.scopus_get        # key rotation + cache
openalex = C.openalex            # metrics ONLY -- never affiliation
http = C.http
scopus_keys = C.scopus_keys
log = C.log

AAU_AFID = C.AAU_AFID
AAU_RE = C.AAU_RE
CENSUS_DATA = C.DATA


def census_file(name):
    """Absolute path to a file in the census's data/ directory."""
    return os.path.join(CENSUS_DATA, name)


def have(name):
    return os.path.exists(census_file(name))
