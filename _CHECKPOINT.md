# AAU Research Tracker — checkpoint

Two folders, one product:

    ~/Downloads/AAU_Tracker_Site/       the interface (design + build + deploy)
    ~/Downloads/AAU_Research_Tracker/   the engine (Scopus, roster, census)

## Run it for real

    cd ~/Downloads/AAU_Research_Tracker
    open "Launch AAU Tracker.command"          # or: /usr/bin/python3 app.py

Opens `127.0.0.1:8770`. Press **Run now** and it asks what kind of run this is,
then does it. A real 2025+2026 run took **1m56s** and reported:

    1,330 papers from the university tag
    +8 found by sweeping each author that the tag had missed
    -51 thrown out: no author on them printed an Al Ain University address
    = 1,338 papers | 511 people | 1,257 faculty author-rows
    64 people published with an AAU address but are not on the roster
    2 new papers since the previous run

## How the interface stays exactly as designed

`build.py` applies **named patches** to an untouched copy of the Claude Design
bundle. Nothing is edited in place, so the design cannot drift — delete a patch
and that change is gone. `python3 build.py --check` verifies without writing.

**Editing the bundle by hand will break it.** The real page is a JSON string on
line 382 and must be re-encoded exactly:

    json.dumps(text, ensure_ascii=False).replace("</", "<\\u002F")

`ensure_ascii=False` (em-dashes ship raw) and the `</` escape (an inner
`</script>` would close the host tag early). `encode()` asserts itself
byte-identical against the pristine original before any patch is applied.

**A second trap, hit and fixed:** the bridge must NOT be injected next to
`class Component` — that class lives inside `<script type="text/x-dc">`, so a
nested `<script>` there kills the page. It goes immediately *before* that block.
`node --check` on both extracted scripts is the gate.

## What the adversarial review found (3 isolated panels, 15 objections)

Fixed:
- fake mac window chrome reading **localhost:8765** on a github.io page — gone,
  the app fills the viewport
- app booted `running: true`: a spinner stuck at "Stage 4 of 6" forever, a CSS
  animation dressed as live computation — now starts idle
- the one remaining welcome chip was `text-align:left` inside a centred row
- the 1308px flowchart canvas clipped its right edge below ~1360px with no
  scrollbar — now scrolls
- caption grey `#6B7B71` measured **4.47:1** on white, under the 4.5:1 WCAG AA
  floor, and carries nearly every caption → `#63736A` at 5.01:1
- **six controls styled exactly like working ones had no onClick at all**:
  search, the three filter chips, both export buttons, the review-queue
  decision buttons, import-roster. All wired.

## Your idea, built: "we found another one — add them?"

Every run now ends by asking who printed an AAU address but is **not** on the
roster. They appear as a banner on the Roster screen; each row offers **Add** or
**Not faculty**, and a dismissal sticks (`data/not_faculty.json`).

This came out of a real error: **Ghaleb El Refae, AAU's chancellor, ~50 papers,
was filed as "student or external"** purely because the directory scrape missed
him. The rule does not bend — off the roster means outside faculty — but the
omission is now put in front of you instead of quietly standing.

## Data plumbing

`core/viewmodel.py` turns the census into the three constants the interface
already reads (COLLEGE_DATA / AUTHORS / PAPERS). The bridge mutates those arrays
**in place** — the binding is const, the contents are not — then re-renders. No
style is touched.

Two things it must keep doing:
- match the census to the roster with `translit.compatible()`, not exact names.
  Keyed on the exact name, "Ghaleb A. El Refae" never meets roster "Ghaleb Awad
  El Refae" and 80 people match instead of 169.
- use the roster's **real** eight colleges, not the mockup's. AAU runs
  Education-and-Humanities as ONE college and Dentistry is real; the mockup split
  the first and omitted the second.

## Live

    interface preview  https://abdallahabouhajal.github.io/aau-research-tracker/
    repo               https://github.com/AbdallahAbouHajal/aau-research-tracker

The published page shows **real data** -- 1,338 papers, 536 authors, 14
suggested additions -- read from `docs/data/state.json`, which the engine wrote.
The badge names the date it was generated, so nobody mistakes last Monday's
figures for this minute's.

## The engine on GitHub

Pages serves files, not processes, so the engine cannot listen on the published
site. It does not need to: it RUNS on GitHub Actions, on GitHub's machines.

    .github/workflows/refresh.yml   Monday 03:00 UTC + "Run workflow" on demand
    engine/                         the whole engine, vendored
    docs/data/state.json            what it wrote last time -- the page reads this

**One thing is needed before the Action can run:** add a repository secret
`SCOPUS_KEYS` (Settings > Secrets and variables > Actions) holding the keys as a
JSON array, e.g. `["<32 hex>", "<32 hex>", ...]`. Keys are never committed; the
workflow writes them to a temp file and deletes it before pushing.

`engine/vendor/common.py` is the census module that owns the AAU affiliation
rule -- **vendored, not reimplemented**, so the rule that decides who counts as
AAU still lives in exactly one file. Paths and keys come from env
(`AAU_DATA`, `AAU_CACHE`, `SCOPUS_KEYS_FILE`), so the same code runs on a
laptop and on a runner. Verified: with `AAU_CENSUS_DIR=/nonexistent` the engine
still builds 536 authors and 170 settled AU-IDs from repo data alone.

**Deliberately not committed: the raw Scopus export.** A bulk export carries
Elsevier licensing terms and contained emails. The Action refetches from the
API, which is what the keys license. Only derived metrics ship
(`engine/data/people_metrics.json`, 133 KB, no emails).

## The blank-screen bug, and how it was found

Every tab except Welcome rendered blank. Three things made it hard: the markup
was balanced, `renderVals()` returned cleanly for all seven screens under a node
harness, and the content was present in the DOM with real element heights.

It was invisible, not missing. `min-height:100vh` on the shell div leaves every
`data-rise` child stuck on the `uiRise` animation's `opacity: 0` start frame --
the dc-runtime does its own min-height bookkeeping on that element. Found by
bisecting the ten UI patches one at a time with headless Chrome screenshots
(`--screenshot`, file size as the signal: ~25 KB blank vs ~99 KB rendered).

Two rules came out of it:
- **Never set min-height on the shell div.** Full height goes on the outer
  wrapper.
- **Screenshot every build.** `node --check` and DOM assertions both passed on a
  page that was completely invisible.

## Still open

- The `SCOPUS_KEYS` secret is not set yet, so the Action cannot run until it is.
- Chrome extension is unpaired (this CLI signed into a different claude.ai
  account); builds are verified with headless Chrome screenshots instead, which
  is what caught the blank-screen bug.
- `College of Dentistry` shows 0 people: its three staff have no Scopus record
  in the window, which is correct but looks empty.
- Docker image is written but unbuilt — no docker on this machine to test it.
