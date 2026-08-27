#!/usr/bin/env python3
"""Rebuild the site from the pristine Claude Design bundle.

Every change to the interface is a named patch in PATCHES below, applied to an
untouched copy of the handoff bundle. Nothing is edited in place, so the design
can never drift: delete a patch and that change is gone.

    python3 build.py                 -> docs/index.html   (static, demo data)
    python3 build.py --live          -> docs/index.html   (talks to /api)
    python3 build.py --check         -> verify only, write nothing

The bundle is self-unpacking: the real page is a JSON string on line 382, and it
has to be re-encoded exactly the way the bundler does or the page dies with
"Unterminated string in JSON". encode() below is asserted byte-identical against
the untouched original before any patch is applied.
"""
import argparse
import json
import os
import re
import sys

import patches_live as PL

HERE = os.path.dirname(os.path.abspath(__file__))
SRC = os.path.join(HERE, "_extracted", "handoff",
                   "AAU Research Tracker UI (standalone).html")
OUT = os.path.join(HERE, "docs", "index.html")
TPL_LINE = 381          # 0-indexed line holding the template JSON


def encode(s):
    """Exactly the bundler's encoding. Both details below were learned the hard way.

    ensure_ascii=False  -- it ships em-dashes raw; \\u2014 makes the line differ.
    "</" -> "<\\u002F"  -- an inner </script> would close the host
                           <script type="__bundler/template"> tag early.
    """
    return json.dumps(s, ensure_ascii=False).replace("</", "<\\u002F")


# --------------------------------------------------------------------------
# Patches. Each is (name, old, new). `old` must appear exactly once.
# --------------------------------------------------------------------------

PATCHES = [

    # ---- what the user asked to remove from the first page -----------------
    ("welcome-chips: drop the two run-specific figures",
     "welcomeChips: [\n"
     "        { v: '1,336', l: 'papers in the census' },\n"
     "        { v: '511', l: 'authors, 161 on the roster' },\n"
     "        { v: '8', l: 'colleges covered' },\n"
     "      ],",
     "welcomeChips: [\n"
     "        { v: '8', l: 'colleges covered' },\n"
     "      ],"),

    # ---- the single remaining chip was left-aligned inside a centred row ---
    ("welcome-chip: centre its contents",
     'border-radius:8px;padding:14px 22px;text-align:left;min-width:180px">\n'
     '          <div style="font-size:28px;font-weight:800;'
     'letter-spacing:-.02em;line-height:1">{{ w.v }}</div>',
     'border-radius:8px;padding:14px 26px;text-align:center;min-width:180px">\n'
     '          <div style="font-size:28px;font-weight:800;'
     'letter-spacing:-.02em;line-height:1">{{ w.v }}</div>'),

    # ---- full page, not a mac window on a grey desk -----------------------
    # The chrome was right for a design mockup. On a real URL a fake title bar
    # reading "localhost:8765" is just wrong, so the whole window frame goes and
    # the app fills the viewport.
    ("shell: remove the desk padding and let the app fill the page",
     'style="min-height:100vh;background:#E9EDEA;font-family:Archivo,sans-serif;'
     'color:#1A1A1A;display:block;overflow-x:auto;padding:28px 24px 48px"',
     'style="min-height:100vh;background:#F4F6F5;font-family:Archivo,sans-serif;'
     'color:#1A1A1A;display:block;overflow-x:auto;'
     'padding:0 max(0px, calc((100% - 1560px) / 2))"'),

    # NOTE: do NOT put min-height:100vh on this element. The dc-runtime does
    # its own min-height bookkeeping here, and setting it leaves every
    # data-rise child stuck at the animation's opacity:0 start frame -- the
    # whole app renders, is laid out with real heights, and is invisible.
    # Bisected: this element with min-height:100vh -> blank; without -> fine.
    # Full height belongs on the outer wrapper instead, which already has it.
    #
    # max-width caps the stretch: the design is drawn for 1392px, so letting it
    # run to 1900px inflates every card. The page ground and this element share
    # #F4F6F5, so the capped margins are invisible.
    ("shell: full width, no rounded corners, no drop shadow",
     'style="width:1392px;max-width:100%;min-width:1180px;margin:0 auto;'
     'background:#F4F6F5;border-radius:12px;overflow:hidden;'
     'box-shadow:0 24px 70px -24px rgba(10,60,35,.35),'
     '0 4px 12px rgba(10,60,35,.08)"',
     'style="width:100%;min-width:1180px;margin:0;'
     'background:#F4F6F5;overflow:visible"'),

    ("shell: delete the fake mac title bar and its localhost:8765 label",
     '\n  <div style="height:38px;background:#0F1512;display:flex;'
     'align-items:center;padding:0 16px;gap:9px">\n'
     '    <span style="width:12px;height:12px;border-radius:50%;'
     'background:#FF5F57"></span>\n'
     '    <span style="width:12px;height:12px;border-radius:50%;'
     'background:#FEBC2E"></span>\n'
     '    <span style="width:12px;height:12px;border-radius:50%;'
     'background:#28C840"></span>\n'
     '    <div style="flex:1;text-align:center;font-size:13px;color:#8A938D;'
     'letter-spacing:.04em">AAU Research Tracker — localhost:8765</div>\n'
     '    <div style="width:60px"></div>\n'
     '  </div>\n',
     '\n'),

    ("body: page grey, not desk grey",
     "body { margin: 0; background: #E9EDEA; }",
     "body { margin: 0; background: #F4F6F5; }"),

    ("welcome: fill the viewport height",
     'min-height:812px;display:flex;flex-direction:column;align-items:center;'
     'justify-content:center;padding:80px 96px',
     'min-height:100vh;display:flex;flex-direction:column;align-items:center;'
     'justify-content:center;padding:80px 96px'),

    # ---- a first-time visitor must not land inside a run they never started -
    ("state: start idle, not mid-run",
     "state = { screen: 'welcome', running: true,",
     "state = { screen: 'welcome', running: false,"),

    # ---- title + keep it out of search ------------------------------------
    # ---- the flowchart is a fixed 1308px canvas; below ~1360px the census
    # node and the gate's yes-branch clipped with no way to scroll to them.
    ("workflow: let the fixed 1308px canvas scroll instead of clipping",
     '<sc-if value="{{ onFlow }}" hint-placeholder-val="{{ false }}">\n'
     '  <div style="padding:26px 26px 34px">',
     '<sc-if value="{{ onFlow }}" hint-placeholder-val="{{ false }}">\n'
     '  <div style="padding:26px 26px 34px;overflow-x:auto">'),

    ('head: real <title> and noindex',
     '<meta name="viewport" content="width=device-width, initial-scale=1">',
     '<meta name="viewport" content="width=device-width, initial-scale=1">\n'
     '<title>AAU Research Tracker</title>\n'
     '<meta name="robots" content="noindex, nofollow">'),
]

# Applied everywhere they occur, not once.
GLOBAL_PATCHES = [
    # Meta grey was 4.47:1 on white -- just under the 4.5:1 WCAG AA floor --
    # and it carries nearly every caption in the product at 12.5-14px. #63736A
    # is 5.01:1 on white and 4.62:1 on the page grey: the smallest change that
    # passes, and indistinguishable side by side.
    ("contrast: meta grey #6B7B71 -> #63736A (4.47:1 -> 5.01:1)",
     "#6B7B71", "#63736A"),
]

# The "Powered by [Elsevier Scopus]" badge on the welcome screen. Removed by
# regex because the img carries a bundle uuid that changes between builds. The
# second, identical lockup labelled "Data sources" on the Workflow screen is
# real attribution and is deliberately kept.
POWERED_BY = re.compile(
    r'\n    <div data-fade="" style="animation-delay:\.6s;[^"]*">\s*'
    r'<span[^>]*>Powered by</span>\s*'
    r'<img src="[0-9a-f-]{36}" alt="Elsevier Scopus"[^>]*>\s*</div>')


def apply_patches(tpl, live=False):
    applied = []
    for name, old, new in PATCHES:
        n = tpl.count(old)
        if n != 1:
            raise SystemExit(
                "patch %r matched %d times, expected exactly 1.\n"
                "The bundle changed -- re-check the patch against the source."
                % (name, n))
        tpl = tpl.replace(old, new)
        applied.append(name)

    for name, old, new in GLOBAL_PATCHES:
        n = tpl.count(old)
        if not n:
            raise SystemExit("global patch %r matched nothing" % name)
        tpl = tpl.replace(old, new)
        applied.append("%s  (x%d)" % (name, n))

    for name, old, new in PL.PATCHES + PL.ROUND2 + [PL.BANNER_PATCH]:
        n = tpl.count(old)
        if n != 1:
            raise SystemExit("live patch %r matched %d times, expected 1"
                             % (name, n))
        tpl = tpl.replace(old, new)
        applied.append(name)

    # data bridge in module scope, where the three constants are visible
    anchor = "class Component extends DCLogic {"
    assert tpl.count(anchor) == 1
    tpl = tpl.replace(anchor, PL.APPLY + anchor)
    applied.append("live: mutate the data constants in place")

    # ask the engine for real figures once React has mounted
    st = ("state = { screen: 'welcome', running: false, sched: true, day: 1, "
          "college: null, review: false, author: 'tkhayneh' };")
    assert tpl.count(st) == 1
    tpl = tpl.replace(st, st.replace("author: 'tkhayneh' }",
                                     "author: null, q: '', tag: 'all', "
                                     "program: null }")
                      + "\n" + PL.MOUNT)
    applied.append("live: load real data on mount")

    # extra view-model keys. Injected LAST inside the returned object so the
    # keys here win over the shorthand ones above them.
    tail = "      toggleSched: () => this.setState(s => ({ sched: !s.sched })),"
    assert tpl.count(tail) == 1
    tpl = tpl.replace(tail, tail + "\n" + PL.VALS.rstrip() + "\n"
                      + "      exports: exports.map(e => Object.assign({}, e, "
                        "{ go: () => window.__AAU "
                        "&& window.__AAU.exportOne(this, e.kind) })),\n"
                      + "      candidates: candidates.map(c => Object.assign({}, c, "
                        "{ go: () => window.__AAU "
                        "&& window.__AAU.decide(this, c) })),")
    applied.append("live: handlers for exports, review and search")

    m = POWERED_BY.search(tpl)
    if not m:
        raise SystemExit("powered-by badge not found")
    tpl = tpl[:m.start()] + tpl[m.end():]
    applied.append("welcome: remove the Powered-by Scopus badge")

    # Always injected. It degrades on its own: no engine answering means the
    # baked-in sample stays and the badge says "sample data".
    tpl = inject_live(tpl)
    applied.append("live: the bridge (live.js)")
    return tpl, applied


LIVE_HOOK = open(os.path.join(HERE, "live.js")).read() \
    if os.path.exists(os.path.join(HERE, "live.js")) else ""


def inject_live(tpl):
    """Put the bridge in the document as its OWN script tag.

    It must NOT go next to `class Component`, because that class lives inside
    <script type="text/x-dc">. Nesting a <script> there means the bridge's own
    </script> closes the component block early and the page dies -- which is
    exactly what happened the first time. So the bridge goes immediately before
    that block, and only the tiny module-scope shim (patches_live.APPLY, no
    tags) goes inside it.
    """
    if not LIVE_HOOK:
        raise SystemExit("live.js is missing next to build.py")
    anchor = '<script type="text/x-dc"'
    assert tpl.count(anchor) == 1, "expected exactly one x-dc script block"
    return tpl.replace(anchor, LIVE_HOOK.strip() + "\n" + anchor)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--live", action="store_true",
                    help="build the version that talks to the local engine")
    ap.add_argument("--out", default=OUT)
    ap.add_argument("--check", action="store_true",
                    help="verify the patches apply; write nothing")
    a = ap.parse_args()

    lines = open(SRC, encoding="utf-8").read().split("\n")
    tpl = json.loads(lines[TPL_LINE])
    if encode(tpl) != lines[TPL_LINE]:
        raise SystemExit("encoder is not byte-identical to the bundler -- stop")

    tpl, applied = apply_patches(tpl, live=a.live)

    # gates: the things that must be true of every build
    assert "Powered by" not in tpl
    assert tpl.count("Elsevier Scopus") == 1          # the Data-sources one
    assert "localhost:8765" not in tpl
    assert "papers in the census' }" not in tpl.split("welcomeChips")[1][:200]
    assert "running: false" in tpl

    lines[TPL_LINE] = encode(tpl)
    out = "\n".join(lines).replace("<title>Bundled Page</title>",
                                   "<title>AAU Research Tracker</title>", 1)
    json.loads(out.split("\n")[TPL_LINE])            # must re-parse

    for name in applied:
        print("  + %s" % name)
    if a.check:
        print("\n  check only -- nothing written")
        return
    os.makedirs(os.path.dirname(a.out), exist_ok=True)
    open(a.out, "w", encoding="utf-8").write(out)
    print("\n  wrote %s  (%d bytes)" % (a.out, len(out.encode())))


if __name__ == "__main__":
    main()
