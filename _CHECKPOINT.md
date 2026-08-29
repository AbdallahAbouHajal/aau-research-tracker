# AAU Research Tracker — checkpoint, 29 Aug 2026

    page   https://abdallahabouhajal.github.io/aau-research-tracker/
    repo   https://github.com/AbdallahAbouHajal/aau-research-tracker
    proxy  https://aau-tracker-run.abouhajal.workers.dev
    local  ~/Downloads/AAU_Tracker_Site      (interface + build + engine/ that CI runs)
           ~/Downloads/AAU_Research_Tracker  (master copy of the engine, kept in sync by hand)

Everything below is SHIPPED AND LIVE unless it says otherwise.

## Nothing is in flight

Mobile is done — reflow by hand, no library vendored (Abdallah asked for the
technique to be researched and applied, not for a framework to be dropped in;
that distinction matters to him). Verified at 500 / 834 / 1440: no horizontal
scroll, no tap target under 36px, no text under 11px, on all nine screens.

## The page keeps itself current — and there are TWO publishers

It no longer needs a reload. `live.js` HEADs `data/state.json` **and**
`data/network.json` every 60s while the tab is visible, and immediately when
the tab is re-shown.

Why both: the census job writes state/papers/network together, then the
institutions job writes **`network.json` alone** for ~20 minutes, never
touching state.json. Watching only state.json misses every collaboration
checkpoint. Confirmed in the history — "Census refresh" touches three files,
both "Institutions read" commits touch one.

Three things that must stay true:

1. **Decide on `generated`, not the ETag.** The tag is a hint; the stamp is
   what stops the page mistaking its own refresh for a run. An earlier draft
   re-baselined the tag after each refresh and silently lost any run landing
   in the gap.
2. **Drop the lazy cache when the data moves.** `papers.json`/`network.json`
   are held for the life of the page. Nothing cleared them, so after a
   2025-26 run the Papers screen still showed the previous window's 4,285
   rows next to a Dashboard reading 522.
3. **Cache-bust each file with ITS OWN publisher's stamp.** Pages sends
   `max-age=600`; stamping network.json with the census stamp gave two
   different files one URL.

The reader is never moved — figures change underneath them and the badge says
why. Only a run started in that tab switches screens.

## What the app now is

Nine screens. **Papers** (every paper in the run, its own file fetched on
open) and **Collaboration and Network** (who AAU publishes with); each
researcher's page carries a **co-author wheel** built from our own papers.

The **Dashboard is three levels** — eight college cards, then that college's
programmes, then one programme — with the **run panel BELOW the figures** and
a prompt pointing down at it. The **Roster is a joined list**, deliberately
unlike the Dashboard's grid: its rail is vertical where the Dashboard's is
horizontal, its hero number is people where the Dashboard's is papers, and its
eight bars grow in unison where the Dashboard's cards cascade. Each college
carries an emoji mark, defined once in `live.js` (`collegeIcon`).

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

## Numbers that must never be printed

- **`staff`** is the sum of per-programme tag counts, so a person on three
  programmes is counted three times — it reads **83 for a college of 44
  people**. Papers-per-person divides by `people`.
- **Never roll programme figures up to a college by summing them**: 51
  programmes sum to 6,904 papers against the 3,606 the eight colleges hold.
- The two dashboard levels divide by different populations — a college by its
  roster, a programme by the staff AAU tags to it — so each ratio carries its
  denominator on hover. A programme reading 115 papers/person is usually
  right (3 tagged people, all career h-index > 30), not a fault.

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

### Two more, learned 29-Aug

- **An element already carrying one bare `data-` attribute silently loses a
  second.** `<div data-rise data-run-panel …>` arrives as `data-rise` alone:
  the patch applies, matches once, and the CSS rule matches nothing. Hook a
  sibling instead. (Two bare attributes on a `<button>` do survive — probe
  the DOM, don't assume either way.)
- **`VALS` is one flat object literal, so a repeated key silently wins.** It
  has cost twice: `progNote` broke the Roster's caption, and a second
  `backToColleges` killed the Roster's back button while looking correct.
  `grep -c "yourKey:" patches_live.py` before adding one.
- **`animation-fill-mode: both` freezes `transform`** and outranks both the
  rule and the inline style, so any `:hover { transform }` dies silently.
  Card animations use `backwards`.

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

- The proxy still holds Abdallah's `gh` CLI OAuth token, which reaches all his
  repos. Swap it for a fine-grained PAT scoped to `aau-research-tracker` with
  Actions: Read and write. He has been told.
- Six people still need a decision on the Review screen; the directory publishes
  no id for them.
- 11 of 165 academics carry no programme, confirmed by the browser pass to be
  AAU's own gap, not ours.
