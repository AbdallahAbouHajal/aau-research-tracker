# AAU Research Tracker — UI mockup handoff

Everything a developer needs to rebuild this interface exactly.

## What is in this folder

    AAU Research Tracker UI (standalone).html   The whole mockup in ONE file.
                                                Open it in any browser. No server,
                                                no internet, no build step. Images
                                                and fonts are already inlined.

    source/AAU Research Tracker UI.dc.html      The authored source: template first,
                                                then the logic class at the bottom.
                                                Read this to see the real markup and
                                                the real inline styles.

    source/support.js                           Runtime that renders the source file.

    assets/aau-logo.png                         Al Ain University logo
    assets/scopus-mark.png                      Scopus square mark
    assets/scopus-elsevier.png                  Elsevier Scopus lockup

## Screens

1. Welcome        Full-bleed AAU green, logo, what the app does, three figures,
                  one button into the app. This is the landing state.
2. Dashboard      Three figures, six-stage run panel with live progress,
                  findings in plain sentences, donut of papers by college,
                  delta since the last run.
3. Roster         Step one: eight college cards. Step two: that college's authors
                  with a link to their aau.ac.ae profile. Review queue behind the
                  red button (8 names need a decision).
4. Authors        Searchable list of 511 people, filters, detail panel with career
                  figures, staff profile link, Scopus author id, and their papers.
5. Exports        Workbook, slide deck, chart pack. All three enabled.
6. Schedule       Weekly toggle, day picker, next four runs, health list,
                  college-map decisions.
7. Workflow       Animated flowchart: two sources, name matching, two collection
                  routes, the affiliation gate as a decision diamond with yes/no
                  branches, the census, and the output files.

## Design tokens actually used

    Font            Archivo (400, 500, 600, 700, 800) from Google Fonts
    AAU green       #0A7A3A   primary, headers, bars, buttons
    Bright green    #0FA64F   emphasis
    Deep green      #14563A   secondary chart series
    AAU red         #E0303F   the gate, rejections, alerts
    Scopus orange   #F27524   the Scopus source lane only
    Ink             #1A1A1A   body text
    Meta grey       #6B7B71   captions, secondary text
    Page grey       #F4F6F5   app background
    Desk grey       #E9EDEA   outside the window
    Card white      #ffffff
    Hairline        #F0F3F1   row dividers
    Border          #E4EAE6 / #D5DED8
    Radius          8px cards, 6px buttons, 5px chips
    Shell width     1392px, min 1180px, horizontal scroll below that
    Flowchart       fixed 1308 x 450 canvas, absolute node positions

## Animations

    uiRise      cards and rows lift in, 0.42s, staggered by 0.04-0.06s
    uiBar       bars scale from the left, 0.7s
    uiArc       donut arcs draw by stroke-dashoffset, 1.1s
    uiSweep     a light band crosses the active progress bar, 1.6s loop
    uiSpin      the run spinner, 1s loop
    uiBlink     the live dot beside "what it has found so far", 1.4s loop
    flowDash    travelling dashes along every flowchart connector, 1.15s loop
    flowPop     flowchart nodes lift in, staggered by 0.08s

## Notes for the rebuild

- The state machine is small: screen, running, sched, day, college, review, author.
  It is all in the logic class at the bottom of the source file.
- Every style is inline in the source. There is no stylesheet to port.
- The mockup shows figures from run 20260827-010252: 1,336 papers, 511 people,
  161 faculty, 152 of 160 academics resolved, 8 needing a decision, 67 rejected.
- Two-step roster and the yes/no gate are the two interactions worth preserving.
