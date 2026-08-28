# AAU Research Tracker — checkpoint, 28 Aug 2026

    page   https://abdallahabouhajal.github.io/aau-research-tracker/
    repo   https://github.com/AbdallahAbouHajal/aau-research-tracker
    proxy  https://aau-tracker-run.abouhajal.workers.dev
    local  ~/Downloads/AAU_Tracker_Site      (interface + build + engine/ that CI runs)
           ~/Downloads/AAU_Research_Tracker  (master copy of the engine, kept in sync by hand)

Everything below is SHIPPED AND LIVE unless it says otherwise.

## The one thing in flight

**Mobile.** Abdallah asked for the site to be genuinely usable on a phone. He
does NOT want a third-party library vendored into the page — he wants the
technique researched online first, learned, then applied by hand. That
distinction matters to him; do not vendor a framework.

A Workflow was auditing all nine screens when the session ended:
`wf_4eb1fee8-46e`, script at
`~/.claude/projects/-Users-abdallahabouhajal-Downloads-AAU-Tracker-Site/b6efd401-.../workflows/scripts/aau-mobile-audit-wf_4eb1fee8-46e.js`
Five auditors (tables, fixed canvases, chrome, viewport decision, dashboard+net)
each returning exact inline-style substrings and the media-query rule that
fixes them, then one agent synthesising a single stylesheet. Resume with
`Workflow({scriptPath: ..., resumeFromRunId: 'wf_4eb1fee8-46e'})` — completed
agents replay from cache.

The open decision it was settling: keep `<meta name="viewport" content="width=1180">`
(everything visible, small, zoomable — what ships today) or move to
`width=device-width` and reflow properly. Decide on the audit's evidence.

Verify any mobile work with headless screenshots at 390 / 430 / 834 / 1440.
Desktop at 1280+ must not change.

## What the app now is

Seven screens plus two added today: **Papers** (every paper in the run, its own
~950KB file fetched on open) and **Collaboration and Network** (who AAU
publishes with). Each researcher's page carries a **co-author wheel** built
from our own papers.

Live figures on the 2021-2026 window: 4,285 papers, 556 authors, 213 roster
people, 8 colleges, 51 programmes.

## Facts that must not regress

- **Scopus author ids come from AAU's own directory.** Each directory card
  prints `authorId=`. 141 ids, verified to resolve before being stored, and
  they outrank every matcher — 7 of the matcher's guesses were wrong, including
  Niazur Rahman, who had been bound to a chemist at the University of Nizwa.
  An id is refused only when Scopus has no such author (Shirin AlAmoor's card
  drops a digit), never for having few AAU papers.
- **Programme membership comes from `data/programme_index.csv`** — the index
  Abdallah exported alongside his screenshots of every college x programme.
  It is used EXCLUSIVELY, not unioned: a union puts back the rows it corrects.
  `sync_roster.py --check` verifies all 355 (person, programme) pairs plus
  name/college/scopus/scholar, 209 agree 0 disagree, and exits non-zero if not.
  Re-run `python3 sync_roster.py` after any CSV changes.
- **The directory's programme filter does not work over HTTP.** `?program=47`
  and `?program=5` differ by six bytes — which `<option>` is `selected` — and
  both list the whole college. It filters in a browser only. Do not re-walk this.
- **Institutions per paper come from `/content/abstract/scopus_id/<id>?view=META`.**
  The Search API reports ONE affiliation per paper; META gives the true list
  (measured: 1,1,1,1,1,1,1,1 vs 4,1,1,5,3,4,1,14). It truncates the AUTHOR list,
  which is why co-author names are still unavailable and the wheel is AAU-only.
- **Consortium papers are quarantined at >25 institutions.** 18 of them carry
  81% of all institution pairs; left in they decide every ranking.
- **AAU has EIGHT colleges.** Count from the roster, never from who has papers.

## The traps this project keeps re-hitting

1. Re-encode the bundle exactly: `json.dumps(t, ensure_ascii=False).replace("</", "<\\u002F")`.
2. Handlers must be `sc-camel-on-click`. Raw `onClick` lowercases and never binds.
3. **Never** set `min-height` on the shell div — every `data-rise` child sticks
   at opacity:0 and the app renders invisible.
4. The runtime does NOT interpolate text nodes inside `<svg>`, only attributes.
   Every SVG label is an HTML overlay. The donut and the co-author wheel both
   depend on this.
5. **Verify every build with a headless screenshot.** ~25KB = blank, ~97KB+ =
   rendered. A schedule patch once replaced 3 of 4 literals, made a double
   ternary, and blanked the page while `node --check` and the patch log both
   said success.
6. Patch ORDER matters: a patch whose anchor is created by a later patch matches
   zero times. Place it after the one that creates its anchor.
7. `actions/upload-artifact` silently skips hidden files. The census/institutions
   hand-off is `engine/handoff.json`, not `.handoff.json`, for exactly this.

## How a run works now

Two jobs. **refresh** publishes the whole census in ~50s. **institutions** then
reads every paper's institution list and republishes `network.json` at each
quarter, so the Collaboration screen fills in visibly. A window nobody has asked
for costs ~20 minutes there; a repeat is seconds, because the answers are cached
and `actions/cache` restores them. `full_affiliations: false` skips it.

`fill_institutions.py` REFUSES to publish coverage lower than what is already
published, and exits non-zero. It once wrote 0 partners over 1,723 because the
hand-off wrote `sid` where the reader wanted `scopus_id`.

## Still open

- Mobile (above).
- The proxy still holds Abdallah's `gh` CLI OAuth token, which reaches all his
  repos. Swap it for a fine-grained PAT scoped to `aau-research-tracker` with
  Actions: Read and write. He has been told.
- Tell him to delete `~/Downloads/PASTE_INTO_GITHUB_SCOPUS_KEYS.json`.
- Six people still need a decision on the Review screen; the directory publishes
  no id for them.
- 11 of 165 academics carry no programme, confirmed by the browser pass to be
  AAU's own gap, not ours.
