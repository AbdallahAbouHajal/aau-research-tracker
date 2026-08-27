"""Mirror the Scopus keys where a scheduled job can actually read them.

common.scopus_keys() reads a file in ~/Desktop, mode -rwx------. On macOS 14
~/Desktop, ~/Documents and ~/Downloads are TCC-protected, and a launchd job
does NOT inherit Terminal's Full Disk Access. The weekly run would die on
PermissionError and the dashboard would simply stop updating -- failure that
looks like silence.

So: read the mirror if present, else read through from the census (which
happens interactively, where TCC is satisfied) and write it. The Desktop file
stays the source of truth; this is a cache with a visible age.
"""
import json
import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
MIRROR = os.path.join(ROOT, "config", "scopus_keys.json")


def load(force_resync=False):
    if not force_resync and os.path.exists(MIRROR):
        try:
            with open(MIRROR) as fh:
                b = json.load(fh)
            if b.get("keys"):
                return b["keys"]
        except Exception:
            pass
    import census as X
    keys = X.scopus_keys()
    os.makedirs(os.path.dirname(MIRROR), exist_ok=True)
    with open(MIRROR, "w") as fh:
        json.dump({"synced": time.time(), "n": len(keys), "keys": keys}, fh)
    os.chmod(MIRROR, 0o600)
    return keys


def state():
    if not os.path.exists(MIRROR):
        return {"mirrored": False}
    try:
        with open(MIRROR) as fh:
            b = json.load(fh)
        return {"mirrored": True, "n": b.get("n"),
                "age_days": round((time.time() - b.get("synced", 0)) / 86400, 1)}
    except Exception:
        return {"mirrored": False}
