# AAU Research Tracker — checkpoint

Two folders, one product:

    ~/Downloads/AAU_Tracker_Site/       the interface (design + build + deploy + engine copy)
    ~/Downloads/AAU_Research_Tracker/   the engine (Scopus, roster, census) — the master copy

    live      https://abdallahabouhajal.github.io/aau-research-tracker/
    repo      https://github.com/AbdallahAbouHajal/aau-research-tracker

## Run it locally

    cd ~/Downloads/AAU_Research_Tracker
    open "Launch AAU Tracker.command"        # or /usr/bin/python3 app.py

## Run it on GitHub

Actions → **Refresh the census** → Run workflow. Or the page's own **Run now**,
which dispatches the same workflow (needs a token — see below).
Schedule: `0 3 * * 1` = **Mondays 03:00 UTC = 07:00 Gulf**. Workflow state is
`active`; the first scheduled firing is Mon 31 Aug 2026 (every run so far was
manual). GitHub disables cron on repos with no pushes for 60 days.

Timing, measured on the runner: was 13.7 min, of which "Find each person in
Scopus" was 638 s. Those 38 profile lookups are now marked `profile_checked` in
`engine/data/roster.json` and skipped, so **a run is ~3 min**. Pass
`force_profiles` to recheck them.

---

# OPEN — the bug being chased when this checkpoint was written

**Everything the published page derives from a run's `slots` is empty when the
run happens on GitHub.** On the deployed `docs/data/state.json`
(`source: github-actions`, generated 08:07Z):

    papers map keys : 0        -> the Authors screen's paper table renders nothing
    every college   : papers 0 -> the donut is one flat ring
    people counts   : correct  -> those come from the roster, not slots
    stats.papers    : 1338     -> correct, comes from the run's stats blob

Locally the same code gives 12 papers for Tabash and 325/303/274/… per college,
and a node harness on the built page returns 12 paper rows. So the code path is
right and something about the CI run's saved blob is not.

**Chain to check, in order:**
1. `run_stage.py` stage 5 sets `b["slots"]` (~30k rows) and writes
   `AAU_STAGE_FILE` (`engine/.stage.json`). Check it was written whole.
2. Stage 6 reads it back, calls `RUNS.roster(b["slots"])`, then
   `RUNS.save(rid, {... "slots": …, "roster": …})`.
3. `runs.results()` builds the college rollup from `b["roster"]` — **not** from
   slots. An empty roster gives 0 papers everywhere.
4. `viewmodel._papers_from_run(run_id)` reads `blob["slots"]` keyed on
   `scopus_auid` (it read `auid` once; that bug is fixed).

Fastest next step: print `len(b["slots"])` in stage 5 and `len(roster)` in
stage 6, run the workflow, read the log. If slots survive stage 5 but the
roster is empty, the fault is in `RUNS.roster` under CI conditions.

# OPEN — the rest of the current request

- **The dashboard mixes live tiles with mockup text.** "No run yet" sits above
  "27 August at 01:06 · took 5 minutes 20 seconds", six green "Done" bars, and
  findings quoting 1,336 / 511 / 161 / 67 while the tiles say 1,338 / 536 / 169.
  Fix `runTitle`, `runMeta`, the idle stage state, `findings` (read
  `window.__AAU.state.findings` — already populated) and "SINCE THE LAST RUN"
  (read `window.__AAU.state.delta`).
- **Donut centre still reads 1,351**; the real sum is 1,294. Make it live.
- **Header chips** "Window 2025–2026" / "Roster 2026-08-27" are hardcoded.
- **`__` placeholders during a run** (requested): blank every figure whose
  producing stage has not finished, fill as stages complete. Stage → figure:
  1 roster_people · 2 resolved/review · 3 window papers · 4 swept_in/rejected/
  papers · 5 authors/faculty/colleges · 6 delta/suggestions.
  NOTE: GitHub exposes step *status*, not intermediate numbers, so on the
  published page the figures land together at the end. The local app can fill
  progressively because `/api/run/status` carries partial stats.
- **Staff profile link** must open a new tab (`source` line 385, an `<a>`).
- **"Show all"** on the papers table has no handler.
- Workflow `wf_bb46d4f6-1ec` was finding exact patch anchors for these; journal
  at `subagents/workflows/wf_bb46d4f6-1ec/journal.jsonl`.

# OPEN — the professor cannot run it, and has no GitHub account

A public static page cannot hold a credential: anything embedded is public, so
only someone with a GitHub token can press Run now. The reader is now shown
"this updates itself every Monday" instead of a token form.

**If he must be able to trigger it: a tiny free proxy.** A Cloudflare Worker
(or Vercel function) holding the GitHub token as a secret plus a shared
passphrase. The page asks for the passphrase, the Worker checks it and calls
GitHub. He needs no GitHub account and installs nothing. One free Cloudflare
account and ~30 lines. Not built yet — awaiting the go-ahead.

---

## How the interface stays exactly as designed

`build.py` applies **named patches** to an untouched copy of the Claude Design
bundle; `patches_live.py` holds the ones that make it functional. Nothing is
edited in place, so the design cannot drift. `python3 build.py --check` verifies
without writing.

**Three traps, each hit at least once:**

1. **Re-encoding.** The real page is a JSON string on line 382 and must be
   written back exactly:
   `json.dumps(t, ensure_ascii=False).replace("</", "<\\u002F")`.
   `ensure_ascii=False` (em-dashes ship raw) and the `</` escape (an inner
   `</script>` closes the host tag early). `encode()` asserts itself
   byte-identical against the pristine original before any patch runs.
2. **Where the bridge goes.** `live.js` must be injected *before*
   `<script type="text/x-dc">`, never beside `class Component` — that class
   lives inside that script tag, and a nested `<script>` kills the page.
3. **`min-height` on the shell.** Setting it leaves every `data-rise` child
   stuck at the `uiRise` animation's `opacity: 0` start frame: the app lays out
   with real heights and is completely invisible. Also, this runtime renders
   each `sc-if` as its own root, so the shell only ever contains the header —
   width caps belong on the **outer wrapper**.

**Verify every build by screenshot**, not by assertions. `node --check` and DOM
assertions both passed on a page that rendered nothing:

    "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome" --headless \
      --disable-gpu --no-sandbox --window-size=1680,1000 --virtual-time-budget=10000 \
      --screenshot=/tmp/x.png "http://127.0.0.1:8899/index.html"

~25 KB = blank, ~100 KB+ = rendered.

## The engine on GitHub

`engine/` holds the whole engine, including `vendor/common.py` — the census
module that owns the AAU affiliation rule, **vendored not reimplemented**, so
the rule stays in one file. Paths and keys come from env (`AAU_DATA`,
`AAU_CACHE`, `SCOPUS_KEYS_FILE`). Verified: with `AAU_CENSUS_DIR=/nonexistent`
it still builds 536 authors and 170 settled AU-IDs from repo data alone.

**Not committed: the raw Scopus export.** A bulk export carries Elsevier
licensing terms and held emails. The Action refetches from the API. Only
derived metrics ship (`engine/data/people_metrics.json`, 133 KB, no emails).

**The commit step must never rebase.** These files are generated, not authored;
a rebase hits the guaranteed conflict on `state.json`, leaves markers and
reports success — a whole run silently discarded. It parks its output,
hard-resets onto main, restores, pushes. A final step reads `state.json` back
off main and fails loudly if the published page is not serving this run.

## Data rules that must not regress

- Match the census to the roster with `translit.compatible()`, never exact
  names. Keyed exactly, "Ghaleb A. El Refae" never meets "Ghaleb Awad El Refae"
  and 80 people match instead of 169.
- Use the roster's **real** eight colleges. AAU runs Education-and-Humanities as
  ONE college and Dentistry is real; the mockup split the first and omitted the
  second.
- Off the roster means outside faculty — the rule does not bend. But people
  publishing like staff who are missing from the roster are surfaced as
  suggestions rather than buried. That is how El Refae, the chancellor with ~50
  papers, was found filed as a student.

## Security

- The download route uses `os.path.commonpath`, not `startswith` — the latter is
  a prefix test and served `/downloads/../../docsX/secret`. Verified with a
  canary file in exactly such a sibling directory.
- The workflow passes `github.event.inputs` through `env:`, never interpolated
  into a shell command.
