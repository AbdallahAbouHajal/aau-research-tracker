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

The published page has no engine behind it, so it shows the sample figures and
says so in a badge. That is deliberate: named colleagues with silently stale
numbers is the worse failure.

## Still open

- Chrome extension is unpaired (this CLI signed into a different claude.ai
  account), so the last builds were verified by `node --check` and by structural
  assertions, not by eye. Worth one visual pass.
- `College of Dentistry` shows 0 people: its three staff have no Scopus record
  in the window, which is correct but looks empty.
- Docker image is written but unbuilt — no docker on this machine to test it.
