"""Patches that make the interface functional.

The design is not touched. Every patch here either hands a control a handler it
never had, or lets real data reach a constant the interface already reads. The
adversarial UI review found six controls styled exactly like working ones that
had no onClick at all -- search, the filter chips, both export buttons, the
review-queue decision buttons, import-roster and edit-the-map. Those are the
work list.
"""

# ---------------------------------------------------------------- data bridge
# COLLEGE_DATA / AUTHORS / PAPERS are module-level consts. The BINDING is
# const; the CONTENTS are not. Mutating them in place is what lets real data
# arrive after mount without rewriting a single line of the interface.
APPLY = r"""
window.__aauApply = function (d) {
  if (d && d.colleges) {
    COLLEGE_DATA.length = 0;
    d.colleges.forEach(function (c) { COLLEGE_DATA.push(c); });
  }
  if (d && d.authors) {
    AUTHORS.length = 0;
    d.authors.forEach(function (a) { AUTHORS.push(a); });
  }
  if (d && d.papers) {
    Object.keys(PAPERS).forEach(function (k) { delete PAPERS[k]; });
    Object.assign(PAPERS, d.papers);
  }
  if (d && d.programs) {
    PROGRAMS.length = 0;
    d.programs.forEach(function (p) { PROGRAMS.push(p); });
  }
  if (d && d.review) {
    REVIEW.length = 0;
    d.review.forEach(function (r) { REVIEW.push(r); });
  }
};

// The two lazy files land here, each replacing its constant in place so the
// screen re-renders against real data without the page reloading.
window.__aauNetwork = function (d) {
  Object.keys(NETWORK).forEach(function (k) { delete NETWORK[k]; });
  Object.assign(NETWORK, d || {});
};
window.__aauCorpus = function (d) {
  CORPUS.length = 0;
  ((d && d.papers) || []).forEach(function (r) { CORPUS.push(r); });
};

"""

MOUNT = r"""
  componentDidMount() {
    // Ask the local engine for real figures. If nothing answers -- the page is
    // on GitHub Pages, or the app is not running -- the baked-in sample stays
    // and the badge says so, because showing stale numbers for named
    // colleagues without saying they are stale is the worse failure.
    var self = this;
    if (!window.__AAU) return;
    window.__AAU.refresh(self).then(function () {
      // Then keep asking. A run started on a phone, the Monday schedule, or
      // this reader's own run after they navigated away all used to leave
      // the page on old numbers with no sign anything had happened.
      if (window.__AAU.watchForNewData) window.__AAU.watchForNewData(self);
    }).catch(function () {
      window.__AAU.badge('sample data · engine not running', '#63736A');
      self.setState({ demo: true });
    });
  }
"""

MOBILE_CSS = r'''
/* ---- the Roster's joined list ------------------------------------------
   dub's card list has a "compact" variant where the rows share borders and
   only the ends are rounded, so a directory reads as one surface rather than
   as scattered cards. That is what tells this screen apart from the
   Dashboard's board of figures. */
[data-roster-row]:first-of-type {
  border-top-left-radius: 12px; border-top-right-radius: 12px;
}
[data-roster-row]:last-of-type {
  border-bottom-left-radius: 12px; border-bottom-right-radius: 12px;
  border-bottom: 1px solid #E4EAE6 !important;
}
[data-roster-row] {
  transition: background-color .15s cubic-bezier(.16, 1, .3, 1);
}
[data-roster-row]:hover { background: #FAFBFA !important; }
[data-roster-row]:focus-visible {
  outline: 2px solid #0A7A3A; outline-offset: -2px; position: relative;
}
@media (max-width: 834px) {
  [data-roster-row] {
    grid-template-columns: 3px 1fr 22px !important;
    row-gap: 6px !important;
  }
  [data-roster-row] > *:nth-child(n+3):nth-child(-n+4) {
    grid-column: 2 !important;
  }
}

/* ---- cards you can open ------------------------------------------------
   Values read off dub's production dashboard (dubinc/dub, 24.6k stars):
   packages/tailwind-config/tailwind.config.ts defines its card hover as
   drop-shadow "0 2px 4px #222A350d" -- five percent alpha -- and its cards as
   `border rounded-xl` with `hover:bg-neutral-50`. Not a glow, not a lift of
   six pixels: a one-pixel rise and a shadow you notice only when it is gone.
   The easing is theirs too, cubic-bezier(0.16, 1, 0.3, 1), the curve they use
   for every slide and scale in the product.
   Filter is animated rather than box-shadow: it does not force layout. */
[data-open-card] {
  transition: background-color .18s cubic-bezier(.16, 1, .3, 1),
              border-color .18s cubic-bezier(.16, 1, .3, 1),
              filter .18s cubic-bezier(.16, 1, .3, 1),
              transform .18s cubic-bezier(.16, 1, .3, 1);
}
@media (hover: hover) and (pointer: fine) {
  [data-open-card]:hover {
    background: #FAFBFA !important;
    border-color: #C3D6CA !important;
    filter: drop-shadow(0 2px 4px #222A350d);
    transform: translateY(-1px);
  }
  /* The rail is the discriminator between the two screens: the Dashboard's
     runs along the TOP and grows sideways, the Roster's runs down the LEFT
     and grows downward. One axis, and the eye tells the screens apart
     before it has read a word. */
  [data-open-card]:hover [data-rail] { transform: scaleX(1); }
  [data-roster-row]:hover [data-rail-v] { transform: scaleY(1); }
  [data-roster-row]:hover { background: #FAFBFA !important; }
}
/* Press is ungated -- a touch device has no hover but it does have :active,
   and it is the only feedback a finger gets. Faster down than up. */
[data-open-card]:active { transform: scale(.985); filter: none;
                          transition-duration: .09s; }
[data-open-card]:focus-visible {
  outline: 2px solid #0A7A3A; outline-offset: 2px;
}

/* The page animates on every mount and nothing asked whether that was
   wanted. This is the one guard the sheet was missing. */
@media (prefers-reduced-motion: reduce) {
  [data-rise], [data-rise-card], [data-fade], [data-bar], [data-bar-sm],
  [data-arc], [data-node], [data-step], [data-open-card] {
    animation: none !important; transition: none !important;
    opacity: 1 !important; transform: none !important;
  }
  /* resolves to a FULL rail, which is the right resting state, not a stub */
  [data-rail], [data-rail-v] { transform: none !important; }
  [data-flow], [data-drop], [data-sweep], [data-dash] { animation: none !important; }
  /* [data-spin] and [data-blink] deliberately survive: they are the only
     evidence on screen that a Scopus sweep is still running. Switching them
     off would make a working run look like a hung one. */
}

/* ---- motion ------------------------------------------------------------
   `backwards`, never `both`. An animation declaration outranks the CSS rule
   AND the inline style, so a `both` fill freezes transform at the end frame
   and the hover lift below silently stops working. [data-rise] gets away
   with it only because it sits on a wrapper; these sit on the cards. */
@keyframes uiFwd  { from { opacity: 0; transform: translateX(14px); } }
@keyframes uiBack { from { opacity: 0; transform: translateX(-14px); } }
[data-step="fwd"]  { animation: uiFwd  .24s cubic-bezier(0, 0, .38, .9) backwards; }
[data-step="back"] { animation: uiBack .24s cubic-bezier(0, 0, .38, .9) backwards; }
[data-rise-card] { animation: uiRise .42s cubic-bezier(.22, .7, .2, 1) backwards; }
[data-bar-sm] { animation: uiBar .34s cubic-bezier(.2, 0, .38, .9) backwards;
                transform-origin: left center; }
[data-rail], [data-rail-v] { transition: transform .22s cubic-bezier(.16, 1, .3, 1); }
[data-roster-row] { transition: background-color .18s cubic-bezier(.16, 1, .3, 1); }
/* state the outer edge once; keep the interior hairlines */
[data-roster-row]:not(:first-of-type) { border-top-color: #F0F3F1 !important; }
/* the six detail tiles, onto the same weight ramp as everything else */
[style*="font-size: 25px"][style*="font-variant-numeric: tabular-nums"] {
  font-weight: 600 !important; letter-spacing: -.03em !important;
}

/* Mobile. Read this first, it will save you the afternoon it cost me.

   THE SELECTORS HERE MATCH THE DOM'S SPELLING, NOT THE SOURCE'S. Every style
   in this page is an inline attribute, and the runtime re-serialises those
   attributes when it hydrates: `min-width:1180px` in patches_live.py becomes
   `min-width: 1180px` in the live DOM, `0` becomes `0px`, and
   `repeat(3,minmax(0,1fr))` becomes `repeat(3, minmax(0px, 1fr))`. A selector
   written the way the source spells it matches NOTHING. Both spellings are
   listed below so this cannot silently rot again; verify any new rule against
   the real DOM, never against patches_live.py.

   Overriding an inline style needs !important. That is not laziness; it is the
   only lever an inline style leaves.

   Nothing sits outside a media query. Desktop at 1281px and up is untouched.

   The viewport is width=device-width. It was width=1180, which made a phone
   fit the whole desktop page and scale it to 33%: 13px body text rendered at
   4.3px. Everything was visible and nothing was readable.

   NEVER add min-height to the shell div. Every data-rise child then sticks at
   its animation's opacity:0 start frame and the app renders blank.
*/

/* An fr column keeps an automatic minimum of its own content, so one long word
   pushes its track past its share and a row stops lining up with its header.
   True at every width, desktop included. */
[style*="display: grid"] > *, [style*="display:grid"] > * { min-width: 0; }

/* Four college tiles need ~1200px to stay readable, so they drop to three
   before the shell's own floor lifts. The band is closed at both ends on
   purpose: this selector carries two attribute matches, which outranks the
   single-match 2-up and 1-up rules below regardless of source order, and
   left open it kept the cards 3-up down to 390px.
   Selector in the DOM's spelling -- the runtime re-serialises
   `repeat(4,minmax(0,1fr))` on its way in. */
@media (min-width: 1025px) and (max-width: 1279.98px) {
  [style*="repeat(4, minmax(0px, 1fr))"][style*="gap: 20px"] {
    grid-template-columns: repeat(3, minmax(0px, 1fr)) !important; }
}

/* ---- touch targets -----------------------------------------------------
   Measured on the built page at 500px, not guessed: the Authors search box
   renders 19px tall, the DOI links on Papers 14px, the staff-profile link
   30px. The WCAG floor is 44. The search box also gets 16px type, which is
   the one number that stops iOS Safari zooming the whole page when the
   field takes focus -- anything under 16 triggers it.
   The inline links grow by padding cancelled with an equal negative margin,
   so the hit area doubles and the line box does not move. */
@media (max-width: 1024px) {
  input[type="text"] {
    min-height: 44px !important; font-size: 16px !important;
    padding: 11px 13px !important;
  }
  a[href*="doi.org"], a[href*="aau.ac.ae"], a[href*="scopus"] {
    display: inline-block !important;
    padding: 11px 7px !important; margin: -11px -7px !important;
  }
}

@media (max-width: 1279.98px) {
  /* Four college tiles need ~1200px to stay readable; drop to three before
     the shell's own floor lifts. Selector in the DOM's spelling -- the
     runtime re-serialises `repeat(4,minmax(0,1fr))` on its way in. */
  /* The 1180px floor on the shell is what forces the sideways scroll. */
  [style*="min-width: 1180px"], [style*="min-width:1180px"] {
    min-width: 0 !important; }
  /* viewport-fit=cover lets the page reach under the notch, so the side
     padding becomes the safe-area inset rather than nothing. */
  [style*="min-height: 100vh"][style*="overflow-x: auto"],
  [style*="min-height:100vh"][style*="overflow-x:auto"] {
    padding: 0 env(safe-area-inset-right, 0px)
             env(safe-area-inset-bottom, 0px)
             env(safe-area-inset-left, 0px) !important; }

  /* Seven tabs and two chips in a fixed 64px row. Let it grow. */
  [style*="height: 64px"], [style*="height:64px"] {
    height: auto !important; min-height: 56px !important;
    flex-wrap: wrap !important; padding: 8px 14px !important;
    row-gap: 6px !important; }

  [style*="padding: 24px 26px 30px"], [style*="padding:24px 26px 30px"],
  [style*="padding: 26px 26px 34px"], [style*="padding:26px 26px 34px"] {
    padding: 16px 14px 24px !important; }
  [style*="padding: 20px 22px"], [style*="padding:20px 22px"],
  [style*="padding: 22px 24px"], [style*="padding:22px 24px"] {
    padding: 15px 14px !important; }
  [style*="padding: 80px 96px"], [style*="padding:80px 96px"] {
    padding: 56px 20px !important; }

  /* Once the header wraps, its flexible spacer only adds an empty line, and
     the window/as-of chips read better under the brand than beside it. */
  [style*="flex: 1 1 0%"][style*="min-width: 12px"] { display: none !important; }
  [style*="color: rgb(213, 232, 220)"][style*="white-space: nowrap"] {
    order: 2 !important; font-size: 12px !important; gap: 10px !important; }
  [style*="align-items: stretch"][style*="gap: 2px"] {
    order: 3 !important; flex: 1 1 100% !important; width: 100% !important; }

  /* Making the header height:auto took the tabs' height with it: the buttons
     are padding:0 17px and had no height of their own. Give them one, at the
     44px Apple asks for. */
  [style*="padding: 0px 17px"], [style*="padding:0 17px"] {
    min-height: 44px !important; padding: 0 13px !important; }

  /* The tab row is a nested flex that does not wrap. Measured at 833px, so
     below that width the last tabs are simply clipped and unreachable --
     wrapping the header is not enough. It scrolls sideways instead, which
     keeps every tab tappable and costs the layout nothing. */
  [style*="align-items: stretch"][style*="gap: 2px"],
  [style*="align-items:stretch;gap:2px"] {
    overflow-x: auto !important; flex-wrap: nowrap !important;
    max-width: 100% !important; -webkit-overflow-scrolling: touch !important;
    scrollbar-width: none !important; }
  [style*="align-items: stretch"][style*="gap: 2px"] > *,
  [style*="align-items:stretch;gap:2px"] > * { flex: 0 0 auto !important; }
  [style*="align-items: stretch"][style*="gap: 2px"]::-webkit-scrollbar {
    display: none !important; }

  [style*="grid-template-columns: 1.5fr 1fr"],
  [style*="grid-template-columns: 1.25fr 1fr"],
  [style*="grid-template-columns: 1.4fr 1fr"],
  [style*="grid-template-columns: 330px 1fr"] {
    grid-template-columns: 1fr !important; }

  /* Stacked, the Authors rail must not be tall enough to hide the person it
     selects. */
  [style*="grid-template-columns: 330px 1fr"] > *:first-child {
    max-height: 300px !important; overflow-y: auto !important; }
}

@media (max-width: 1024px) {
  [style*="repeat(3, minmax(0px, 1fr))"],
  [style*="repeat(4, minmax(0px, 1fr))"],
  [style*="repeat(5, minmax(0px, 1fr))"] {
    grid-template-columns: repeat(2, minmax(0px, 1fr)) !important; }

  /* Collaboration partner rows: a 300px name and a 320px bar do not fit; the
     bar and its caption drop under the name. */
  [style*="grid-template-columns: 26px 300px 320px 1fr"] {
    grid-template-columns: 22px 1fr !important; row-gap: 3px !important; }
  [style*="grid-template-columns: 26px 300px 320px 1fr"] > *:nth-child(3),
  [style*="grid-template-columns: 26px 300px 320px 1fr"] > *:nth-child(4) {
    grid-column: 2 !important; }

  [style*="grid-template-columns: 1fr 1fr"][style*="gap: 22px"] {
    grid-template-columns: 1fr !important; }
}

@media (max-width: 834px) {
  /* The six run stages: 28px + 150px + gaps = 202px before the label gets
     anything, and the label is the part you read. */
  [style*="grid-template-columns: 28px 1fr 150px"] {
    grid-template-columns: 28px 1fr !important; row-gap: 3px !important; }
  [style*="grid-template-columns: 28px 1fr 150px"] > *:nth-child(3) {
    grid-column: 2 !important; text-align: left !important; }

  /* The donut is 176px and its legend shares a non-wrapping row, which leaves
     the legend about 100px -- narrower than "Education, Humanities and Social
     Sciences". They stack. */
  [style*="display: flex"][style*="align-items: center"][style*="gap: 18px"] {
    flex-direction: column !important; align-items: flex-start !important; }

  /* Type below 12px is not readable on a phone, and the table headers and the
     smallest captions are exactly where a reader needs help. */
  [style*="font-size: 11px"], [style*="font-size: 11.5px"] {
    font-size: 12px !important; }

  /* Programme chips and the remove-author x are 27px and about 15px tall. */
  [style*="border-radius: 14px"][style*="padding: 5px 12px"] {
    min-height: 36px !important; display: inline-flex !important;
    align-items: center !important; }

  [style*="grid-template-columns: 1fr 1fr"] {
    grid-template-columns: 1fr !important; }

  /* Bar rows: let the bar take what is left rather than set the row's width. */
  [style*="grid-template-columns: 1fr 290px 54px"],
  [style*="grid-template-columns: 1fr 250px 44px"],
  [style*="grid-template-columns: 1fr 190px 34px"],
  [style*="grid-template-columns: 1fr 140px 38px"] {
    grid-template-columns: 1fr 84px 42px !important; }

  /* The Workflow diagram is a fixed 1308x450 canvas of absolutely-positioned
     nodes. It cannot reflow, so the whole thing scales: transform keeps every
     node with its label, which re-laying-out would not. The negative margin
     reclaims the height the untransformed box still reserves. */
  [style*="width: 1308px"], [style*="width:1308px"] {
    transform: scale(.56) !important; transform-origin: top left !important;
    margin-bottom: -198px !important; }
  /* The credit line under the diagram is a second hard 1308px block in the
     same scroller, so it inherits the whole width without the transform. */
  [style*="border-radius: 8px"][style*="width: 1308px"] {
    width: auto !important; max-width: 100% !important;
    transform: none !important; margin-bottom: 0 !important; }

  /* iOS zooms the page when a focused input's text is under 16px, and every
     input here was 13.5 or 14.5. The zoom is not undone on blur, so tapping
     the passphrase box leaves you pinching back out. 16px is the floor. */
  input, select, textarea { font-size: 16px !important; }

  /* Apple's touch-target floor is 44px; these were padded to about 32. */
  button { min-height: 40px !important; }

  /* The status badge is fixed where the iOS toolbar sits. */
  [style*="position: fixed"][style*="bottom: 14px"],
  [style*="position:fixed"][style*="bottom:14px"] {
    bottom: calc(14px + env(safe-area-inset-bottom, 0px)) !important;
    max-width: calc(100vw - 24px) !important;
    /* It writes its size with the `font:` shorthand, so the font-size rule
       above does not see it -- it was the last thing on the page under the
       12px floor. */
    font-size: 12px !important; }
}

@media (max-width: 640px) {
  /* The Dashboard's heading row keeps its count on the same line as the
     paragraph, which at 390px leaves the two touching. Let it drop. */
  [style*="align-items: flex-end"][style*="justify-content: space-between"] {
    flex-wrap: wrap !important; }
  /* A stacked card has no use for the column headers above it -- "NAME TITLE
     PAPERS H STATUS PROFILE" over a card that repeats none of them in that
     order is worse than nothing. The header row and the body rows share a
     track list, so they are told apart by the thing only the header carries. */
  [style*="1.7fr 1.1fr 90px 78px 90px 120px"][style*="font-size: 11.5px"],
  [style*="1.35fr 1fr 230px 58px 66px"][style*="font-size: 11.5px"],
  [style*="1fr 68px 64px 80px"][style*="font-size: 11.5px"] {
    display: none !important; }

  /* The roster people table: six columns, four fixed, summing with the gaps to
     448px before the name and title get anything. One card per person. */
  [style*="grid-template-columns: 1.7fr 1.1fr 90px 78px 90px 120px"] {
    grid-template-columns: 1fr auto !important; row-gap: 5px !important;
    padding: 13px 0 !important; }
  [style*="grid-template-columns: 1.7fr 1.1fr 90px 78px 90px 120px"] > *:nth-child(2) {
    grid-column: 1 / -1 !important; }
  [style*="grid-template-columns: 1.7fr 1.1fr 90px 78px 90px 120px"] > *:nth-child(n+3) {
    text-align: left !important; }

  /* Papers: five columns, 354px of them fixed. Title and the Al Ain authors
     take a line each; journal, year and citations share the next. */
  [style*="grid-template-columns: 1.35fr 1fr 230px 58px 66px"] {
    grid-template-columns: 1fr auto auto !important; row-gap: 4px !important;
    padding: 13px 0 !important; }
  [style*="grid-template-columns: 1.35fr 1fr 230px 58px 66px"] > *:nth-child(1),
  [style*="grid-template-columns: 1.35fr 1fr 230px 58px 66px"] > *:nth-child(2) {
    grid-column: 1 / -1 !important; }
  [style*="grid-template-columns: 1.35fr 1fr 230px 58px 66px"] > *:nth-child(3) {
    white-space: normal !important; }

  [style*="grid-template-columns: 1fr 68px 64px 80px"],
  [style*="grid-template-columns: 1fr 120px 92px 104px"],
  [style*="grid-template-columns: 1fr 110px 22px"] {
    grid-template-columns: 1fr auto !important; row-gap: 4px !important; }

  /* The co-author wheel is a 640x420 SVG with HTML labels laid on top at
     computed pixel offsets. Scaling the SVG alone would strand the labels, so
     the composite scales as one. */
  [style*="width: 640px"][style*="height: 420px"],
  [style*="width:640px;height:420px"] {
    transform: scale(.58) !important; transform-origin: top left !important;
    margin-bottom: -176px !important; }

  /* The run wizard's two month pickers sit in a row; a native month control
     will not shrink below its own text. */
  [style*="display: flex"][style*="gap: 14px"][style*="align-items: flex-end"] {
    flex-direction: column !important; align-items: stretch !important; }

  [style*="width: 520px"], [style*="width: 760px"], [style*="width: 420px"],
  [style*="width: 900px"], [style*="max-width: 900px"] {
    width: auto !important; max-width: calc(100vw - 26px) !important; }
}

@media (max-width: 430px) {

  [style*="display: flex"][style*="gap: 4px"] > button {
    padding: 9px 3px !important; font-size: 12px !important; }

  [style*="repeat(3, minmax(0px, 1fr))"],
  [style*="repeat(4, minmax(0px, 1fr))"],
  [style*="repeat(5, minmax(0px, 1fr))"] {
    grid-template-columns: 1fr !important; }
}
'''

PATCHES = [

    # ---- the run button now asks what kind of run this is ------------------
    ("run: ask what kind of run, instead of flipping a boolean",
     "toggleRun: () => this.setState(s => ({ running: !s.running })),",
     "toggleRun: () => {\n"
     "        if (this.state.running) { window.__AAU && window.__AAU.stop "
     "&& window.__AAU.stop(); this.setState({ running: false }); return; }\n"
     "        if (window.__AAU && window.__AAU.live) "
     "{ window.__AAU.askRun(this); return; }\n"
     "        window.__AAU && window.__AAU.askRun "
     "&& window.__AAU.askRun(this);\n"
     "      },"),

    # ---- searchable + filterable author list -------------------------------
    ("authors: the search box actually searches",
     '<input type="text" placeholder="Search 511 people…" style="border:0;',
     '<input type="text" placeholder="{{ searchHint }}" '
     'value="{{ q }}" sc-camel-on-input="{{ onSearch }}" style="border:0;'),

    ("authors: filter chips carry live counts and a handler",
     "    const authorFilters = [\n"
     "      { label: 'All 511', bg: accent, fg: '#ffffff', border: accent },\n"
     "      { label: 'Faculty', bg: '#ffffff', fg: '#3A4A41', "
     "border: '#D5DED8' },\n"
     "      { label: 'Students', bg: '#ffffff', fg: '#3A4A41', "
     "border: '#D5DED8' },\n"
     "    ];",
     "    const nFac = AUTHORS.filter(a => a.tag === 'Faculty').length;\n"
     "    const authorFilters = [\n"
     "      ['all', 'All ' + AUTHORS.length.toLocaleString()],\n"
     "      ['faculty', 'Faculty ' + nFac.toLocaleString()],\n"
     "      ['other', 'Students ' + (AUTHORS.length - nFac).toLocaleString()],\n"
     "    ].map(([id, label]) => {\n"
     "      const on = (this.state.tag || 'all') === id;\n"
     "      return { label, bg: on ? accent : '#ffffff',\n"
     "        fg: on ? '#ffffff' : '#3A4A41',\n"
     "        border: on ? accent : '#D5DED8',\n"
     "        pick: () => this.setState({ tag: id }) };\n"
     "    });"),

    ("authors: the filter chip is a button that does something",
     '<button type="button" style="background:{{ f.bg }};color:{{ f.fg }};'
     'border:1px solid {{ f.border }};border-radius:14px;',
     '<button type="button" sc-camel-on-click="{{ f.pick }}" '
     'style="background:{{ f.bg }};color:{{ f.fg }};'
     'border:1px solid {{ f.border }};border-radius:14px;'),

    ("authors: apply the search text and the chosen filter to the list",
     "    const authorList = AUTHORS.map(a => {",
     "    const _q = String(this.state.q || '').trim().toLowerCase();\n"
     "    const _tag = this.state.tag || 'all';\n"
     "    const _shown = AUTHORS.filter(a => {\n"
     "      if (_tag === 'faculty' && a.tag !== 'Faculty') return false;\n"
     "      if (_tag === 'other' && a.tag === 'Faculty') return false;\n"
     "      if (!_q) return true;\n"
     "      return (a.name + ' ' + (a.college || '') + ' ' + (a.title || '')\n"
     "        + ' ' + (a.auid || '')).toLowerCase().indexOf(_q) >= 0;\n"
     "    });\n"
     "    const authorList = _shown.map(a => {"),

    # ---- exports write real files -----------------------------------------
    ("exports: each card's button exports that file",
     '<button type="button" style="margin-top:16px;background:{{ e.btnBg }};',
     '<button type="button" sc-camel-on-click="{{ e.go }}" '
     'style="margin-top:16px;background:{{ e.btnBg }};'),

    ("exports: 'Export all three' does all three",
     '<button type="button" style="background:{{ accent }};color:#ffffff;'
     'border:0;border-radius:6px;padding:12px 24px;font-family:Archivo,'
     'sans-serif;font-size:14px;font-weight:700;cursor:pointer;'
     'white-space:nowrap">Export all three',
     '<button type="button" sc-camel-on-click="{{ exportAll }}" '
     'style="background:{{ accent }};color:#ffffff;'
     'border:0;border-radius:6px;padding:12px 24px;font-family:Archivo,'
     'sans-serif;font-size:14px;font-weight:700;cursor:pointer;'
     'white-space:nowrap">Export all three'),

    # ---- the review queue can actually clear a name -----------------------
    ("review: the decision buttons decide",
     '<button type="button" style="background:{{ c.btnBg }};color:{{ c.btnFg }};'
     'border:1px solid {{ c.btnBorder }};border-radius:5px;',
     '<button type="button" sc-camel-on-click="{{ c.go }}" '
     'style="background:{{ c.btnBg }};color:{{ c.btnFg }};'
     'border:1px solid {{ c.btnBorder }};border-radius:5px;'),

    # ---- headline figures come from the run, not from a literal -----------
    ("dashboard: the three tiles read live figures",
     "    const tiles = [\n"
     "      { v: '1,336', l: 'papers in the census', sub: 'publication years "
     "2025 and 2026', color: accent },\n"
     "      { v: '6', l: 'added by the sweep', sub: 'found on an author, not "
     "on the university tag', color: accent },\n"
     "      { v: '511', l: 'authors', sub: '161 of them on the faculty "
     "roster', color: accent },\n"
     "    ];",
     "    const S_ = (window.__AAU && window.__AAU.state "
     "&& window.__AAU.state.stats) || null;\n"
     "    const yrs_ = (window.__AAU && window.__AAU.years) "
     "|| [2025, 2026];\n"
     "    const tiles = S_ ? [\n"
     "      { v: S_.papers.toLocaleString(), l: 'papers in the census',\n"
     "        sub: 'publication years ' + yrs_.join(' and '), color: accent },\n"
     "      { v: String(S_.review), l: 'need a decision',\n"
     "        sub: 'names matching more than one Scopus author', color: accent },\n"
     "      { v: S_.authors.toLocaleString(), l: 'authors',\n"
     "        sub: S_.faculty.toLocaleString() + ' of them on the faculty "
     "roster', color: accent },\n"
     "    ] : [\n"
     "      { v: '1,336', l: 'papers in the census', sub: 'publication years "
     "2025 and 2026', color: accent },\n"
     "      { v: '6', l: 'added by the sweep', sub: 'found on an author, not "
     "on the university tag', color: accent },\n"
     "      { v: '511', l: 'authors', sub: '161 of them on the faculty "
     "roster', color: accent },\n"
     "    ];"),

    # The mockup's donut appended two categories that do not exist on the
    # roster -- "Computer and Info. Sciences" is the invented college the
    # census produced before the curated roster replaced guessing. With real
    # data they must not reappear.
    ("dashboard: drop the two invented pie categories when data is live",
     "      .concat([['Computer and Info. Sciences', 79, '#14563A'], "
     "['No college stated', 48, '#9BB0A4']])",
     "      .concat((window.__AAU && window.__AAU.live) ? [] : "
     "[['Computer and Info. Sciences', 79, '#14563A'], "
     "['No college stated', 48, '#9BB0A4']])"),

    # ---- what the run actually reported ----------------------------------
    ("dashboard: findings come from the run that just happened",
     "    const findings = running ? [",
     "    const liveF_ = (window.__AAU && window.__AAU.status\n"
     "      && window.__AAU.status.findings) || null;\n"
     "    const findings = liveF_ && liveF_.length ? liveF_.map(f => ({\n"
     "      text: f.text,\n"
     # 'info' is a line that is neither good news nor a fault -- the papers
     # examined and left out are the rule working, and painting them red read
     # as damage. `why` becomes the hover: a number nobody can interrogate is
     # worse than no number.
     "      why: f.why || '',\n"
     "      color: f.kind === 'bad' ? '#E0303F'\n"
     "        : (f.kind === 'warn' ? '#E8A33D'\n"
     "        : (f.kind === 'info' ? '#8C9A92' : accent)),\n"
     "    })).filter((f, i) => i === 0 || this.state.findMore)\n"
     "      : running ? ["),

    ("dashboard: a finding can explain itself on hover",
     '<div style="font-size:14px;color:#2A3A31;line-height:1.45">{{ f.text }}</div>',
     '<div title="{{ f.why }}" style="font-size:14px;color:#2A3A31;'
     'line-height:1.45">{{ f.text }}</div>'),

    ("dashboard: the run caption reflects the real run",
     "      runTitle: running ? 'Run in progress' : 'Last run finished',",
     "      runTitle: running ? 'Run in progress'\n"
     "        : (((window.__AAU && window.__AAU.status\n"
     "            && (window.__AAU.status.stages || []).some(x =>\n"
     "                 /fail|cancel|timed|error/i.test(x.label || '')))\n"
     "           ? 'Last run failed'\n"
     "        : ((window.__AAU && (window.__AAU.status\n"
     "            || (window.__AAU.state && window.__AAU.state.generated)))\n"
     "           ? 'Last run finished'\n"
     "           : (window.__AAU && window.__AAU.live ? 'No run yet'\n"
     "              : 'Last run finished')))),"),

    # ---- import roster CSV -------------------------------------------------
    ("roster: 'Import roster CSV' opens a file picker",
     '<button type="button" style="background:#ffffff;color:{{ accent }};'
     'border:1px solid #C3D6CA;border-radius:6px;padding:10px 17px;',
     '<button type="button" sc-camel-on-click="{{ importCsv }}" '
     'style="background:#ffffff;color:{{ accent }};'
     'border:1px solid #C3D6CA;border-radius:6px;padding:10px 17px;'),
]


# ---------------------------------------------------------------------------
# "We found another one -- add them to the roster?"
#
# Every run already ends by asking Scopus for papers that print an AAU address.
# Some of those papers carry an author who is NOT on the roster and who is
# plainly not a student: Ghaleb El Refae, AAU's chancellor, has ~50 papers and
# was filed as "student or external" purely because the directory scrape missed
# him. The rule stays -- off the roster means outside faculty -- but the run now
# surfaces those people on the Roster screen so the omission gets fixed instead
# of quietly persisting.
# ---------------------------------------------------------------------------
SUGGEST_BANNER = (
    '\n    <sc-if value="{{ hasSuggestions }}" '
    'hint-placeholder-val="{{ true }}">\n'
    '    <button type="button" sc-camel-on-click="{{ openSuggestions }}" data-rise '
    'style="display:flex;width:100%;text-align:left;align-items:center;'
    'gap:14px;background:#ffffff;border:1px solid #C3D6CA;'
    'border-left:4px solid {{ accent }};border-radius:8px;'
    'padding:15px 18px;margin-bottom:16px;cursor:pointer;'
    'font-family:Archivo,sans-serif">\n'
    '      <div style="flex:1">\n'
    '        <div style="font-size:14.5px;font-weight:700;color:#1A1A1A">'
    '{{ suggestTitle }}</div>\n'
    '        <div style="font-size:13px;color:#63736A;margin-top:4px;'
    'line-height:1.45">{{ suggestSub }}</div>\n'
    '      </div>\n'
    '      <div style="font-size:13.5px;font-weight:700;color:{{ accent }};'
    'white-space:nowrap">Review them &rsaquo;</div>\n'
    '    </button>\n'
    '    </sc-if>\n')

# build.py applies this one LAST, so its anchor must be the markup as the
# joined-list patch leaves it, not as the design shipped it.
BANNER_PATCH = (
    "roster: banner offering the people a run found who are not on the roster",
    '\n    <div style="display:flex;flex-direction:column">\n'
    '      <sc-for list="{{ rosterCols }}" as="c" hint-placeholder-count="8">',
    SUGGEST_BANNER +
    '    <div style="display:flex;flex-direction:column">\n'
    '      <sc-for list="{{ rosterCols }}" as="c" hint-placeholder-count="8">')


# view-model additions the new markup and handlers need
VALS = r"""
      // --- live wiring -----------------------------------------------------
      q: this.state.q || '',
      tag: this.state.tag || 'all',
      searchHint: 'Search ' + AUTHORS.length.toLocaleString() + ' people…',
      onSearch: (e) => this.setState({ q: e && e.target ? e.target.value : '' }),
      exportAll: () => window.__AAU && window.__AAU.exportAll(this),
      importCsv: () => window.__AAU && window.__AAU.importCsv(this),
      hasSuggestions: !!(window.__AAU && window.__AAU.suggestions
                         && window.__AAU.suggestions.length),
      suggestTitle: (window.__AAU && window.__AAU.suggestions
        ? (window.__AAU.suggestions.length === 1
            ? 'We found someone who is not on your roster'
            : 'We found ' + window.__AAU.suggestions.length
              + ' people who are not on your roster')
        : ''),
      suggestSub: 'Their papers print an Al Ain University address and they '
        + 'publish like faculty, but the roster does not list them. '
        + 'Until you add them they count as outside faculty.',
      openSuggestions: () => window.__AAU && window.__AAU.showSuggestions(this),
      addPerson: () => window.__AAU && window.__AAU.addPerson(this),
      hasPrograms: !!(PROGRAMS.length && sel),
      // Empty is a real answer. The design had no way to show it, so it
      // substituted three other people instead -- see the patch below.
      colEmpty: !!(sel && !colAuthors.length),
      colEmptyNote: (() => {
        if (!sel || colAuthors.length) return '';
        if (this.state.program) return 'Nobody on ' + this.state.program
          + ' has a paper in this window.';
        return 'Nobody in this college has a paper in this window.';
      })(),
      // The degree prefix is the same on every chip in a college, so it says
      // nothing; what distinguishes them is the subject. Cut on a word, never
      // mid-word -- "Networks and Communication Enginee" reads as a mistake.
      shortProgUnused: 0,
      progNote: (() => {
        const p = this.state.program;
        if (!p || !sel) return '';
        const rec = PROGRAMS.find(x => x.name === p && x.college === sel);
        if (!rec) return '';
        // Two different numbers, and showing the wrong one reads as a bug:
        // `tagged` is how many staff are ON the programme, `people` is how
        // many of them have a Scopus record in this window. Dentistry has
        // three staff and none with papers -- as "0 people" that looks like
        // the tagging failed, so say both.
        const n = rec.tagged || rec.people;
        return n + (n === 1 ? ' member of staff \u00b7 ' : ' staff \u00b7 ')
          + (rec.papers ? rec.papers.toLocaleString() + ' papers from '
               + rec.people + ' of them'
             : 'none of them published in this window')
          + (rec.assumed ? ' \u00b7 assigned here \u2014 AAU lists this '
             + 'college\u2019s staff but tags nobody to its one programme'
             : '');
      })(),
      progChips: (() => {
        const shortProg = (n) => {
          let t = String(n)
            .replace(/^(Bachelor|Master|Doctor) of (Science|Arts|Philosophy) in /, '')
            .replace(/^(Bachelor|Master|Doctor) of /, '')
            .replace(/^(Bachelor|Master) in /, '')
            .replace(/^Postgraduate Professional Diploma in /, 'Diploma, ')
            .replace(/^BBA in /, '')
            .replace(/ Engineering$/, ' Eng.');
          if (t.length <= 30) return t;
          const cut = t.slice(0, 30);
          const sp = cut.lastIndexOf(' ');
          return (sp > 14 ? cut.slice(0, sp) : cut).replace(/[ ,]+$/, '') + '\u2026';
        };
        if (!sel) return [];
        const mine = PROGRAMS.filter(p => p.college === sel);
        if (!mine.length) return [];
        const chosen = this.state.program || '';
        const chip = (label, value, title) => {
          const on = chosen === value;
          return {
            label, title,
            bg: on ? accent : '#ffffff',
            fg: on ? '#ffffff' : '#3A4A41',
            border: on ? accent : '#D5DED8',
            pick: () => this.setState({ program: on ? null : value }),
          };
        };
        // A person can teach on several programmes, so these do not partition
        // the college and the chip counts sum to more than its people.
        return [chip('Everyone', '', 'All ' + mine.length
                     + ' programmes in this college')].concat(
          mine.slice().sort((a, b) => b.papers - a.papers
                                 || b.tagged - a.tagged).map(p =>
            chip(shortProg(p.name) + (p.assumed ? ' *' : ''),
                 p.name,
                 p.name + ' \u2014 ' + (p.tagged || p.people) + ' staff, '
                   + (p.papers ? p.papers.toLocaleString() + ' papers'
                      : 'no papers in this window')
                   + (p.assumed ? ' (* assigned here, not tagged by AAU)'
                      : ''))));
      })(),
      csvHelp: () => window.__AAU && window.__AAU.csvHelp(),
      showPapers: () => window.__AAU && window.__AAU.showPapers(this),
      exportCollege: () => window.__AAU && window.__AAU.exportCollege(this),
      // ---- the dashboard is a card per programme -------------------------
      // PROGRAMS is already filled from state.programs by the bridge, so this
      // needs no new plumbing. Every number here is the window the last run
      // covered, except avg h, which Scopus defines over a whole career and
      // which is labelled as such wherever it appears.
      progWindowNote: (() => {
        const st = (window.__AAU && window.__AAU.state) || {};
        const n = PROGRAMS.length;
        const w = (st.stats && st.stats.papers) ? st.stats.papers.toLocaleString() : '\u2014';
        return 'Everything below covers the window the last run asked for \u2014 '
          + w + ' papers across ' + n + ' programmes. To see another period, '
          + 'press Run now above.';
      })(),
      // Three levels, the same shape the Roster uses: colleges, then one
      // college's programmes, then one programme. Fifty-one cards in a
      // single wall was a data dump; eight is a dashboard.
      progList: !this.state.prog && !this.state.dashCol,
      progOfCollege: !this.state.prog && !!this.state.dashCol,
      progDetail: !!this.state.prog,
      // Grouped under their college, in the app's own college order, so the
      // eight colours mean the same thing here as everywhere else.
      dashColleges: (() => {
        const best = Math.max(1, ...COLLEGE_DATA.map(c => c.papers || 0));
        return COLLEGE_DATA.map((c, i) => ({
          name: c.name.replace('College of ', ''),
          full: c.name,
          color: c.color,
          papers: (c.papers || 0).toLocaleString(),
          // Citations are gone from this card on purpose: they rank the
          // eight colleges in almost exactly the order papers already does,
          // so a third figure bought density and no new information. They
          // survive one click down, next to their denominators.
          //
          // Papers per person is the opposite -- it is the only figure here
          // that RE-ORDERS the eight. Business leads on rate and is fourth
          // on volume; Engineering leads on volume and is second on rate.
          //
          // The divisor is `people`, never `staff`: `staff` is the sum of
          // per-programme tag counts, and a person tagged to three
          // programmes is counted three times. It reads 83 for a college of
          // 44. Never print it, and never roll programme figures up to a
          // college by summing them -- 51 programmes sum to 6,904 papers
          // against 3,606 actually held by the eight colleges.
          per: (c.people || 0) ? ((c.papers || 0) / c.people).toFixed(1) : '\u2014',
          // The Dashboard's two levels divide by different populations --
          // a college by everyone on its roster, a programme by the staff
          // AAU tags to it -- and the cards look identical. Each figure
          // therefore carries its own denominator on hover.
          perWhy: (c.papers || 0).toLocaleString() + ' papers \u00f7 '
            + (c.people || 0) + ' people on the roster in this college',
          meta: (c.programs || 0) + (c.programs === 1 ? ' programme' : ' programmes')
            + ' \u00b7 ' + (c.people || 0) + ((c.people || 0) === 1 ? ' person' : ' people'),
          // Clamped, not 0.03 * i. Education runs 14 programmes; unclamped,
          // its last card would not begin until 520ms and would land at
          // 940ms, which reads as the page still loading.
          delay: (0.03 * Math.min(i, 8)).toFixed(2) + 's',
          barW: Math.max(2, Math.round(100 * (c.papers || 0) / best)) + '%',
          open: () => this.setState({ dashCol: c.name, dashNav: 'fwd' }),
        }));
      })(),
      dashColName: (this.state.dashCol || '').replace('College of ', ''),
      dashColMeta: (() => {
        const c = COLLEGE_DATA.find(x => x.name === this.state.dashCol);
        if (!c) return '';
        return (c.programs || 0) + ' programmes \u00b7 ' + (c.people || 0)
          + ' people \u00b7 ' + (c.papers || 0).toLocaleString() + ' papers'
          + (c.citations ? (' \u00b7 ' + c.citations.toLocaleString()
             + ' citations') : '');
      })(),
      dashColColor: (() => {
        const c = COLLEGE_DATA.find(x => x.name === this.state.dashCol);
        return (c && c.color) || accent;
      })(),
      // NOT `backToColleges` -- the Roster already owns that name, and a
      // second definition in the same object literal silently won,
      // killing the Roster's own back button. The same mistake as the
      // duplicate progNote; a flat key is a shared namespace.
      dashBack: () => this.setState({ dashCol: null, prog: null, dashNav: 'back' }),
      // Which way the last move went, so the level that mounts can enter
      // from the side it came from. 'none' on first paint, so the opening
      // screen simply rises rather than sliding in from nowhere.
      dashNav: this.state.dashNav || 'none',
      dashEyebrow: (() => {
        const y = (S_ && S_.years) || [];
        return 'Research output \u00b7 ' + (y.length
          ? (y.length > 1 ? y[0] + '\u2013' + y[y.length - 1] : String(y[0]))
          : '2021\u20132026');
      })(),
      dashCount: (() => {
        const n = (S_ && S_.programs_total) || PROGRAMS.length;
        return COLLEGE_DATA.length + ' colleges \u00b7 ' + n + ' programmes';
      })(),
      progGroups: (() => {
        const order = COLLEGE_DATA.map(c => c.name);
        const colour = {}; COLLEGE_DATA.forEach(c => { colour[c.name] = c.color; });
        // Scale each bar against the best in ITS OWN college. Against the
        // global best -- Business's MBA at 743 -- most of Law, Education,
        // Communication and Nursing draw a 3% stub and stop saying
        // anything. The colour carries the cross-college comparison.
        const bestIn = {};
        PROGRAMS.forEach(p => {
          const c = p.college;
          bestIn[c] = Math.max(bestIn[c] || 1, p.papers || 0);
        });
        // The degree has to survive the shortening. Dropping it collapsed
        // "Bachelor of Arts in Applied Sociology" and "Master of Arts in
        // Applied Sociology" into two cards both reading "Applied Sociology",
        // side by side, with different numbers.
        const shortP = (n) => {
          const s0 = String(n);
          let deg = '';
          if (/^Bachelor of Science/.test(s0)) deg = 'BSc';
          else if (/^Master of Science/.test(s0)) deg = 'MSc';
          else if (/^Bachelor of Arts/.test(s0)) deg = 'BA';
          else if (/^Master of Arts/.test(s0)) deg = 'MA';
          else if (/^Doctor of Philosophy/.test(s0)) deg = 'PhD';
          else if (/^Bachelor of Education/.test(s0)) deg = 'BEd';
          else if (/^Master of Education/.test(s0)) deg = 'MEd';
          else if (/^Postgraduate Professional Diploma/.test(s0)) deg = 'Dip';
          else if (/^BBA/.test(s0)) deg = 'BBA';
          else if (/^Bachelor/.test(s0)) deg = 'B';
          else if (/^Master/.test(s0)) deg = 'M';
          let t = s0
            .replace(/^(Bachelor|Master|Doctor) of (Science|Arts|Philosophy|Education) in /, '')
            .replace(/^(Bachelor|Master|Doctor) of (Science|Arts|Philosophy|Education) - /, '')
            .replace(/^(Bachelor|Master|Doctor) of /, '')
            .replace(/^(Bachelor|Master) in /, '')
            .replace(/^Postgraduate Professional Diploma in /, '')
            .replace(/^BBA in /, '');
          const room = deg ? 34 : 38;
          if (t.length > room) {
            const cut = t.slice(0, room), sp = cut.lastIndexOf(' ');
            t = (sp > 16 ? cut.slice(0, sp) : cut).replace(/[ ,]+$/, '') + '\u2026';
          }
          return deg ? (deg + ' \u00b7 ' + t) : t;
        };
        // AAU tags the same ten people to five of Communication's
        // programmes, and the same four to two of Education's. Those cards
        // carry identical figures under different names, and side by side
        // with nothing said that reads as a bug or as a lie. Count the
        // signature and let the card admit it.
        const sig = {};
        PROGRAMS.forEach(p => {
          const k = [p.college, p.tagged, p.people, p.papers].join('|');
          sig[k] = (sig[k] || 0) + 1;
        });
        const only = this.state.dashCol;
        return order.filter(c => !only || c === only).map(col => ({
          college: col.replace('College of ', ''),
          // Inside one college the context bar already names it; repeating it
          // as a group heading directly underneath says nothing twice.
          headShow: only ? 'none' : 'flex',
          color: colour[col] || accent,
          cards: PROGRAMS.filter(p => p.college === col)
            .sort((a, b) => (b.papers || 0) - (a.papers || 0))
            .map((p, i) => {
              const staff = p.tagged || p.people || 0;
              const per = staff ? (p.papers || 0) / staff : 0;
              return {
                name: shortP(p.name),
                full: p.name + ' \u2014 ' + col,
                papers: p.papers ? p.papers.toLocaleString() : '\u2014',
                cites: p.citations ? p.citations.toLocaleString() : '\u2014',
                per: staff ? per.toFixed(1) : '\u2014',
                // Small programmes staffed by prolific people produce
                // genuinely large ratios -- the MSc in Software Systems
                // Engineering is 345 papers over the 3 staff AAU tags to
                // it, all three with a career h-index above 30. The figure
                // is right; without its denominator it reads as a fault.
                perWhy: (p.papers || 0).toLocaleString() + ' papers \u00f7 '
                  + staff + (staff === 1 ? ' member of staff AAU tags to this '
                    : ' staff AAU tags to this ') + 'programme. A paper counts '
                  + 'for the programme if any of its authors is tagged to it, '
                  + 'so a few prolific people can carry a large number.',
                barW: Math.max(2, Math.round(100 * (p.papers || 0) / (bestIn[col] || 1))) + '%',
                color: colour[col] || accent,
                quiet: p.papers ? '' : 'No one on this programme has a paper '
                  + 'in this window.',
                quietShow: p.papers ? 'none' : 'block',
                shared: (() => {
                  const n = sig[[p.college, p.tagged, p.people, p.papers].join('|')];
                  return n > 1 ? ('same staff as ' + (n - 1) + ' other'
                    + (n > 2 ? 's' : '')) : '';
                })(),
                sharedShow: sig[[p.college, p.tagged, p.people, p.papers]
                  .join('|')] > 1 ? 'inline-block' : 'none',
                sharedWhy: 'AAU tags the same people to several of this '
                  + 'college\u2019s programmes, so these are the figures for '
                  + 'that group of staff rather than for this programme alone.',
                statShow: p.papers ? 'flex' : 'none',
                delay: (0.025 * Math.min(i, 8)).toFixed(3) + 's',
                pick: () => this.setState({ prog: p.name, dashNav: 'fwd' }),
              };
            }),
        })).filter(g => g.cards.length);
      })(),
      backToProgs: () => this.setState({ prog: null, dashNav: 'back' }),
      backLabel: this.state.dashCol
        ? ('\u2039 ' + this.state.dashCol.replace('College of ', ''))
        : '\u2039 All programmes',
      // Seven lines of run narration, on a screen whose job is now the
      // programme cards. The one that stays carries the corpus total, because
      // removing the headline tiles took it off the page. The rest are kept,
      // not deleted -- the "checked and not counted" line is what proves the
      // affiliation gate is working, and the co-author line is what stops a
      // reader over-trusting the author lists -- and open on a click.
      findMore: !!this.state.findMore,
      toggleFind: () => this.setState(s => ({ findMore: !s.findMore })),
      findMoreLabel: this.state.findMore
        ? 'Hide the rest' : 'What else this run found',
      findMoreCount: (() => {
        const st = (window.__AAU && window.__AAU.state) || {};
        const n = ((window.__AAU && window.__AAU.status
          && window.__AAU.status.findings) || st.findings || []).length;
        return n > 1 ? ('  \u00b7  ' + (n - 1) + ' more') : '';
      })(),
      // The drill-down. Six metrics, and two comparisons -- the programme's own
      // people, and the programme against its siblings in the same college with
      // that college's median marked, because a number without a comparison is
      // not a finding.
      progOne: (() => {
        const p = PROGRAMS.find(x => x.name === this.state.prog);
        if (!p) return { name: '', college: '', color: accent };
        const colour = {}; COLLEGE_DATA.forEach(c => { colour[c.name] = c.color; });
        const staff = p.tagged || p.people || 0;
        const f = (v) => v ? v.toLocaleString() : '\u2014';
        const r = (v) => (v || v === 0) ? v.toFixed(1) : '\u2014';
        return {
          name: p.name,
          college: p.college.replace('College of ', ''),
          color: colour[p.college] || accent,
          papers: f(p.papers), cites: f(p.citations),
          perStaff: staff ? r((p.papers || 0) / staff) : '\u2014',
          // A missing citation count is not a count of zero. Until a run
          // has been made with an engine that carries it, these read as
          // unknown rather than as nothing.
          citesPerStaff: (p.citations && staff) ? r(p.citations / staff) : '\u2014',
          citesPerPaper: (p.citations && p.papers) ? r(p.citations / p.papers) : '\u2014',
          avgH: p.avg_h ? r(p.avg_h) : '\u2014',
          hNote: p.with_h ? ('career h-index, averaged over the ' + p.with_h
            + ' of ' + staff + ' with one') : 'no career h-index on file',
          staffLine: staff + (staff === 1 ? ' member of staff AAU lists on this '
            : ' staff AAU lists on this ') + 'programme, '
            + (p.people || 0) + ' with a Scopus record',
          assumedShow: p.assumed ? 'block' : 'none',
        };
      })(),
      progPeople: (() => {
        const p = PROGRAMS.find(x => x.name === this.state.prog);
        if (!p) return [];
        // PROGRAMS and the authors do not always spell a programme the
        // same way: "Master of Business Administration (MBA)" against
        // "Master of Business Administration". Joining on the raw string
        // drilled the largest programme at AAU down to nobody.
        const pk = (n) => String(n || '').replace(/\([^)]*\)/g, ' ')
          .toLowerCase().replace(/[^a-z0-9]+/g, ' ').trim();
        const want = pk(p.name);
        const mine = AUTHORS.filter(a =>
          (a.programs || []).some(x => pk(x) === want));
        const max = Math.max(1, ...mine.map(a => a.papers || 0));
        return mine.sort((a, b) => (b.papers || 0) - (a.papers || 0)).slice(0, 14)
          .map(a => ({
            name: a.name, papers: a.papers || 0,
            barW: Math.max(2, Math.round(100 * (a.papers || 0) / max)) + '%',
            title: a.name + ' \u2014 ' + (a.papers || 0) + ' papers in this window, '
              + 'career h-index ' + (a.h || 0),
          }));
      })(),
      progSiblings: (() => {
        const p = PROGRAMS.find(x => x.name === this.state.prog);
        if (!p) return [];
        const sib = PROGRAMS.filter(x => x.college === p.college);
        const vals = sib.map(x => (x.tagged || x.people)
          ? (x.papers || 0) / (x.tagged || x.people) : 0).sort((a, b) => a - b);
        const med = vals.length ? vals[Math.floor(vals.length / 2)] : 0;
        const max = Math.max(0.1, ...vals);
        return sib.sort((a, b) => {
          const av = (a.tagged || a.people) ? (a.papers || 0) / (a.tagged || a.people) : 0;
          const bv = (b.tagged || b.people) ? (b.papers || 0) / (b.tagged || b.people) : 0;
          return bv - av;
        }).map(x => {
          const st = x.tagged || x.people || 0;
          const v = st ? (x.papers || 0) / st : 0;
          const me = x.name === p.name;
          return {
            name: x.name.length > 40 ? x.name.slice(0, 40) + '\u2026' : x.name,
            v: v.toFixed(1),
            barW: Math.max(2, Math.round(100 * v / max)) + '%',
            bg: me ? (COLLEGE_DATA.find(c => c.name === p.college) || {}).color || accent
                   : '#CDE6D8',
            weight: me ? 700 : 500,
            medLeft: Math.round(100 * med / max) + '%',
          };
        });
      })(),
      progMedNote: (() => {
        const p = PROGRAMS.find(x => x.name === this.state.prog);
        if (!p) return '';
        const sib = PROGRAMS.filter(x => x.college === p.college);
        const vals = sib.map(x => (x.tagged || x.people)
          ? (x.papers || 0) / (x.tagged || x.people) : 0).sort((a, b) => a - b);
        const med = vals.length ? vals[Math.floor(vals.length / 2)] : 0;
        return 'Papers per member of staff AAU lists. The line is this '
          + 'college\u2019s median, ' + med.toFixed(1) + '.';
      })(),
      // ---- Networking and Collaboration ----------------------------------
      netReady: !!(NETWORK && NETWORK.top && NETWORK.top.length),
      netNote: (() => {
        const c = NETWORK.coverage;
        if (!c) return 'Loading\u2026';
        // Floor, not round: 3,203 of 3,204 is not 100%, and a page that
        // rounds its way to a completeness it does not have is the small
        // dishonesty this whole screen is built to avoid.
        const pct = Math.floor(100 * c.printed / Math.max(1, c.papers));
        return 'Built from ' + c.printed.toLocaleString() + ' of the '
          + c.papers.toLocaleString() + ' papers in this window \u2014 '
          + pct + '% \u2014 by reading the institutions printed on each one.';
      })(),
      // The institution list is fetched one paper at a time on a window that
      // has not been asked for before, so a run can land with the screen
      // still partly filled. Say so, with how long it takes, rather than
      // letting a reader take a partial answer for the whole one.
      netPendingShow: (() => {
        const c = NETWORK.coverage;
        if (!c || !c.papers) return 'none';
        return (c.papers - c.printed) > c.papers * 0.02 ? 'block' : 'none';
      })(),
      netPending: (() => {
        const c = NETWORK.coverage;
        if (!c) return '';
        const left = c.papers - c.printed;
        return 'Still reading the institutions on ' + left.toLocaleString()
          + ' more papers. That takes about 25 to 30 minutes the first time a '
          + 'window is asked for, and is instant afterwards \u2014 the answers '
          + 'are kept. Everything below is real, but it is those '
          + c.printed.toLocaleString() + ' papers only, so the counts will '
          + 'grow. Come back in half an hour for the full picture.';
      })(),
      netQuar: (() => {
        const c = NETWORK.coverage;
        if (!c) return '';
        const pc = Math.round(100 * c.mega_pairs / Math.max(1, c.pairs));
        return c.mega + ' consortium papers are set aside. Each lists more than '
          + c.threshold + ' institutions, and between them they carry ' + pc
          + '% of every institution mentioned anywhere \u2014 left in, they '
          + 'decide every ranking below. The largest ordinary paper lists '
          + c.largest_ordinary + ' institutions; the smallest consortium one '
          + c.smallest_mega + '.';
      })(),
      netPartners: (() => {
        const rows = (NETWORK.top || []).slice(0, 12);
        const max = rows.length ? rows[0].papers : 1;
        return rows.map((r, i) => ({
          rank: i + 1, name: r.name, papers: r.papers.toLocaleString(),
          barW: Math.max(3, Math.round(300 * r.papers / max)) + 'px',
          creditW: Math.max(2, Math.round(300 * r.credit / max)) + 'px',
          led: r.aau_led,
          cols: r.colleges.length,
          title: r.name + ' \u2014 ' + r.papers + ' joint papers. Fractional '
            + 'credit ' + r.credit + ', which shares each paper out among the '
            + 'institutions on it. An Al Ain author led or corresponded on '
            + r.aau_led + '. Worked with by ' + r.colleges.length
            + ' AAU colleges.',
        }));
      })(),
      netColleges: Object.keys(NETWORK.by_college || {}).sort().map(c => ({
        name: c.replace('College of ', ''),
        rows: (NETWORK.by_college[c] || []).slice(0, 5).map(r => ({
          name: r.name, papers: r.papers,
          barW: Math.max(4, Math.round(140 * r.papers
            / ((NETWORK.by_college[c][0] || {}).papers || 1))) + 'px',
        })),
      })),
      netCountries: (NETWORK.countries || []).slice(0, 14).map(r => ({
        name: r.name, papers: r.papers.toLocaleString(),
        barW: Math.max(3, Math.round(290 * r.papers
          / (((NETWORK.countries || [])[0] || {}).papers || 1))) + 'px',
      })),
      netJoint: (NETWORK.joint || []).slice(0, 10).map(r => ({
        pair: r.a.replace('College of ', '') + '  \u00b7  '
          + r.b.replace('College of ', ''),
        papers: r.papers,
        barW: Math.max(4, Math.round(250 * r.papers
          / (((NETWORK.joint || [])[0] || {}).papers || 1))) + 'px',
      })),
      // ---- the dashboard's top collaborators -----------------------------
      // Fed from the summary that rides along in state.json, so the card is
      // there on arrival without fetching the 21KB collaboration file.
      dashCollab: (() => {
        const st = (window.__AAU && window.__AAU.state) || {};
        const rows = ((st.network || {}).top || []).slice(0, 6);
        if (!rows.length) return [];
        const max = rows[0].papers;
        return rows.map(r => ({
          name: r.name.replace(/^The /, ''),
          papers: r.papers,
          barW: Math.max(4, Math.round(190 * r.papers / max)) + 'px',
          creditW: Math.max(2, Math.round(190 * r.credit / max)) + 'px',
          title: r.name + ' \u2014 ' + r.papers + ' joint papers, and '
            + r.credit + ' once each paper is shared out among the '
            + 'institutions on it.',
        }));
      })(),
      dashCollabShow: (() => {
        const st = (window.__AAU && window.__AAU.state) || {};
        return ((st.network || {}).top || []).length ? 'block' : 'none';
      })(),
      goNet: () => { if (window.__AAU && window.__AAU.needNetwork) {
        window.__AAU.needNetwork(this); } this.setState({ screen: 'net' }); },
      // ---- one researcher's co-authors, as a wheel -----------------------
      // Laid out here, in JS, because the runtime does not interpolate text
      // inside an <svg>: the circles and lines are SVG attributes, every
      // label is an HTML box positioned on top of them.
      coHas: (() => {
        const st = (window.__AAU && window.__AAU.state) || {};
        const p_ = AUTHORS.find(a => a.key === this.state.author) || AUTHORS[0];
        return !!(p_ && ((st.coauthors || {})[p_.key] || []).length);
      })(),
      coNote: (() => {
        const st = (window.__AAU && window.__AAU.state) || {};
        const p_ = AUTHORS.find(a => a.key === this.state.author) || AUTHORS[0];
        const rows = (st.coauthors || {})[(p_ || {}).key] || [];
        if (!rows.length) return '';
        const tot = rows.reduce((s2, r) => s2 + r[1], 0);
        return rows.length + ' people at Al Ain University appear on '
          + p_.name + '\u2019s papers, ' + tot + ' co-authorships in all. '
          + 'Sized and thickened by how many papers they share. Only Al Ain '
          + 'colleagues can be named \u2014 Scopus does not serve outside '
          + 'co-author lists to these keys.';
      })(),
      coCentre: (() => {
        const p_ = AUTHORS.find(a => a.key === this.state.author) || AUTHORS[0];
        return (p_ && p_.name ? p_.name.trim().slice(0, 1) : 'A').toUpperCase();
      })(),
      coNodes: (() => {
        const st = (window.__AAU && window.__AAU.state) || {};
        const p_ = AUTHORS.find(a => a.key === this.state.author) || AUTHORS[0];
        const rows = ((st.coauthors || {})[(p_ || {}).key] || []).slice(0, 12);
        if (!rows.length) return [];
        const W = 640, H = 420, CX = W / 2, CY = H / 2, R = 150;
        const max = rows[0][1] || 1;
        return rows.map((r, i) => {
          const ang = (2 * Math.PI * i) / rows.length - Math.PI / 2;
          const cos = Math.cos(ang), sin = Math.sin(ang);
          const cx = CX + R * cos, cy = CY + R * sin;
          const rad = 9 + Math.round(13 * r[1] / max);
          // The label sits outside the node, on the side the node lies.
          const out = rad + 9;
          const lw = 150;
          const right = cos > 0.25, left = cos < -0.25;
          return {
            cx: Math.round(cx), cy: Math.round(cy), r: rad,
            x2: Math.round(CX + (cos * (R - rad))),
            y2: Math.round(CY + (sin * (R - rad))),
            w: Math.max(1.5, (3.5 * r[1] / max)).toFixed(1),
            name: r[0], n: '\u00d7' + r[1], college: r[2] || '',
            title: r[0] + (r[2] ? ' \u2014 ' + r[2] : '') + ' \u00b7 '
              + r[1] + (r[1] === 1 ? ' shared paper' : ' shared papers'),
            lleft: Math.round(right ? cx + out
                   : (left ? cx - out - lw : cx - lw / 2)) + 'px',
            ltop: Math.round(cy - 9) + 'px',
            lwidth: lw + 'px',
            lalign: right ? 'left' : (left ? 'right' : 'center'),
          };
        });
      })(),
      // ---- the corpus ----------------------------------------------------
      corpusReady: CORPUS.length > 0,
      corpusNote: (() => {
        if (!CORPUS.length) return 'Loading the paper list\u2026';
        const q = (this.state.pq || '').trim().toLowerCase();
        const n = q ? CORPUS.filter(r => (r[0] + ' ' + r[1]).toLowerCase()
          .indexOf(q) >= 0).length : CORPUS.length;
        return q
          ? n.toLocaleString() + ' of ' + CORPUS.length.toLocaleString()
            + ' papers match \u201c' + q + '\u201d'
          : 'Every paper in the current window, newest first.';
      })(),
      onPaperSearch: (e) => this.setState({ pq: e.target.value, pn: 60 }),
      pq: this.state.pq || '',
      corpusRows: (() => {
        const q = (this.state.pq || '').trim().toLowerCase();
        const lim = this.state.pn || 60;
        const out = [];
        for (let i = 0; i < CORPUS.length && out.length < lim; i++) {
          const r = CORPUS[i];
          if (q && (r[0] + ' ' + r[1]).toLowerCase().indexOf(q) < 0) continue;
          out.push({
            title: r[0] || '(untitled)', journal: r[1] || '', year: r[2],
            cited: (r[3] || 0).toLocaleString(),
            kind: r[4] || '', sweep: r[7] ? 'found by author' : '',
            aau: (r[8] && r[8].length)
              ? r[8].map(x => x[1] ? (x[0] + ' (' + x[1] + ')') : x[0]).join(', ')
              : '\u2014',
            aauTitle: (r[8] && r[8].length)
              ? ('Al Ain authors on this paper: '
                 + r[8].map(x => x[1] ? (x[0] + ' \u2014 ' + x[1]) : x[0]).join('; '))
              : 'No Al Ain author on this paper was matched to the roster.',
            sweepShow: r[7] ? 'inline-block' : 'none',
            url: r[5] ? 'https://doi.org/' + r[5] : '',
            urlShow: r[5] ? 'inline' : 'none',
          });
        }
        return out;
      })(),
      moreCorpus: () => this.setState({ pn: (this.state.pn || 60) + 120 }),
      moreCorpusShow: (() => {
        const q = (this.state.pq || '').trim().toLowerCase();
        const n = q ? CORPUS.filter(r => (r[0] + ' ' + r[1]).toLowerCase()
          .indexOf(q) >= 0).length : CORPUS.length;
        return (this.state.pn || 60) < n ? 'inline-block' : 'none';
      })(),
      reviewLabel: (S_ ? (S_.review === 1 ? '1 needs a decision'
                          : S_.review + ' need a decision')
                       : '8 need a decision'),
      pieTotal: pieTotal.toLocaleString(),
      windowChip: (S_ && S_.years && S_.years.length)
        ? ('Window ' + (S_.years.length > 1
            ? S_.years[0] + '\u2013' + S_.years[S_.years.length - 1]
            : String(S_.years[0])))
        : 'Window 2025\u20132026',
      asOfChip: (() => {
        const g = (window.__AAU && window.__AAU.state || {}).generated;
        return g ? ('As of ' + String(g).slice(0, 10)) : 'Roster 2026-08-27';
      })(),
      deltaLine: (() => {
        const A = window.__AAU;
        if (!A || !A.live) return 'Nothing changed. No new papers, no new people.';
        const d = (A.state || {}).delta || null;
        if (!d) return 'No previous run to compare against yet.';
        if (d.first_run) return 'This was the first run, so there is nothing to compare it with.';
        const bits = [];
        const n = (v) => Number(v || 0);
        if (n(d.new_papers)) bits.push(n(d.new_papers).toLocaleString()
          + (n(d.new_papers) === 1 ? ' new paper' : ' new papers'));
        if (n(d.new_people)) bits.push(n(d.new_people).toLocaleString()
          + (n(d.new_people) === 1 ? ' author never seen before' : ' authors never seen before'));
        if (n(d.returning)) bits.push(n(d.returning).toLocaleString() + ' publishing again');
        if (n(d.updated)) bits.push(n(d.updated).toLocaleString() + ' updated');
        if (!bits.length) return 'Nothing changed. No new papers, no new people.';
        return bits.join(', ') + (d.since ? ' since the run on ' + String(d.since).slice(0, 8) : '') + '.';
      })(),
      moreLabel: (() => {
        const shown = (PAPERS[(AUTHORS.find(a => a.key === this.state.author)
          || AUTHORS[0] || {}).key] || []).length;
        const tot = ((AUTHORS.find(a => a.key === this.state.author)
          || AUTHORS[0] || {}).papers) || 0;
        if (!shown) return tot
          ? 'The paper list was not in the last run\\u2019s output.'
          : 'No papers in this window.';
        const more = Math.max(0, tot - shown);
        return more ? more.toLocaleString() + ' more papers' : 'That is all of them.';
      })(),
      rosterHead: (S_ ? S_.roster_people.toLocaleString() + ' people across '
        + COLLEGE_DATA.length + ' colleges' : '208 people across eight colleges'),
      rosterSub: (S_ ? S_.resolved + ' of the ' + S_.academics
        + ' on the roster resolved to a Scopus author. Open a college to see '
        + 'its authors.'
        : 'Open a college to see its authors.'),
"""

# ---------------------------------------------------------------------------
# Round 2. Everything below came from looking at the deployed page.
# ---------------------------------------------------------------------------

ROUND2 = [

    # Workflow first: it explains what a run is before showing the result of
    # one. And the Roster badge said 8 while the dashboard tile said 6 -- two
    # different counts of the same thing, so the badge goes entirely.
    ("tabs: workflow first, and drop the review badge",
     "    const TABS = [\n"
     "      ['dash', 'Dashboard', null],\n"
     "      ['roster', 'Roster', '8'],\n"
     "      ['author', 'Authors', null],\n"
     "      ['export', 'Exports', null],\n"
     "      ['sched', 'Schedule', null],\n"
     "      ['flow', 'Workflow', null],\n"
     "    ];",
     "    const TABS = [\n"
     "      ['flow', 'Workflow', null],\n"
     "      ['dash', 'Dashboard', null],\n"
     "      ['roster', 'Roster', null],\n"
     "      ['author', 'Authors', null],\n"
     "      ['papers', 'Papers', null],\n"
     "      ['net', 'Collaboration and Network', null],\n"
     "      ['export', 'Exports', null],\n"
     "      ['sched', 'Schedule', null],\n"
     "    ];"),

    # The third tile counted names needing a decision -- a figure that
    # disagreed with the Roster badge. Back to what the sweep actually did,
    # which is live and cannot contradict anything.
    ("dashboard: third tile is the sweep, not a disputed count",
     "      { v: String(S_.review), l: 'need a decision',\n"
     "        sub: 'names matching more than one Scopus author', color: accent },",
     "      { v: String(S_.swept_in == null ? 0 : S_.swept_in),\n"
     "        l: 'added by the sweep',\n"
     "        sub: 'found on an author, not on the university tag', color: accent },"),

    # ---- the workflow diagram carries no figures ---------------------------
    # It is an explanation of how a run works, not a report of one. Numbers on
    # it go stale the moment a run finishes and then quietly contradict the
    # dashboard. The words stay; every metric goes.
    ("workflow: no figure on the roster source",
     '<div style="font-size:12.5px;color:#63736A;margin-top:3px">208 people · '
     '8 colleges · who belongs to AAU</div>',
     '<div style="font-size:12.5px;color:#63736A;margin-top:3px">Who the '
     'university says belongs to it</div>'),

    ("workflow: no figure on node 01",
     '<div style="display:flex;align-items:baseline;gap:7px;margin-top:8px">\n'
     '          <span style="font-size:20px;font-weight:800;'
     'letter-spacing:-.02em;color:{{ accent }}">152</span>\n'
     '          <span style="font-size:12.5px;color:#63736A">of 160 resolved'
     '</span>\n        </div>',
     ''),

    ("workflow: no figure on node 02",
     '<div style="display:flex;align-items:baseline;gap:7px;margin-top:8px">\n'
     '          <span style="font-size:20px;font-weight:800;'
     'letter-spacing:-.02em;color:{{ accent }}">1,330</span>\n'
     '          <span style="font-size:12.5px;color:#63736A">papers, '
     '2025–2026</span>\n        </div>',
     ''),

    ("workflow: no figure on node 03",
     '<div style="display:flex;align-items:baseline;gap:7px;margin-top:8px">\n'
     '          <span style="font-size:20px;font-weight:800;'
     'letter-spacing:-.02em;color:{{ accent }}">73</span>\n'
     '          <span style="font-size:12.5px;color:#63736A">candidates '
     'returned</span>\n        </div>',
     ''),

    ("workflow: no figure on node 04",
     '<div style="display:flex;align-items:baseline;gap:7px;margin-top:8px">\n'
     '          <span style="font-size:22px;font-weight:800;'
     'letter-spacing:-.02em;color:{{ accent }}">1,336</span>\n'
     '          <span style="font-size:12.5px;color:#63736A">papers · 511 '
     'people</span>\n        </div>',
     ''),

    # The rejected box sat at x 838-1088 while the "no" branch drops at x=922,
    # and it overlapped "Files to download" (which starts at 1072) by 16px.
    # Centred on the connector at 922 it spans 797-1047: aligned, 25px clear.
    ("workflow: centre the rejected box under the gate, clear of Files",
     'style="animation-delay:.56s;position:absolute;left:838px;top:350px;'
     'width:250px;height:84px;background:#FCF4F5',
     'style="animation-delay:.56s;position:absolute;left:797px;top:350px;'
     'width:250px;height:84px;background:#FCF4F5'),

    ("workflow: the rejected box states the rule, not a count",
     '<div style="display:flex;align-items:baseline;gap:9px">\n'
     '          <span style="font-size:24px;font-weight:800;color:#E0303F;'
     'line-height:1">67</span>\n'
     '          <span style="font-size:13.5px;font-weight:700;color:#8B2A32">'
     'rejected</span>\n        </div>',
     '<div style="font-size:13.5px;font-weight:700;color:#8B2A32">Rejected'
     '</div>'),

    # ---- the two explainer cards quoted specific people and counts ---------
    ("workflow: explain the gate without quoting a count",
     "A sweep by author returns everything that person published anywhere. "
     "Asking for one professor's papers returns 53, and only 30 print an "
     "AAU address. Without the gate the census re-inflates by hundreds of "
     "papers belonging to other universities.",
     "A sweep by author returns everything that person published anywhere, "
     "including work they did at other universities. Without the gate the "
     "census re-inflates with papers that were never AAU's."),

    ("workflow: explain near-misses without quoting a count",
     'The roster writes Al-Takhayneh, Scopus prints Al-Tkhayneh. One vowel '
     'apart. Exact matching misses it and a professor with 39 papers '
     'disappears, so near-misses are checked separately before anyone is '
     'called new.',
     'The roster writes Al-Takhayneh, Scopus prints Al-Tkhayneh. One vowel '
     'apart. Exact matching misses it and a whole career disappears, so '
     'near-misses are checked separately before anyone is called new.'),

    # Begin lands on Workflow: read how a run works, then look at one.
    ("welcome: begin lands on the workflow, not the dashboard",
     "enter: () => this.setState({ screen: 'dash' }),",
     "enter: () => this.setState({ screen: 'flow' }),"),

    # ---- the exports screen described files that did not exist -------------
    # "Fourteen slides", "1,336 rows", "5 native charts": all literals, and all
    # wrong the moment a run finished. Each line now names something the engine
    # actually writes, counted from the run it came from.
    ("exports: describe the files the engine really writes",
     "    const exports = [",
     "    const nCol = COLLEGE_DATA.length;\n"
     "    const fig = (n) => (S_ ? Number(n || 0).toLocaleString() + ' rows'\n"
     "                           : 'from the last run');\n"
     "    const CHART_LIST = [\n"
     "      ['Papers by college', 'bar'],\n"
     "      ['Faculty on the roster, by college', 'bar'],\n"
     "      ['Every author on an AAU paper', 'split bar'],\n"
     "      ['Most published on the roster', 'bar'],\n"
     "      ['Career standing against output', 'scatter'],\n"
     "    ];\n"
     "    const exports = [\n"
     "      { kind: 'xlsx', title: 'Excel workbook',\n"
     "        sub: 'Every row behind the figures on the dashboard',\n"
     "        delay: '0s', btn: 'Download workbook', btnBg: accent,\n"
     "        btnFg: '#ffffff', btnBorder: accent,\n"
     "        chip: 'XLSX', path: 'downloads/AAU_Research_Tracker.xlsx',\n"
     "        items: [\n"
     "          { label: 'Summary', meta: 'headline figures' },\n"
     "          { label: 'People', meta: fig(S_ && S_.authors) },\n"
     "          { label: 'Papers', meta: fig(S_ && S_.papers) },\n"
     "          { label: 'By college', meta: nCol + ' rows' },\n"
     "          { label: 'Suggested additions',\n"
     "            meta: fig(S_ && S_.suggested) },\n"
     "          { label: 'Rejected papers, with the reason',\n"
     "            meta: fig(S_ && S_.rejected) },\n"
     "        ] },\n"
     "      { kind: 'pptx', title: 'Slide deck',\n"
     "        sub: 'A cover and one slide per chart, ready to present',\n"
     "        delay: '.05s', btn: 'Download deck', btnBg: accent,\n"
     "        btnFg: '#ffffff', btnBorder: accent,\n"
     "        chip: 'PPTX', path: 'downloads/AAU_Research_Tracker.pptx',\n"
     "        items: [{ label: 'Cover, with the headline figures',\n"
     "                  meta: '1 slide' }].concat(\n"
     "          CHART_LIST.map(([n]) => ({ label: n, meta: '1 slide' }))) },\n"
     "      { kind: 'charts', title: 'Chart pack',\n"
     "        sub: 'Every chart as its own image, in one zip',\n"
     "        delay: '.1s', btn: 'Download charts', btnBg: '#ffffff',\n"
     "        btnFg: accent, btnBorder: '#C3D6CA',\n"
     "        chip: 'ZIP', path: 'downloads/AAU_Charts.zip',\n"
     "        items: CHART_LIST.map(([n, k]) => ({ label: n, meta: k })) },\n"
     "    ];\n"
     "    const exportsUnused = ["),


    # The strip along the bottom previewed five charts the engine does not make
    # and captioned them with figures ("161 against 350") from nowhere. It now
    # previews the five it does make, with no invented numbers.
    ("exports: the chart strip previews the real charts",
     "    const chartKinds = [\n"
     "      { label: 'Papers by college', note: 'ten colleges, sorted', "
     "bars: bars([100, 96, 94, 86, 28, 20, 16, 15], accent) },\n"
     "      { label: 'Share of credits', note: 'as a ring', "
     "bars: bars([70, 70, 70, 70, 70], '#C3D6CA') },\n"
     "      { label: 'h-index bands', note: 'seven bands', "
     "bars: bars([100, 51, 33, 21, 9, 4, 2], accent) },\n"
     "      { label: 'Faculty and students', note: '161 against 350', "
     "bars: bars([32, 68, 32, 68, 32], '#C3D6CA') },\n"
     "      { label: 'Papers per year', note: '2025 against 2026', "
     "bars: bars([100, 57], accent) },\n"
     "    ];",
     "    const chartKinds = [\n"
     "      { label: 'Papers by college', note: 'one bar per college', "
     "bars: bars([100, 96, 94, 86, 28, 20, 16, 15], accent) },\n"
     "      { label: 'Faculty on the roster', note: 'by college', "
     "bars: bars([100, 88, 70, 62, 26, 24, 8, 4], accent) },\n"
     "      { label: 'Every author on a paper', note: 'roster against the rest', "
     "bars: bars([32, 68], '#C3D6CA') },\n"
     "      { label: 'Most published', note: 'the roster, ranked', "
     "bars: bars([100, 62, 52, 44, 40, 34, 30, 26], accent) },\n"
     "      { label: 'Standing against output', note: 'h-index and papers', "
     "bars: bars([18, 44, 30, 72, 55, 90, 40], '#C3D6CA') },\n"
     "    ];"),

    # the little file-type chip lost its capitals when kind became the api key
    ("exports: keep the file-type chip in capitals",
     ">{{ e.kind }}<", ">{{ e.chip }}<"),

    # ---- the six stages show what is really happening ----------------------
    # Locally that is the engine's own progress; on the published page it is
    # GitHub's, because the six stages are six real workflow steps. Either way
    # the bar moves because work finished, never because time passed.
    ("dashboard: the six stages read live progress",
     "    const stages = stageDefs.map((d, i) => {\n"
     "      const pct = running ? d[2] : 100;\n"
     "      const done = pct >= 100;\n"
     "      const active = running && d[2] > 0 && d[2] < 100;",
     "    const LIVE_ = (window.__AAU && window.__AAU.status\n"
     "      && window.__AAU.status.stages) || null;\n"
     "    const stages = stageDefs.map((d, i) => {\n"
     "      const L_ = LIVE_ ? (LIVE_[i] || {}) : null;\n"
     "      const pct = L_ ? (L_.pct || 0) : (running ? d[2] : 100);\n"
     "      const done = pct >= 100;\n"
     "      const active = L_ ? !!L_.active\n"
     "        : (running && d[2] > 0 && d[2] < 100);\n"
     "      const lab_ = String((L_ && L_.label) || '');\n"
     "      const bad = /fail|cancel|timed|error/i.test(lab_);\n"
     "      const skip = /skip/i.test(lab_);\n"
     "      const ok = done && !bad && !skip;"),

    ("dashboard: a failed or skipped stage is not a green tick",
     "        mark: done ? '\u2713' : String(i + 1),",
     "        mark: bad ? '\u2715' : (skip ? '\u2013'\n"
     "          : (ok ? '\u2713' : String(i + 1))),"),

    ("dashboard: nor a green dot",
     "        dotBg: done ? accent : (active ? '#ffffff' : '#F4F6F5'),",
     "        dotBg: bad ? '#E0303F' : (skip ? '#E4EAE6'\n"
     "          : (ok ? accent : (active ? '#ffffff' : '#F4F6F5'))),"),

    ("dashboard: nor a green bar",
     "        barColor: pct > 0 ? accent : '#EDF1EE',",
     "        barColor: bad ? '#E0303F' : (skip ? '#E4EAE6'\n"
     "          : (pct > 0 ? accent : '#EDF1EE')),"),

    ("dashboard: the caption reads in the failure colour",
     "        statusColor: active ? accent : '#63736A',",
     "        statusColor: bad ? '#E0303F' : (active ? accent : '#63736A'),"),

    ("dashboard: the stage caption is the live one",
     "        status: running ? d[3] : 'Done',",
     "        status: L_ ? (L_.label || (done ? 'Done' : 'Waiting'))\n"
     "          : (running ? d[3] : 'Done'),"),

    # "Stage 4 of 6" has to count the stage that is really running
    ("dashboard: the stage counter follows the live run",
     "      runTitle: running ? 'Run in progress'",
     "      stageNow: (LIVE_ ? (LIVE_.filter(x => x.pct >= 100).length + 1)\n"
     "        : stages.filter(s => s.pct >= 100).length + 1),\n"
     "      runTitle: running ? 'Run in progress'"),

    ("dashboard: 'Stage 4 of 6' counts the real stage",
     ">Stage 4 of 6</span>", ">Stage {{ stageNow }} of 6</span>"),

    # Once live data replaces PAPERS, the hardcoded fallback key is gone. With
    # a selected author who has no papers in the window, rows was undefined and
    # renderVals threw -- taking the whole screen with it.
    ("authors: an author with no papers is not a crash",
     "    const rows = PAPERS[p.key] || PAPERS.tkhayneh;",
     "    const rows = PAPERS[p.key] || PAPERS.tkhayneh || [];"),

    ("workflow: a plainer heading",
     ">Six stages, roster first, Scopus second</div>",
     ">How this works</div>"),

    # ---- the papers table showed nothing, and could show the WRONG person --
    # Two faults, one line apart. "more" was p.papers - 6, arithmetic on the
    # design-time placeholder count, so it said "93 more papers" whether six
    # rows rendered or none. And the || PAPERS.tkhayneh fallback printed one
    # professor's publications under another person's name whenever the map
    # had no entry for them -- worse than an empty table, because it is wrong
    # rather than absent.
    ("authors: count the rows actually shown, and never borrow another person's",
     "S.find(a => a.key === this.state.author) || AUTHORS[0];\n"
     "    const pick = {",
     "S.find(a => a.key === this.state.author) || AUTHORS[0];\n"
     "    const myRows = (PAPERS[p.key] || []);\n"
     "    const pick = {"),

    ("authors: 'more' is what is not on screen",
     "auid: p.auid, papers: p.papers, more: p.papers - 6,",
     "auid: p.auid, papers: p.papers,\n"
     "      more: Math.max(0, (p.papers || 0) - myRows.length),\n"
     "      hasRows: myRows.length > 0,"),

    ("authors: rows come from this author only",
     "    const rows = PAPERS[p.key] || PAPERS.tkhayneh || [];",
     "    const rows = myRows;"),

    ("authors: say nothing rather than '0 more papers'",
     ">{{ pick.more }} more papers</div>",
     ">{{ pick.moreLabel }}</div>"),

    # ---- the donut divided by zero -----------------------------------------
    # With every college at 0, pieTotal is 0 and share is 0/0 = NaN, so each
    # arc got stroke-dasharray="NaN 628.32" -- invalid, and the ring rendered
    # as one flat band. That is what the flat grey donut in the screenshot was.
    ("donut: a total of zero must not become NaN",
     "      const share = r[1] / pieTotal;",
     "      const share = pieTotal > 0 ? (r[1] / pieTotal) : 0;"),

    # The design never interpolates a text node inside SVG -- only attributes,
    # and the runtime does not support it: {{ pieTotal }} in a <text> rendered
    # empty and the donut lost its centre entirely. Both centre labels move to
    # an HTML overlay, where every other live figure on this page already is.
    ("donut: blank the two static SVG centre labels",
     '<text x="120" y="114" text-anchor="middle" font-family="Archivo, '
     'sans-serif" font-size="40" font-weight="800" fill="#1A1A1A">1,351</text>\n'
     '              <text x="120" y="140" text-anchor="middle" '
     'font-family="Archivo, sans-serif" font-size="18" font-weight="600" '
     'fill="#63736A">CREDITS</text>',
     ''),

    ("donut: open an overlay wrapper around the ring",
     '<svg width="176" height="176" sc-camel-view-box="0 0 240 240" '
     'style="display:block;flex:0 0 auto">',
     '<div style="position:relative;flex:0 0 auto;width:176px;height:176px">'
     '<div style="position:absolute;inset:0;display:flex;'
     'flex-direction:column;align-items:center;justify-content:center;'
     'pointer-events:none;text-align:center">'
     '<div style="font-size:28px;font-weight:800;letter-spacing:-.02em;'
     'line-height:1;color:#1A1A1A">{{ pieTotal }}</div>'
     '<div style="font-size:11.5px;font-weight:600;letter-spacing:.06em;'
     'margin-top:4px;color:#63736A">CREDITS</div></div>'
     '<svg width="176" height="176" sc-camel-view-box="0 0 240 240" '
     'style="display:block">'),

    ("donut: close that wrapper after the ring",
     '</svg>\n            <div style="flex:1;min-width:0">',
     '</svg></div>\n            <div style="flex:1;min-width:0">'),

    # ---- the roster header repeated stale figures --------------------------
    ("roster: header figures come from the run",
     '<div style="font-size:25px;font-weight:700;letter-spacing:-.02em;'
     'margin-top:6px">208 people across eight colleges</div>',
     '<div style="font-size:25px;font-weight:700;letter-spacing:-.02em;'
     'margin-top:6px">{{ rosterHead }}</div>'),

    ("roster: subtitle too",
     '<div style="font-size:13.5px;color:#63736A;margin-top:5px">152 of the '
     '160 academics resolved to a Scopus author. Open a college to see its '
     'authors.</div>',
     '<div style="font-size:13.5px;color:#63736A;margin-top:5px">'
     '{{ rosterSub }}</div>'),
    # ---- the run caption claimed a run that never happened -----------------
    ("dashboard: the run caption names a real moment or says nothing",
     "      runMeta: running\n"
     "        ? 'Started 06:00 \u00b7 roster 2026-08-27 \u00b7 about three "
     "minutes left'\n"
     "        : '27 August at 01:06 \u00b7 took 5 minutes 20 seconds',",
     "      runMeta: (function () {\n"
     "        var A = window.__AAU;\n"
     "        if (!A || !A.live) return running\n"
     "          ? 'Started 06:00 \u00b7 roster 2026-08-27 \u00b7 about three "
     "minutes left'\n"
     "          : '27 August at 01:06 \u00b7 took 5 minutes 20 seconds';\n"
     "        if (running) return A.canRun ? 'Running on this machine'\n"
     "                                     : 'Running on GitHub';\n"
     "        var g = (A.state || {}).generated;\n"
     "        if (!g) return 'not run from this page yet';\n"
     "        var d = new Date(g);\n"
     "        if (isNaN(d.getTime())) return 'last run ' + String(g).slice(0, 10);\n"
     "        return d.toLocaleDateString(undefined,\n"
     "                 { day: 'numeric', month: 'long' })\n"
     "          + ' at ' + d.toLocaleTimeString(undefined,\n"
     "                 { hour: '2-digit', minute: '2-digit' });\n"
     "      })(),"),

    ("dashboard: findings come from the run, finished or in flight",
     "    const liveF_ = (window.__AAU && window.__AAU.status\n"
     "      && window.__AAU.status.findings) || null;",
     "    const liveF_ = (window.__AAU && ((window.__AAU.status\n"
     "      && window.__AAU.status.findings\n"
     "      && window.__AAU.status.findings.length\n"
     "      && window.__AAU.status.findings)\n"
     "      || (window.__AAU.state && window.__AAU.state.findings))) || null;"),

    ("dashboard: the delta is read, not asserted",
     '<div style="font-size:14.5px;color:#3A4A41;line-height:1.45">Nothing '
     'changed. No new papers, no new people.</div>',
     '<div style="font-size:14.5px;color:#3A4A41;line-height:1.45">'
     '{{ deltaLine }}</div>'),

    ("header: the window chip is the window the run covered",
     "<span>Window 2025\u20132026</span>",
     "<span>{{ windowChip }}</span>"),

    ("header: the second chip names when the figures are from",
     "<span>Roster 2026-08-27</span>",
     "<span>{{ asOfChip }}</span>"),
    # The staff profile navigated the whole app away in the same tab: the
    # reader lost the screen they were reading to look at one link.
    ("authors: the staff profile opens in a new tab",
     '<a href="{{ pick.url }}" style="font-size:13px;font-weight:600;',
     '<a href="{{ pick.url }}" target="_blank" rel="noopener noreferrer" '
     'style="font-size:13px;font-weight:600;'),
    # ---- the roster needed a second way in, and a way to ask ---------------
    # A whole CSV is the wrong shape for "we hired someone in March", and
    # nobody should have to guess the columns before building a file.
    ("roster: add-a-person and a help affordance beside the import",
     '<div style="display:flex;gap:10px">\n'
     '        <button type="button" sc-camel-on-click="{{ importCsv }}" '
     'style="background:#ffffff;color:{{ accent }};border:1px solid #C3D6CA;'
     'border-radius:6px;padding:10px 17px;font-family:Archivo,sans-serif;'
     'font-size:13.5px;font-weight:600;cursor:pointer">Import roster CSV'
     '</button>',
     '<div style="display:flex;gap:10px;align-items:center">\n'
     '        <button type="button" sc-camel-on-click="{{ addPerson }}" '
     'title="Add one person by hand" '
     'style="background:{{ accent }};color:#ffffff;border:0;'
     'border-radius:6px;padding:10px 17px;font-family:Archivo,sans-serif;'
     'font-size:13.5px;font-weight:600;cursor:pointer">Add a person</button>\n'
     '        <button type="button" sc-camel-on-click="{{ importCsv }}" '
     'title="Import a whole roster from a CSV file" '
     'style="background:#ffffff;color:{{ accent }};border:1px solid #C3D6CA;'
     'border-radius:6px;padding:10px 17px;font-family:Archivo,sans-serif;'
     'font-size:13.5px;font-weight:600;cursor:pointer">Import roster CSV'
     '</button>\n'
     '        <button type="button" sc-camel-on-click="{{ csvHelp }}" '
     'title="Which columns the CSV needs" aria-label="What the CSV needs" '
     'style="background:#ffffff;color:{{ accent }};border:1px solid #C3D6CA;'
     'border-radius:50%;width:32px;height:32px;flex:0 0 auto;'
     'font-family:Archivo,sans-serif;font-size:14px;font-weight:700;'
     'cursor:pointer;line-height:1">?</button>'),

    # the review-queue button counted with a literal
    ("roster: the review button counts what is really waiting",
     '>8 need a decision</button>',
     '>{{ reviewLabel }}</button>'),
    # ---- a way to take somebody off, next to each person -------------------
    ("roster: an x on each person in a college",
     '<div><span style="font-size:12px;font-weight:600;color:{{ a.tagFg }};'
     'background:{{ a.tagBg }};padding:3px 9px;border-radius:4px">{{ a.tag }}'
     '</span></div>',
     '<div style="display:flex;align-items:center;gap:8px">'
     '<span style="font-size:12px;font-weight:600;color:{{ a.tagFg }};'
     'background:{{ a.tagBg }};padding:3px 9px;border-radius:4px">{{ a.tag }}'
     '</span>'
     '<button type="button" sc-camel-on-click="{{ a.drop }}" '
     'title="{{ a.dropTitle }}" aria-label="{{ a.dropTitle }}" '
     'style="background:none;border:0;padding:0 2px;cursor:pointer;'
     'font-family:Archivo,sans-serif;font-size:15px;line-height:1;'
     'color:#B9C4BD;visibility:{{ a.dropShow }}">&times;</button></div>'),
    ("roster: each college row can drop that person",
     "      open: () => this.setState({ screen: 'author', author: a.key, "
     "college: null }),\n    }));",
     "      open: () => this.setState({ screen: 'author', author: a.key, "
     "college: null }),\n"
     "      drop: () => window.__AAU\n"
     "        && window.__AAU.removePerson(this, a.name, a.college),\n"
     "      dropShow: a.tag === 'Faculty' ? 'visible' : 'hidden',\n"
     "      dropTitle: 'Take ' + a.name + ' off the roster',\n"
     # Zero is not "0 papers", it is one of two different facts, and the roster
     # should say which. Someone AAU prints no Scopus link for was not on this
     # screen at all until now.
     "      papersLabel: a.papers ? a.papers.toLocaleString() : '\\u2014',\n"
     "      papersWhy: a.papers ? (a.papers + ' papers in this window')\n"
     "        : (a.why_no_papers || 'no papers in this window'),\n"
     "      flag: a.no_scopus ? 'no Scopus record' : '',\n"
     "      flagShow: a.no_scopus ? 'inline-block' : 'none',\n"
     # The programme is what the roster is filed BY, and it was nowhere on the
     # screen that lists the roster.
     "      progs: (a.programs && a.programs.length)\n"
     "        ? a.programs.join(' \\u00b7 ')\n"
     "        : 'AAU lists no programme for them',\n"
     "      progsColor: (a.programs && a.programs.length) ? '#63736A' : '#B0B9B4',\n"
     "    }));"),

    ("roster: each person shows the programme they are filed under",
     '<div style="font-size:13px;color:#3A4A41">{{ a.title }}</div>',
     # min-width:0 is load-bearing. A grid column sized in fr still has an
     # automatic minimum of its content, so the long programme line stretched
     # the Title column past its share -- and because the header row is a
     # SEPARATE grid with the same template but shorter content, the two
     # resolved to different widths and stopped lining up.
     '<div style="min-width:0"><div style="font-size:13px;color:#3A4A41;'
     'overflow:hidden;text-overflow:ellipsis;white-space:nowrap">'
     '{{ a.title }}</div>\n'
     '            <div title="{{ a.progs }}" style="font-size:11.5px;'
     'color:{{ a.progsColor }};margin-top:3px;line-height:1.35;'
     'overflow:hidden;text-overflow:ellipsis;white-space:nowrap">'
     '{{ a.progs }}</div></div>'),

    ("roster: and marks anyone AAU publishes no Scopus record for",
     '<button type="button" sc-camel-on-click="{{ a.open }}" style="text-align:left;'
     'background:none;border:0;padding:0;font-family:Archivo,sans-serif;'
     'font-size:14.5px;font-weight:600;color:{{ accent }};cursor:pointer">'
     '{{ a.name }}</button>',
     '<div style="min-width:0"><button type="button" '
     'sc-camel-on-click="{{ a.open }}" '
     'style="text-align:left;background:none;border:0;padding:0;'
     'font-family:Archivo,sans-serif;font-size:14.5px;font-weight:600;'
     'color:{{ accent }};cursor:pointer">{{ a.name }}</button>'
     '<span title="AAU\u2019s directory prints no Scopus author link on this '
     'card, so there is no record to count papers from." '
     'style="display:{{ a.flagShow }};margin-left:8px;padding:1px 7px;'
     'border:1px solid #E0D5B8;border-radius:9px;background:#FBF6E9;'
     'font-size:11px;color:#8A6D1F;white-space:nowrap">{{ a.flag }}</span></div>'),

    ("roster: no cell may stretch its column past the header's",
     '<div style="display:grid;grid-template-columns:1.7fr 1.1fr 90px 78px '
     '90px 120px;gap:14px;align-items:center;padding:11px 0;'
     'border-bottom:1px solid #F0F3F1">',
     '<div style="display:grid;grid-template-columns:1.7fr 1.1fr 90px 78px '
     '90px 120px;gap:14px;align-items:center;padding:11px 0;'
     'border-bottom:1px solid #F0F3F1;min-width:0">'),

    ("roster: a zero says which kind of zero it is",
     '<div style="font-size:14px;text-align:right;font-variant-numeric:'
     'tabular-nums">{{ a.papers }}</div>',
     '<div title="{{ a.papersWhy }}" style="font-size:14px;text-align:right;'
     'font-variant-numeric:tabular-nums">{{ a.papersLabel }}</div>'),
    # ---- college -> programme -> people ------------------------------------
    # AAU publishes which programmes each person teaches on, on the college's
    # own subsite. A person can be on several, so a paper counts for every
    # programme represented on it -- the same whole counting the colleges use.
    ("roster: a programme row inside each college",
     '<div style="background:#ffffff;border-radius:8px;padding:20px 22px">\n'
     '      <div style="display:grid;grid-template-columns:1.7fr 1.1fr 90px '
     '78px 90px 120px;gap:14px;font-size:11.5px;font-weight:700;',
     '<sc-if value="{{ hasPrograms }}" hint-placeholder-val="{{ true }}">\n'
     '    <div data-rise style="animation-delay:.04s;display:flex;'
     'align-items:center;gap:8px;flex-wrap:wrap;margin-bottom:14px">\n'
     '      <span style="font-size:11.5px;font-weight:700;letter-spacing:.07em;'
     'text-transform:uppercase;color:#63736A;margin-right:2px">Programme'
     '</span>\n'
     '      <sc-for list="{{ progChips }}" as="p" hint-placeholder-count="5">\n'
     '        <button type="button" sc-camel-on-click="{{ p.pick }}" '
     'title="{{ p.title }}" '
     'style="background:{{ p.bg }};color:{{ p.fg }};border:1px solid '
     '{{ p.border }};border-radius:14px;padding:5px 12px;'
     'font-family:Archivo,sans-serif;font-size:12.5px;font-weight:600;'
     'cursor:pointer">{{ p.label }}</button>\n'
     '      </sc-for>\n'
     '    </div>\n'
     '    </sc-if>\n'
     '    <div style="background:#ffffff;border-radius:8px;padding:20px 22px">\n'
     '      <div style="display:grid;grid-template-columns:1.7fr 1.1fr 90px '
     '78px 90px 120px;gap:14px;font-size:11.5px;font-weight:700;'),

    # ---- an empty college says so, never borrows somebody else's people ----
    # The design shipped `colAuthors.length ? colAuthors : AUTHORS.slice(0, 3)`
    # so the mockup never showed an empty table. Against real data that is a
    # fabrication: Dentistry has nobody with a paper in the window, so opening
    # it listed the first three authors overall -- El Refae and Tabash, who are
    # Business -- under a Dentistry heading.
    ("roster: an empty college shows nothing, not the first three authors",
     "const filled = colAuthors.length ? colAuthors : AUTHORS.slice(0, 3);",
     "const filled = colAuthors;"),

    ("roster: and says why it is empty",
     '</sc-for>\n    </div>\n  </div>\n  </sc-if>\n\n'
     '  <!-- ============ REVIEW QUEUE ============ -->',
     '</sc-for>\n'
     '      <sc-if value="{{ colEmpty }}" hint-placeholder-val="{{ false }}">\n'
     '      <div style="padding:26px 4px;text-align:center;font-size:13.5px;'
     'color:#63736A">{{ colEmptyNote }}</div>\n'
     '      </sc-if>\n'
     '    </div>\n  </div>\n  </sc-if>\n\n'
     '  <!-- ============ REVIEW QUEUE ============ -->'),

    # ---- two more screens: the corpus, and who AAU publishes with ---------
    ("screens: papers and networking exist",
     "      onSchedule: S === 'sched', onFlow: S === 'flow',",
     "      onSchedule: S === 'sched', onFlow: S === 'flow',\n"
     "      onPapers: S === 'papers', onNet: S === 'net',"),

    # ---- the Networking screen -------------------------------------------
    # Bars are div widths, not SVG: the runtime does not interpolate text
    # nodes inside an svg, and every label here is text.
    ("networking: the screen",
     '<!-- ============ WORKFLOW ============ -->',
     '<sc-if value="{{ onNet }}" hint-placeholder-val="{{ false }}">\n'
     '  <div style="padding:24px 26px 30px">\n'
     '    <div data-rise style="margin-bottom:6px">\n'
     '      <div style="font-size:22px;font-weight:700;color:#1A1A1A">'
     'Networking and Collaboration</div>\n'
     '      <div style="font-size:13.5px;color:#63736A;margin-top:5px;'
     'max-width:900px;line-height:1.5">{{ netNote }}</div>\n'
     '      <div style="font-size:12.5px;color:#8C9A92;margin-top:7px;'
     'max-width:900px;line-height:1.5">{{ netQuar }}</div>\n'
     '      <div style="display:{{ netPendingShow }};margin-top:11px;'
     'max-width:900px;background:#FBF6E9;border:1px solid #E8DCC0;'
     'border-radius:7px;padding:11px 14px;font-size:12.5px;color:#7A6320;'
     'line-height:1.55">{{ netPending }}</div>\n'
     '    </div>\n'
     '    <sc-if value="{{ netReady }}" hint-placeholder-val="{{ true }}">\n'
     '    <div data-rise style="animation-delay:.05s;background:#ffffff;border-radius:8px;padding:20px 22px;margin-bottom:16px">\n'
     '      <div style="font-size:11.5px;font-weight:700;letter-spacing:.07em;text-transform:uppercase;color:#63736A">Who Al Ain University publishes with'
     '</div>\n'
     '      <div style="font-size:12.5px;color:#63736A;margin:6px 0 14px">'
     'The pale bar is the joint paper count; the solid one is the same work '
     'shared out among every institution on each paper.</div>\n'
     '      <sc-for list="{{ netPartners }}" as="r" hint-placeholder-count="8">\n'
     '        <div title="{{ r.title }}" style="display:grid;'
     'grid-template-columns:26px 300px 320px 1fr;gap:12px;align-items:center;'
     'padding:7px 0;border-bottom:1px solid #F0F3F1">\n'
     '          <div style="font-size:12px;color:#8C9A92;'
     'font-variant-numeric:tabular-nums">{{ r.rank }}</div>\n'
     '          <div style="font-size:14px;color:#1A1A1A;overflow:hidden;'
     'text-overflow:ellipsis;white-space:nowrap">{{ r.name }}</div>\n'
     '          <div style="position:relative;height:16px">\n'
     '            <div style="position:absolute;left:0;top:3px;'
     'width:{{ r.barW }};height:10px;border-radius:3px;background:#CDE6D8">'
     '</div>\n'
     '            <div style="position:absolute;left:0;top:3px;'
     'width:{{ r.creditW }};height:10px;border-radius:3px;background:'
     '{{ accent }}"></div>\n'
     '          </div>\n'
     '          <div style="font-size:12.5px;color:#63736A;'
     'font-variant-numeric:tabular-nums">{{ r.papers }} papers \u00b7 '
     '{{ r.cols }} colleges \u00b7 AAU led {{ r.led }}</div>\n'
     '        </div>\n'
     '      </sc-for>\n'
     '    </div>\n'
     '    <div data-rise style="animation-delay:.1s;background:#ffffff;border-radius:8px;padding:20px 22px;margin-bottom:16px">\n'
     '      <div style="font-size:11.5px;font-weight:700;letter-spacing:.07em;text-transform:uppercase;color:#63736A">Each college and its five biggest '
     'partners</div>\n'
     '      <div style="display:grid;grid-template-columns:1fr 1fr;gap:22px;'
     'margin-top:14px">\n'
     '        <sc-for list="{{ netColleges }}" as="c" hint-placeholder-count="6">\n'
     '          <div>\n'
     '            <div style="font-size:13.5px;font-weight:700;color:#1A1A1A;'
     'margin-bottom:7px">{{ c.name }}</div>\n'
     '            <sc-for list="{{ c.rows }}" as="r" hint-placeholder-count="5">\n'
     '              <div style="display:grid;grid-template-columns:1fr 140px '
     '38px;gap:10px;align-items:center;padding:4px 0">\n'
     '                <div style="font-size:12.5px;color:#3A4A41;'
     'overflow:hidden;text-overflow:ellipsis;white-space:nowrap">'
     '{{ r.name }}</div>\n'
     '                <div style="height:8px;border-radius:3px;'
     'background:#EDF1EE"><div style="width:{{ r.barW }};height:8px;'
     'border-radius:3px;background:{{ accent }}"></div></div>\n'
     '                <div style="font-size:12px;color:#63736A;text-align:right;'
     'font-variant-numeric:tabular-nums">{{ r.papers }}</div>\n'
     '              </div>\n'
     '            </sc-for>\n'
     '          </div>\n'
     '        </sc-for>\n'
     '      </div>\n'
     '    </div>\n'
     '    <div style="display:grid;grid-template-columns:1fr 1fr;gap:16px">\n'
     '      <div data-rise style="animation-delay:.15s;background:#ffffff;border-radius:8px;padding:20px 22px;margin-bottom:16px">\n'
     '        <div style="font-size:11.5px;font-weight:700;letter-spacing:.07em;text-transform:uppercase;color:#63736A">Where the partners are</div>\n'
     '        <div style="font-size:12.5px;color:#63736A;margin:6px 0 12px">'
     'Countries as the addresses print them, one count per paper.</div>\n'
     '        <sc-for list="{{ netCountries }}" as="r" hint-placeholder-count="10">\n'
     '          <div style="display:grid;grid-template-columns:1fr 290px 54px;'
     'gap:10px;align-items:center;padding:4px 0">\n'
     '            <div style="font-size:13px;color:#3A4A41">{{ r.name }}</div>\n'
     '            <div style="height:9px;border-radius:3px;background:#EDF1EE">'
     '<div style="width:{{ r.barW }};height:9px;border-radius:3px;'
     'background:#4E9E74"></div></div>\n'
     '            <div style="font-size:12px;color:#63736A;text-align:right;'
     'font-variant-numeric:tabular-nums">{{ r.papers }}</div>\n'
     '          </div>\n'
     '        </sc-for>\n'
     '      </div>\n'
     '      <div data-rise style="animation-delay:.2s;background:#ffffff;border-radius:8px;padding:20px 22px;margin-bottom:16px">\n'
     '        <div style="font-size:11.5px;font-weight:700;letter-spacing:.07em;text-transform:uppercase;color:#63736A">Inside AAU: who works across college '
     'lines</div>\n'
     '        <div style="font-size:12.5px;color:#63736A;margin:6px 0 12px">'
     'Papers carrying authors from two different colleges.</div>\n'
     '        <sc-for list="{{ netJoint }}" as="r" hint-placeholder-count="8">\n'
     '          <div style="display:grid;grid-template-columns:1fr 250px 44px;'
     'gap:10px;align-items:center;padding:4px 0">\n'
     '            <div style="font-size:13px;color:#3A4A41;overflow:hidden;'
     'text-overflow:ellipsis;white-space:nowrap">{{ r.pair }}</div>\n'
     '            <div style="height:9px;border-radius:3px;background:#EDF1EE">'
     '<div style="width:{{ r.barW }};height:9px;border-radius:3px;'
     'background:#7BB894"></div></div>\n'
     '            <div style="font-size:12px;color:#63736A;text-align:right;'
     'font-variant-numeric:tabular-nums">{{ r.papers }}</div>\n'
     '          </div>\n'
     '        </sc-for>\n'
     '      </div>\n'
     '    </div>\n'
     '    </sc-if>\n'
     '  </div>\n'
     '</sc-if>\n\n'
     '<!-- ============ WORKFLOW ============ -->'),

    ("screens: opening a lazy screen asks for its data",
     "  go(s) { return () => this.setState({ screen: s, college: null, review: false }); }",
     "  go(s) {\n"
     "    return () => {\n"
     "      // The corpus and the collaboration file are fetched on the way in,\n"
     "      // once each, so the payload every visitor pays for stays small.\n"
     "      if (window.__AAU) {\n"
     "        if (s === 'net' && window.__AAU.needNetwork) {\n"
     "          window.__AAU.needNetwork(this);\n"
     "        }\n"
     "        if (s === 'papers' && window.__AAU.needCorpus) {\n"
     "          window.__AAU.needCorpus(this);\n"
     "        }\n"
     "      }\n"
     "      this.setState({ screen: s, college: null, review: false,\n"
     "                      program: null, q: '', author: null,\n"
     "                      prog: null, dashCol: null });\n"
     "    };\n"
     "  }"),

    ("papers: the screen",
     '<!-- ============ WORKFLOW ============ -->',
     '<sc-if value="{{ onPapers }}" hint-placeholder-val="{{ false }}">\n'
     '  <div style="padding:24px 26px 30px">\n'
     '    <div data-rise style="display:flex;align-items:flex-end;gap:16px;'
     'margin-bottom:14px">\n'
     '      <div style="flex:1">\n'
     '        <div style="font-size:22px;font-weight:700;color:#1A1A1A">'
     'Papers in this run</div>\n'
     '        <div style="font-size:13.5px;color:#63736A;margin-top:5px">'
     '{{ corpusNote }}</div>\n'
     '      </div>\n'
     '      <input type="text" value="{{ pq }}" sc-camel-on-input="{{ onPaperSearch }}" '
     'placeholder="Search a title or a journal" style="width:320px;'
     'border:1px solid #D5DED8;border-radius:6px;padding:9px 12px;'
     'font-family:Archivo,sans-serif;font-size:13.5px;color:#1A1A1A" />\n'
     '    </div>\n'
     '    <div data-rise style="animation-delay:.05s;background:#ffffff;border-radius:8px;padding:20px 22px">\n'
     '      <div style="display:grid;grid-template-columns:1.35fr 1fr 230px '
     '58px 66px;gap:14px;font-size:11.5px;font-weight:700;'
     'letter-spacing:.06em;text-transform:uppercase;color:#63736A;'
     'padding-bottom:10px;border-bottom:1px solid #E4EAE6">\n'
     '        <div>Title</div><div>Al Ain authors</div><div>Journal</div>'
     '<div style="text-align:right">Year</div>'
     '<div style="text-align:right">Cited</div>\n'
     '      </div>\n'
     '      <sc-for list="{{ corpusRows }}" as="r" hint-placeholder-count="12">\n'
     '        <div title="{{ r.kind }}" style="display:grid;'
     'grid-template-columns:1.35fr 1fr 230px 58px 66px;gap:14px;'
     'align-items:start;padding:9px 0;border-bottom:1px solid #F0F3F1">\n'
     '          <div style="font-size:13.5px;color:#1A1A1A;line-height:1.4">'
     '{{ r.title }}\n'
     '            <a href="{{ r.url }}" target="_blank" rel="noopener" '
     'style="display:{{ r.urlShow }};margin-left:7px;font-size:12px;'
     'text-decoration:none;color:{{ accent }}">doi \u2197</a>\n'
     '            <span title="This paper was not under the university tag; it '
     'came up under a faculty member\u2019s Scopus record and prints an AAU '
     'address." style="display:{{ r.sweepShow }};margin-left:7px;'
     'padding:1px 7px;border:1px solid #C3D6CA;border-radius:9px;'
     'font-size:11px;color:#4E7A5F">{{ r.sweep }}</span>\n'
     '          </div>\n'
     '          <div title="{{ r.aauTitle }}" style="font-size:12.5px;'
     'color:#3A4A41;line-height:1.4">{{ r.aau }}</div>\n'
     '          <div style="font-size:12.5px;color:#63736A;overflow:hidden;'
     'text-overflow:ellipsis;white-space:nowrap">{{ r.journal }}</div>\n'
     '          <div style="font-size:13px;text-align:right;'
     'font-variant-numeric:tabular-nums">{{ r.year }}</div>\n'
     '          <div style="font-size:13px;text-align:right;'
     'font-variant-numeric:tabular-nums">{{ r.cited }}</div>\n'
     '        </div>\n'
     '      </sc-for>\n'
     '      <div style="padding-top:14px;text-align:center">\n'
     '        <button type="button" sc-camel-on-click="{{ moreCorpus }}" '
     'style="display:{{ moreCorpusShow }};background:#ffffff;color:{{ accent }};'
     'border:1px solid #C3D6CA;border-radius:5px;padding:9px 18px;'
     'font-family:Archivo,sans-serif;font-size:13px;font-weight:600;'
     'cursor:pointer">Show more</button>\n'
     '      </div>\n'
     '    </div>\n'
     '  </div>\n'
     '</sc-if>\n\n'
     '<!-- ============ WORKFLOW ============ -->'),

    ("dashboard: top collaborators, under the donut",
     'A paper written across two colleges is credited to both, so the credits '
     'add up to more than the paper count.</div>\n        </div>',
     'A paper written across two colleges is credited to both, so the credits '
     'add up to more than the paper count.</div>\n        </div>\n\n'
     '        <div data-rise style="animation-delay:.125s;display:'
     '{{ dashCollabShow }};background:#ffffff;border-radius:8px;'
     'padding:20px 22px">\n'
     '          <div style="display:flex;align-items:baseline;gap:8px">\n'
     '            <div style="font-size:12px;font-weight:700;letter-spacing:'
     '.1em;text-transform:uppercase;color:{{ accent }};flex:1">'
     'Top collaborators</div>\n'
     '            <button type="button" sc-camel-on-click="{{ goNet }}" '
     'style="background:none;border:0;padding:0;font-family:Archivo,sans-serif;'
     'font-size:12.5px;font-weight:600;color:{{ accent }};cursor:pointer">'
     'All of them \u2192</button>\n'
     '          </div>\n'
     '          <sc-for list="{{ dashCollab }}" as="r" hint-placeholder-count="6">\n'
     '            <div title="{{ r.title }}" style="display:grid;'
     'grid-template-columns:1fr 190px 34px;gap:10px;align-items:center;'
     'padding:6px 0">\n'
     '              <div style="font-size:12.5px;color:#3A4A41;'
     'overflow:hidden;text-overflow:ellipsis;white-space:nowrap">'
     '{{ r.name }}</div>\n'
     '              <div style="position:relative;height:14px">\n'
     '                <div style="position:absolute;left:0;top:3px;'
     'width:{{ r.barW }};height:9px;border-radius:3px;background:#CDE6D8">'
     '</div>\n'
     '                <div style="position:absolute;left:0;top:3px;'
     'width:{{ r.creditW }};height:9px;border-radius:3px;background:'
     '{{ accent }}"></div>\n'
     '              </div>\n'
     '              <div style="font-size:12px;color:#63736A;text-align:right;'
     'font-variant-numeric:tabular-nums">{{ r.papers }}</div>\n'
     '            </div>\n'
     '          </sc-for>\n'
     '          <div style="font-size:11.5px;color:#8C9A92;margin-top:8px;'
     'line-height:1.45">Pale is joint papers; solid is the same work shared '
     'out among every institution on each paper.</div>\n'
     '        </div>'),

    # ---- the Workflow screen ends where the diagram ends ------------------
    # Three boxes explaining the affiliation gate, why a name can be missed,
    # and what a healthy run looks like. They were scaffolding for a reader
    # meeting the tool for the first time; the tool is in daily use now and
    # they are the last thing on the screen every time.
    ("workflow: drop the three explanation boxes",
     '<div style="display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:16px;margin-top:22px">\n      <div data-rise="" style="animation-delay:.1s;background:#ffffff;border-radius:8px;padding:18px 20px;border-left:4px solid {{ accent }}">\n        <div style="font-size:14.5px;font-weight:700">Why the gate exists</div>\n        <div style="font-size:13px;color:#63736A;line-height:1.5;margin-top:7px">A sweep by author returns everything that person published anywhere, including work they did at other universities. Without the gate the census re-inflates with papers that were never AAU\'s.</div>\n      </div>\n      <div data-rise="" style="animation-delay:.14s;background:#ffffff;border-radius:8px;padding:18px 20px;border-left:4px solid {{ accent }}">\n        <div style="font-size:14.5px;font-weight:700">Why a name can be missed</div>\n        <div style="font-size:13px;color:#63736A;line-height:1.5;margin-top:7px">The roster writes Al-Takhayneh, Scopus prints Al-Tkhayneh. One vowel apart. Exact matching misses it and a whole career disappears, so near-misses are checked separately before anyone is called new.</div>\n      </div>\n      <div data-rise="" style="animation-delay:.18s;background:#ffffff;border-radius:8px;padding:18px 20px;border-left:4px solid {{ accent }}">\n        <div style="font-size:14.5px;font-weight:700">What a healthy run looks like</div>\n        <div style="font-size:13px;color:#63736A;line-height:1.5;margin-top:7px">Run it twice on unchanged data and the second run reports nothing new. If it invents an addition, the papers are being matched wrongly, and that is a bug rather than a discovery.</div>\n      </div>\n    </div>',
     ""),

    # ---- the dashboard becomes a card per programme --------------------
    # It reported the machinery: three headline tiles, a donut, a delta and
    # seven findings. A research office wants to know how each programme is
    # doing, so that is what it shows. The run panel stays, because it is how
    # you change the period every one of these numbers describes.
    ("dashboard: drop the three headline tiles",
     '<div data-rise="" style="display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:14px">\n      <sc-for list="{{ tiles }}" as="t" hint-placeholder-count="3">\n        <div style="background:#ffffff;border-radius:8px;padding:18px 20px;border-top:4px solid {{ t.color }}">\n          <div style="font-size:38px;font-weight:800;letter-spacing:-.025em;line-height:1.02;font-variant-numeric:tabular-nums">{{ t.v }}</div>\n          <div style="font-size:14px;font-weight:600;margin-top:7px">{{ t.l }}</div>\n          <div style="font-size:13px;color:#63736A;margin-top:3px;line-height:1.4">{{ t.sub }}</div>\n        </div>\n      </sc-for>\n    </div>',
     ""),

    ("dashboard: the run panel takes the full width",
     'grid-template-columns:1.5fr 1fr;gap:16px;margin-top:16px',
     # The screen's padding wrapper closes right after the tiles -- a quirk
     # of the original design -- so this grid is its sibling and never had
     # any. It did not show while a full-width card filled the row; it does
     # the moment anything sits directly on the page.
     'grid-template-columns:1fr;gap:16px;margin-top:16px;padding:0 26px 30px'),

    ("dashboard: the donut, the collaborators and the delta give way to the programmes",
     '<div style="display:flex;flex-direction:column;gap:16px">\n        <div data-rise="" style="animation-delay:.1s;background:#ffffff;border-radius:8px;padding:20px 22px">\n          <div style="font-size:12px;font-weight:700;letter-spacing:.1em;text-transform:uppercase;color:{{ accent }};margin-bottom:6px">Share of papers by college</div>\n          <div style="display:flex;align-items:center;gap:18px">\n            <div style="position:relative;flex:0 0 auto;width:176px;height:176px"><div style="position:absolute;inset:0;display:flex;flex-direction:column;align-items:center;justify-content:center;pointer-events:none;text-align:center"><div style="font-size:28px;font-weight:800;letter-spacing:-.02em;line-height:1;color:#1A1A1A">{{ pieTotal }}</div><div style="font-size:11.5px;font-weight:600;letter-spacing:.06em;margin-top:4px;color:#63736A">CREDITS</div></div><svg width="176" height="176" sc-camel-view-box="0 0 240 240" style="display:block">\n              <circle cx="120" cy="120" r="100" fill="none" stroke="#EDF1EE" stroke-width="42"></circle>\n              <g fill="none" stroke-width="42">\n                <sc-for list="{{ pie }}" as="p" hint-placeholder-count="10">\n                  <circle data-arc="" cx="120" cy="120" r="100" stroke="{{ p.color }}" stroke-dasharray="{{ p.dash }}" stroke-dashoffset="0" transform="{{ p.rot }}" style="--arc:{{ p.arc }};animation-delay:{{ p.delay }}"></circle>\n                </sc-for>\n              </g>\n              \n            </svg></div>\n            <div style="flex:1;min-width:0">\n              <sc-for list="{{ colleges }}" as="c" hint-placeholder-count="10">\n                <div style="display:grid;grid-template-columns:12px 1fr 40px;gap:9px;align-items:center;padding:3px 0">\n                  <span style="width:11px;height:11px;background:{{ c.color }};border-radius:2px"></span>\n                  <span style="font-size:12.5px;white-space:nowrap;overflow:hidden;text-overflow:ellipsis">{{ c.name }}</span>\n                  <span style="font-size:12.5px;text-align:right;color:#3A4A41;font-variant-numeric:tabular-nums">{{ c.papers }}</span>\n                </div>\n              </sc-for>\n            </div>\n          </div>\n          <div style="margin-top:14px;padding-top:13px;border-top:1px solid #F0F3F1;font-size:12.5px;color:#63736A;line-height:1.45">A paper written across two colleges is credited to both, so the credits add up to more than the paper count.</div>\n        </div>\n\n        <div data-rise style="animation-delay:.125s;display:{{ dashCollabShow }};background:#ffffff;border-radius:8px;padding:20px 22px">\n          <div style="display:flex;align-items:baseline;gap:8px">\n            <div style="font-size:12px;font-weight:700;letter-spacing:.1em;text-transform:uppercase;color:{{ accent }};flex:1">Top collaborators</div>\n            <button type="button" sc-camel-on-click="{{ goNet }}" style="background:none;border:0;padding:0;font-family:Archivo,sans-serif;font-size:12.5px;font-weight:600;color:{{ accent }};cursor:pointer">All of them →</button>\n          </div>\n          <sc-for list="{{ dashCollab }}" as="r" hint-placeholder-count="6">\n            <div title="{{ r.title }}" style="display:grid;grid-template-columns:1fr 190px 34px;gap:10px;align-items:center;padding:6px 0">\n              <div style="font-size:12.5px;color:#3A4A41;overflow:hidden;text-overflow:ellipsis;white-space:nowrap">{{ r.name }}</div>\n              <div style="position:relative;height:14px">\n                <div style="position:absolute;left:0;top:3px;width:{{ r.barW }};height:9px;border-radius:3px;background:#CDE6D8"></div>\n                <div style="position:absolute;left:0;top:3px;width:{{ r.creditW }};height:9px;border-radius:3px;background:{{ accent }}"></div>\n              </div>\n              <div style="font-size:12px;color:#63736A;text-align:right;font-variant-numeric:tabular-nums">{{ r.papers }}</div>\n            </div>\n          </sc-for>\n          <div style="font-size:11.5px;color:#8C9A92;margin-top:8px;line-height:1.45">Pale is joint papers; solid is the same work shared out among every institution on each paper.</div>\n        </div>\n\n        <div data-rise="" style="animation-delay:.15s;background:#ffffff;border-radius:8px;padding:20px 22px">\n          <div style="font-size:12px;font-weight:700;letter-spacing:.1em;text-transform:uppercase;color:{{ accent }};margin-bottom:12px">Since the last run</div>\n          <div style="display:flex;align-items:center;gap:12px;padding:10px 0">\n            <span style="width:9px;height:9px;border-radius:50%;background:#9BB0A4;flex:0 0 auto"></span>\n            <div style="font-size:14.5px;color:#3A4A41;line-height:1.45">{{ deltaLine }}</div>\n          </div>\n          <div style="font-size:12.5px;color:#63736A;line-height:1.5;border-top:1px solid #F0F3F1;padding-top:11px">Run it twice on the same data and this stays empty. If it ever reports something new here, the papers are being matched wrongly.</div>\n        </div>\n      </div>',
     '<sc-if value="{{ progList }}" hint-placeholder-val="{{ true }}">\n      <div data-step="{{ dashNav }}">\n        <div style="display:flex;align-items:flex-end;justify-content:space-between;gap:20px;margin-bottom:20px">\n          <div style="min-width:0">\n            <div style="display:flex;align-items:center;gap:9px">\n              <span style="width:18px;height:2px;border-radius:1px;background:{{ accent }};flex:0 0 auto"></span>\n              <span style="font-size:11px;font-weight:600;letter-spacing:.16em;text-transform:uppercase;color:#63736A">{{ dashEyebrow }}</span>\n            </div>\n            <div style="font-size:22px;font-weight:600;letter-spacing:-.022em;color:#1A1A1A;line-height:1.2;margin-top:9px">Where the papers come from</div>\n            <div style="font-size:13px;color:#63736A;line-height:1.55;max-width:56ch;margin-top:6px">{{ progWindowNote }}</div>\n          </div>\n          <div style="font-size:12px;color:#8C9A92;font-variant-numeric:tabular-nums;white-space:nowrap;flex:0 0 auto;padding-bottom:3px">{{ dashCount }}</div>\n        </div>\n        <div style="display:grid;grid-template-columns:repeat(4,minmax(0,1fr));gap:20px">\n          <sc-for list="{{ dashColleges }}" as="c" hint-placeholder-count="8">\n            <button type="button" sc-camel-on-click="{{ c.open }}" title="{{ c.full }}" data-open-card data-rise-card style="animation-delay:{{ c.delay }};position:relative;overflow:hidden;background:#ffffff;border:1px solid #E4EAE6;border-radius:12px;padding:22px 22px 18px;cursor:pointer;text-align:left;font-family:Archivo,sans-serif;width:100%;display:flex;flex-direction:column">\n              <span data-rail style="position:absolute;top:0;left:0;right:0;height:3px;background:{{ c.color }};transform:scaleX(.3);transform-origin:left center"></span>\n              <div style="display:flex;align-items:flex-start;gap:9px">\n                <span style="font-size:14.5px;font-weight:600;color:#1A1A1A;line-height:1.3;letter-spacing:-.012em;flex:1;min-width:0">{{ c.name }}</span>\n                <span style="font-size:15px;color:#B9C4BD;flex:0 0 auto">›</span>\n              </div>\n              <div style="margin-top:auto;padding-top:16px">\n              <div style="display:flex;align-items:baseline;gap:8px">\n                <span style="font-size:32px;font-weight:600;color:#1A1A1A;letter-spacing:-.03em;line-height:1;font-variant-numeric:tabular-nums">{{ c.papers }}</span>\n                <span style="font-size:12px;color:#63736A">papers</span>\n                <span style="flex:1"></span>\n                <span title="{{ c.perWhy }}" style="font-size:13px;color:#3A4A41;font-variant-numeric:tabular-nums;cursor:help">{{ c.per }}<span style="color:#8C9A92"> / person</span></span>\n              </div>\n              <div style="height:3px;border-radius:2px;background:#EDF1EE;margin-top:16px"><div data-bar-sm style="width:{{ c.barW }};height:3px;border-radius:2px;background:{{ c.color }};animation-delay:{{ c.delay }}"></div></div>\n              <div style="font-size:11.5px;color:#8C9A92;margin-top:11px">{{ c.meta }}</div>\n              </div>\n            </button>\n          </sc-for>\n        </div>\n      </div>\n      </sc-if>\n      <sc-if value="{{ progOfCollege }}" hint-placeholder-val="{{ false }}">\n      <div data-step="{{ dashNav }}">\n        <div style="display:flex;align-items:center;gap:8px;font-size:12.5px;flex-wrap:wrap;margin-bottom:9px">\n          <button type="button" sc-camel-on-click="{{ dashBack }}" style="background:none;border:0;padding:0;font-family:Archivo,sans-serif;font-size:12.5px;font-weight:600;color:{{ accent }};cursor:pointer">All colleges</button>\n          <span style="color:#B9C4BD">›</span>\n          <span style="color:#1A1A1A;font-weight:600">{{ dashColName }}</span>\n        </div>\n        <div style="height:1px;background:#E4EAE6;margin-bottom:18px"><div style="width:44px;height:1px;background:{{ accent }}"></div></div>\n        <div style="display:flex;align-items:center;gap:11px;margin-bottom:18px">\n          <span style="width:10px;height:10px;border-radius:50%;background:{{ dashColColor }};flex:0 0 auto"></span>\n          <div style="min-width:0">\n            <div style="font-size:22px;font-weight:600;letter-spacing:-.022em;color:#1A1A1A;line-height:1.2">{{ dashColName }}</div>\n            <div style="font-size:12.5px;color:#63736A;margin-top:4px;font-variant-numeric:tabular-nums">{{ dashColMeta }}</div>\n          </div>\n        </div>\n        <sc-for list="{{ progGroups }}" as="g" hint-placeholder-count="8">\n          <div style="margin-bottom:22px">\n            <div style="display:{{ g.headShow }};align-items:center;gap:9px;margin-bottom:9px">\n              <span style="width:10px;height:10px;border-radius:50%;background:{{ g.color }};flex:0 0 auto"></span>\n              <span style="font-size:11px;font-weight:600;letter-spacing:.16em;text-transform:uppercase;color:#63736A">{{ g.college }}</span>\n            </div>\n            <div style="display:grid;grid-template-columns:repeat(auto-fill,minmax(262px,1fr));gap:16px">\n              <sc-for list="{{ g.cards }}" as="c" hint-placeholder-count="6">\n                <button type="button" sc-camel-on-click="{{ c.pick }}" title="{{ c.full }}" data-open-card data-rise-card style="animation-delay:{{ c.delay }};background:#ffffff;border:1px solid #E4EAE6;border-radius:12px;padding:16px 17px 14px;cursor:pointer;text-align:left;font-family:Archivo,sans-serif;width:100%;display:flex;flex-direction:column">\n                  <div style="font-size:13.5px;font-weight:600;color:#1A1A1A;line-height:1.35;letter-spacing:-.012em">{{ c.name }}</div>\n                  <div style="display:{{ c.quietShow }};margin-top:8px;font-size:11.5px;color:#8C9A92;line-height:1.45">{{ c.quiet }}</div>\n                  <div title="{{ c.sharedWhy }}" style="display:{{ c.sharedShow }};align-self:flex-start;margin-top:8px;padding:2px 8px;border-radius:4px;background:#F4F6F5;font-size:11px;color:#63736A">{{ c.shared }}</div>\n                  <div style="margin-top:auto;padding-top:14px">\n                    <div style="display:{{ c.statShow }};align-items:baseline;gap:7px">\n                      <span style="font-size:26px;font-weight:600;color:#1A1A1A;letter-spacing:-.03em;font-variant-numeric:tabular-nums;line-height:1">{{ c.papers }}</span>\n                      <span style="font-size:11.5px;color:#63736A">papers</span>\n                      <span style="flex:1"></span>\n                      <span title="{{ c.perWhy }}" style="font-size:12px;color:#3A4A41;font-variant-numeric:tabular-nums;cursor:help">{{ c.per }}<span style="color:#8C9A92"> / person</span></span>\n                    </div>\n                    <div style="height:3px;border-radius:2px;background:#EDF1EE;margin-top:12px"><div data-bar-sm style="width:{{ c.barW }};height:3px;border-radius:2px;background:{{ c.color }};animation-delay:{{ c.delay }}"></div></div>\n                  </div>\n                </button>\n              </sc-for>\n            </div>\n          </div>\n        </sc-for>\n      </div>\n      </sc-if>\n      <sc-if value="{{ progDetail }}" hint-placeholder-val="{{ false }}">\n      <div data-step="{{ dashNav }}">\n        <div style="display:flex;align-items:center;gap:8px;font-size:12.5px;flex-wrap:wrap;margin-bottom:9px">\n          <button type="button" sc-camel-on-click="{{ dashBack }}" style="background:none;border:0;padding:0;font-family:Archivo,sans-serif;font-size:12.5px;font-weight:600;color:{{ accent }};cursor:pointer">All colleges</button>\n          <span style="color:#B9C4BD">›</span>\n          <button type="button" sc-camel-on-click="{{ backToProgs }}" style="background:none;border:0;padding:0;font-family:Archivo,sans-serif;font-size:12.5px;font-weight:600;color:{{ accent }};cursor:pointer">{{ progOne.college }}</button>\n          <span style="color:#B9C4BD">›</span>\n          <span style="color:#1A1A1A;font-weight:600">{{ progOne.name }}</span>\n        </div>\n        <div style="height:1px;background:#E4EAE6;margin-bottom:16px"><div style="width:44px;height:1px;background:{{ accent }}"></div></div>\n        <div style="display:flex;align-items:flex-start;gap:11px;margin-bottom:16px">\n          <span style="width:10px;height:10px;border-radius:50%;background:{{ progOne.color }};flex:0 0 auto;margin-top:7px"></span>\n          <div style="flex:1;min-width:0">\n            <div style="font-size:22px;font-weight:600;letter-spacing:-.022em;color:#1A1A1A;line-height:1.2">{{ progOne.name }}</div>\n            <div style="font-size:12.5px;color:#63736A;margin-top:5px">{{ progOne.staffLine }}</div>\n            <div style="display:{{ progOne.assumedShow }};margin-top:7px;font-size:12px;color:#8A6D1F;background:#FBF6E9;border:1px solid #E0D5B8;border-radius:7px;padding:8px 11px;line-height:1.45">AAU lists this college’s staff but tags nobody to its one programme, so membership here was assigned rather than published.</div>\n          </div>\n        </div>\n        <div style="display:grid;grid-template-columns:repeat(auto-fit,minmax(150px,1fr));gap:12px">\n          <div style="background:#F4F6F5;border-radius:7px;padding:13px 15px"><div style="font-size:25px;font-weight:700;font-variant-numeric:tabular-nums">{{ progOne.papers }}</div><div style="font-size:11.5px;color:#63736A;margin-top:3px">papers in this window</div></div>\n          <div style="background:#F4F6F5;border-radius:7px;padding:13px 15px"><div style="font-size:25px;font-weight:700;font-variant-numeric:tabular-nums">{{ progOne.cites }}</div><div style="font-size:11.5px;color:#63736A;margin-top:3px">citations to those papers</div></div>\n          <div style="background:#F4F6F5;border-radius:7px;padding:13px 15px"><div style="font-size:25px;font-weight:700;font-variant-numeric:tabular-nums">{{ progOne.perStaff }}</div><div style="font-size:11.5px;color:#63736A;margin-top:3px">papers per member of staff</div></div>\n          <div style="background:#F4F6F5;border-radius:7px;padding:13px 15px"><div style="font-size:25px;font-weight:700;font-variant-numeric:tabular-nums">{{ progOne.citesPerStaff }}</div><div style="font-size:11.5px;color:#63736A;margin-top:3px">citations per member of staff</div></div>\n          <div style="background:#F4F6F5;border-radius:7px;padding:13px 15px"><div style="font-size:25px;font-weight:700;font-variant-numeric:tabular-nums">{{ progOne.citesPerPaper }}</div><div style="font-size:11.5px;color:#63736A;margin-top:3px">citations per paper</div></div>\n          <div title="{{ progOne.hNote }}" style="background:#F4F6F5;border-radius:7px;padding:13px 15px"><div style="font-size:25px;font-weight:700;font-variant-numeric:tabular-nums">{{ progOne.avgH }}</div><div style="font-size:11.5px;color:#63736A;margin-top:3px">average h-index · career</div></div>\n        </div>\n        <div style="display:grid;grid-template-columns:1fr 1fr;gap:16px;margin-top:16px">\n          <div style="background:#ffffff;border-radius:8px;padding:18px 20px">\n            <div style="font-size:11.5px;font-weight:700;letter-spacing:.07em;text-transform:uppercase;color:#63736A">Who publishes on it</div>\n            <div style="font-size:12px;color:#63736A;margin:6px 0 12px">Papers in this window.</div>\n            <sc-for list="{{ progPeople }}" as="r" hint-placeholder-count="8">\n              <div title="{{ r.title }}" style="display:grid;grid-template-columns:1fr 110px 34px;gap:10px;align-items:center;padding:4px 0">\n                <div style="font-size:12.5px;color:#3A4A41;overflow:hidden;text-overflow:ellipsis;white-space:nowrap">{{ r.name }}</div>\n                <div style="height:8px;border-radius:3px;background:#EDF1EE"><div style="width:{{ r.barW }};height:8px;border-radius:3px;background:{{ progOne.color }}"></div></div>\n                <div style="font-size:12px;color:#63736A;text-align:right;font-variant-numeric:tabular-nums">{{ r.papers }}</div>\n              </div>\n            </sc-for>\n          </div>\n          <div style="background:#ffffff;border-radius:8px;padding:18px 20px">\n            <div style="font-size:11.5px;font-weight:700;letter-spacing:.07em;text-transform:uppercase;color:#63736A">Against the rest of the college</div>\n            <div style="font-size:12px;color:#63736A;margin:6px 0 12px">{{ progMedNote }}</div>\n            <sc-for list="{{ progSiblings }}" as="r" hint-placeholder-count="6">\n              <div style="display:grid;grid-template-columns:1fr 110px 34px;gap:10px;align-items:center;padding:4px 0">\n                <div style="font-size:12.5px;color:#3A4A41;font-weight:{{ r.weight }};overflow:hidden;text-overflow:ellipsis;white-space:nowrap">{{ r.name }}</div>\n                <div style="position:relative;height:8px;border-radius:3px;background:#EDF1EE"><div style="width:{{ r.barW }};height:8px;border-radius:3px;background:{{ r.bg }}"></div><div style="position:absolute;left:{{ r.medLeft }};top:-2px;width:1px;height:12px;background:#8C9A92"></div></div>\n                <div style="font-size:12px;color:#63736A;text-align:right;font-variant-numeric:tabular-nums">{{ r.v }}</div>\n              </div>\n            </sc-for>\n          </div>\n        </div>\n      </div>\n      </sc-if>'),

    ("dashboard: the other findings open on a click",
     '              <div title="{{ f.why }}" style="font-size:14px;color:#2A3A31;line-height:1.45">{{ f.text }}</div>\n            </div>\n          </sc-for>',
     '              <div title="{{ f.why }}" style="font-size:14px;color:#2A3A31;line-height:1.45">{{ f.text }}</div>\n            </div>\n          </sc-for>\n          <button type="button" sc-camel-on-click="{{ toggleFind }}" style="background:none;border:0;padding:6px 0 0;font-family:Archivo,sans-serif;font-size:12.5px;font-weight:600;color:#0A7A3A;cursor:pointer;text-align:left">{{ findMoreLabel }}<span style="color:#8C9A92;font-weight:500">{{ findMoreCount }}</span></button>'),

    # Deleting the tiles left their padding wrapper behind: an empty
    # 54px band above the run panel. Fold its top padding into the grid
    # so nothing else moves.
    ("dashboard: the screen starts at the run panel, not at empty space",
     '<div style="padding:24px 26px 30px">\n\n    \n    </div>\n\n    <div style="display:grid;grid-template-columns:1fr;gap:16px;margin-top:16px;padding:0 26px 30px">',
     '<div style="display:grid;grid-template-columns:1fr;gap:16px;padding:24px 26px 30px">'),

    # The screen listed five charts and six sheets; the pack now holds eleven
    # and seven, and a list that misdescribes what downloads is worse than no
    # list.
    ("exports: name the charts that actually ship",
     "    const CHART_LIST = [\n"
     "      ['Papers by college', 'bar'],\n"
     "      ['Faculty on the roster, by college', 'bar'],\n"
     "      ['Every author on an AAU paper', 'split bar'],\n"
     "      ['Most published on the roster', 'bar'],\n"
     "      ['Career standing against output', 'scatter'],\n"
     "    ];",
     "    const CHART_LIST = [\n"
     "      ['Papers by college', 'bar'],\n"
     "      ['Faculty on the roster, by college', 'bar'],\n"
     "      ['Every author on an AAU paper', 'split bar'],\n"
     "      ['Most published on the roster', 'bar'],\n"
     "      ['Career standing against output', 'scatter'],\n"
     "      ['Papers per year, by college', 'stacked bar'],\n"
     "      ['Programmes by papers per member of staff', 'bar'],\n"
     "      ['Impact against volume', 'bubble'],\n"
     "      ['Who Al Ain University publishes with', 'paired bar'],\n"
     "      ['Where the partners are', 'bar'],\n"
     "      ['How concentrated the citations are', 'curve'],\n"
     "    ];"),

    # ---- the Roster reads as a directory, not a second scorecard -------
    # It was a four-across grid of bordered cards -- the very shape the
    # Dashboard uses -- so the two screens were indistinguishable at a
    # glance. This is the "compact" card list from dub's dashboard
    # (dubinc/dub, packages/ui/src/card-list): rows joined into one
    # continuous surface, radius on the first and last only. A list of
    # places to go, which is what a roster is, against a board of
    # figures, which is what the Dashboard is.
    # The row needs its college colour; rosterCols never carried one
    # because the old card used the accent for every college.
    ("roster: each row carries its own college colour",
     "      name: c.name, n: c.people, papers: c.papers.toLocaleString(),",
     "      name: c.name, n: c.people, papers: c.papers.toLocaleString(),\n"
     "      color: c.color || accent,"),

    ("roster: the college grid becomes a single column",
     '<div style="display:grid;grid-template-columns:repeat(4,minmax(0,1fr));gap:14px">\n'
     '      <sc-for list="{{ rosterCols }}"',
     '<div style="display:flex;flex-direction:column">\n'
     '      <sc-for list="{{ rosterCols }}"'),

    ("roster: the college list is a joined list, not a card grid",
     '<sc-for list="{{ rosterCols }}" as="c" hint-placeholder-count="8">\n        <button type="button" sc-camel-on-click="{{ c.open }}" style="text-align:left;background:#ffffff;border:1px solid #E4EAE6;border-top:4px solid {{ accent }};border-radius:8px;padding:18px 20px;font-family:Archivo,sans-serif;cursor:pointer;display:flex;flex-direction:column;gap:12px" style-hover="border-color:#0A7A3A;box-shadow:0 6px 18px -8px rgba(10,60,35,.28)">\n          <div style="font-size:16.5px;font-weight:700;line-height:1.25;color:#1A1A1A;min-height:42px">{{ c.name }}</div>\n          <div style="display:flex;align-items:baseline;gap:8px">\n            <span style="font-size:34px;font-weight:800;letter-spacing:-.025em;line-height:1;color:#1A1A1A">{{ c.n }}</span>\n            <span style="font-size:13px;color:#63736A">people</span>\n          </div>\n          <div style="height:6px;background:#EDF1EE;border-radius:3px">\n            <div data-bar="" style="height:6px;width:{{ c.pct }}%;background:{{ accent }};border-radius:3px;animation-delay:{{ c.delay }}"></div>\n          </div>\n          <div style="display:flex;align-items:center;gap:10px;font-size:12.5px;color:#63736A">\n            <span>{{ c.papers }} papers</span>\n            <sc-if value="{{ c.review }}" hint-placeholder-val="{{ false }}">\n              <span style="color:#E0303F;font-weight:600">{{ c.review }} to decide</span>\n            </sc-if>\n            <span style="flex:1"></span>\n            <span style="color:{{ accent }};font-weight:700">Open ›</span>\n          </div>\n        </button>',
     '<sc-for list="{{ rosterCols }}" as="c" hint-placeholder-count="8">\n        <button type="button" sc-camel-on-click="{{ c.open }}" data-roster-row style="text-align:left;background:#ffffff;border:1px solid #E4EAE6;border-bottom:0;padding:14px 20px;font-family:Archivo,sans-serif;cursor:pointer;display:grid;grid-template-columns:3px 1fr 116px 108px 20px;gap:16px;align-items:center;width:100%">\n          <span data-rail-v style="width:3px;border-radius:2px;background:{{ c.color }};align-self:stretch;transform:scaleY(.5);transform-origin:center"></span>\n          <div style="min-width:0">\n            <div style="font-size:15px;font-weight:600;color:#1A1A1A;line-height:1.3;letter-spacing:-.012em;overflow:hidden;text-overflow:ellipsis;white-space:nowrap">{{ c.name }}</div>\n            <div style="height:4px;background:#EDF1EE;border-radius:2px;margin-top:7px"><div data-bar="" style="height:4px;width:{{ c.pct }}%;background:{{ c.color }};border-radius:2px;animation-delay:{{ c.delay }}"></div></div>\n          </div>\n          <div style="font-size:12.5px;color:#63736A;font-variant-numeric:tabular-nums"><span style="font-size:19px;font-weight:600;color:#1A1A1A;letter-spacing:-.02em">{{ c.n }}</span> people</div>\n          <div><sc-if value="{{ c.review }}" hint-placeholder-val="{{ false }}"><span style="display:inline-block;background:#FCE9EB;color:#E0303F;font-size:11.5px;font-weight:600;padding:3px 9px;border-radius:4px;white-space:nowrap">{{ c.review }} to decide</span></sc-if></div>\n          <span style="font-size:15px;color:#B9C4BD;text-align:right">›</span>\n        </button>'),

    ("roster: the college subtitle names the programme when one is chosen",
     '<div style="font-size:13.5px;color:#63736A;margin-top:3px">{{ colMeta }}'
     '</div>',
     '<div style="font-size:13.5px;color:#63736A;margin-top:3px">{{ colMeta }}'
     '</div>\n        <sc-if value="{{ progNote }}" '
     'hint-placeholder-val="{{ false }}">\n'
     '        <div style="font-size:12.5px;color:#63736A;margin-top:4px">'
     '{{ progNote }}</div>\n        </sc-if>'),
    ("programmes: a constant the bridge can fill, beside the others",
     "const PAPERS = {",
     "// Filled from data/programs.json by __aauApply, the same way the three\n"
     "// constants above are. Empty until then, and the programme row hides.\n"
     "const PROGRAMS = [];\n\n"
     "// The people whose Scopus match is genuinely ambiguous. Until this\n"
     "// arrived the review screen showed the designer's placeholder people --\n"
     "// an invented Muhammad Ilyas and seven names that do not exist -- and\n"
     "// the buttons acted on them.\n"
     "const REVIEW = [];\n\nconst PAPERS = {"),

    ("papers and network: constants the bridge fills",
     "const REVIEW = [];\n\nconst PAPERS = {",
     "const REVIEW = [];\n\n"
     "// Fetched only when their screen is first opened: the corpus is ~950KB\n"
     "// and the collaboration file 21KB, and neither belongs in the payload\n"
     "// every visitor pays for.\n"
     "const CORPUS = [];\nconst NETWORK = {};\n\nconst PAPERS = {"),

    # ---- the review screen shows real people ------------------------------
    ("review: the candidate card is the real ambiguous person",
     "    const candidates = [",
     "    const _rv = REVIEW.length\n"
     "      ? (REVIEW.find(x => x.name === this.state.reviewWho) || REVIEW[0])\n"
     "      : null;\n"
     "    const candidates = _rv ? _rv.candidates.map((c, i) => ({\n"
     "      name: _rv.name,\n"
     "      affil: c.papers + (c.papers === 1 ? ' AAU paper' : ' AAU papers')\n"
     "        + ' on Scopus author ' + c.auid,\n"
     "      auid: c.auid,\n"
     "      papers: c.papers ? c.papers + ' in window' : 'none',\n"
     "      rosterName: _rv.name,\n"
     "      btnLabel: 'This one',\n"
     "      btnBg: i === 0 ? accent : '#ffffff',\n"
     "      btnFg: i === 0 ? '#ffffff' : accent,\n"
     "      btnBorder: i === 0 ? accent : '#C3D6CA',\n"
     "    })).concat([{\n"
     "      name: 'None of these', affil: 'none of the records above is '\n"
     "        + _rv.name, auid: '', papers: '', rosterName: _rv.name,\n"
     "      btnLabel: 'Not them', btnBg: '#ffffff', btnFg: '#63736A',\n"
     "      btnBorder: '#D5DED8',\n"
     "    }]) : ["),

    ("review: the queue is the real queue",
     "    const queue = [",
     "    const queue = REVIEW.length ? REVIEW.slice(1).map(r => ({\n"
     "      name: r.name, college: r.college,\n"
     "      cands: r.candidates.length + (r.candidates.length === 1\n"
     "        ? ' candidate' : ' candidates'),\n"
     "      pick: () => this.setState({ reviewWho: r.name }),\n"
     "    })) : ["),

    # ---- say what the rule actually is ------------------------------------
    # "Nothing is counted unless the paper itself prints an AAU address" is
    # what the app aspires to, but it describes 592 of 4,245 papers. Route A
    # takes Scopus's own AF-ID(60105817) assignment on trust -- which is
    # reasonable, and is 99.8% of the corpus -- while the printed-address test
    # is what gates the per-author sweep, where it threw out 584 of 592. The
    # claim as written invited exactly the distrust it was meant to answer.
    ("welcome: describe the rule that is actually applied",
     "Nothing is counted unless the paper itself prints an AAU address.",
     "A paper counts when Scopus files it under Al Ain University; anything "
     "found through an author on top of that has to print an AAU address "
     "itself."),

    # ---- make it survive a phone ------------------------------------------
    # The layout has a hard 1180px floor and no media query, while the page
    # declared width=device-width -- so a phone laid out 390px of a 1180px
    # design and showed the left third of it. On the welcome screen that put
    # "Press here to begin" off-screen entirely, with no way to reach it.
    #
    # Declaring the real layout width instead lets the browser fit the whole
    # page and scale it, the way it treats any desktop site: small, but
    # complete, pannable and pinch-zoomable, and every control reachable. That
    # is the honest fix for a fixed-width design -- a true mobile layout would
    # mean re-drawing seven screens, which is a different job.
    ("head: the viewport is the device, and the layout reflows to it",
     '<meta name="viewport" content="width=device-width, initial-scale=1">',
     '<meta name="viewport" content="width=device-width, initial-scale=1, '
     'viewport-fit=cover">'),

    # Tablets get real breathing room: the two-column screens stack rather
    # than crushing a 330px sidebar against a 1fr pane that has nothing left.
    ("head: the page reflows to the device",
     "</helmet>",
     "<style>" + MOBILE_CSS + "</style>\n</helmet>"),

    # ---- the author panel must not invent a selection ---------------------
    # With nobody picked -- the state on arrival, and again after a run drops
    # the selected person from the list -- the panel fell back to AUTHORS[0]
    # and drew a full dossier for whoever happens to publish most, while the
    # list showed no row highlighted. A reader has no way to tell that from
    # having selected them.
    ("authors: nothing selected shows nothing, not the top author",
     "const p = AUTHORS.find(a => a.key === this.state.author) || AUTHORS[0];",
     "const p = AUTHORS.find(a => a.key === this.state.author)\n"
     "      || (this.state.author ? null : AUTHORS[0]) || AUTHORS[0];\n"
     "    const lostPick = !!(this.state.author\n"
     "      && !AUTHORS.some(a => a.key === this.state.author));"),

    # The caption under the paper table read {{ pick.moreLabel }} while
    # moreLabel was a sibling of `pick`, never a property of it -- so it has
    # rendered empty since the first build, including its own "No papers in
    # this window." case.
    ("authors: the caption under the papers is bound to something real",
     "{{ pick.moreLabel }}", "{{ moreLabel }}"),

    # ---- two buttons that were drawn but never wired ----------------------
    ("authors: Show all opens the full paper list",
     '<button type="button" style="background:#ffffff;color:{{ accent }};'
     'border:1px solid #C3D6CA;border-radius:5px;padding:8px 15px;'
     'font-family:Archivo,sans-serif;font-size:13px;font-weight:600;'
     'cursor:pointer">Show all</button>',
     '<button type="button" sc-camel-on-click="{{ showPapers }}" '
     'style="background:#ffffff;color:{{ accent }};'
     'border:1px solid #C3D6CA;border-radius:5px;padding:8px 15px;'
     'font-family:Archivo,sans-serif;font-size:13px;font-weight:600;'
     'cursor:pointer">Show all</button>'),

    # ---- one researcher's co-authors, drawn ------------------------------
    ("authors: a co-author wheel under the paper list",
     '<button type="button" sc-camel-on-click="{{ showPapers }}" '
     'style="background:#ffffff;color:{{ accent }};border:1px solid #C3D6CA;'
     'border-radius:5px;padding:8px 15px;font-family:Archivo,sans-serif;'
     'font-size:13px;font-weight:600;cursor:pointer">Show all</button>',
     '<button type="button" sc-camel-on-click="{{ showPapers }}" '
     'style="background:#ffffff;color:{{ accent }};border:1px solid #C3D6CA;'
     'border-radius:5px;padding:8px 15px;font-family:Archivo,sans-serif;'
     'font-size:13px;font-weight:600;cursor:pointer">Show all</button>\n'
     '        </div>\n'
     '        <sc-if value="{{ coHas }}" hint-placeholder-val="{{ true }}">\n'
     '        <div data-rise style="animation-delay:.12s;margin-top:18px;'
     'border-top:1px solid #F0F3F1;padding-top:18px">\n'
     '          <div style="font-size:11.5px;font-weight:700;'
     'letter-spacing:.07em;text-transform:uppercase;color:#63736A">'
     'Who they write with</div>\n'
     '          <div style="font-size:12.5px;color:#63736A;margin:6px 0 4px;'
     'line-height:1.5;max-width:640px">{{ coNote }}</div>\n'
     '          <div style="position:relative;width:640px;height:420px;'
     'margin:0 auto">\n'
     '            <svg width="640" height="420" style="position:absolute;'
     'left:0;top:0">\n'
     '              <sc-for list="{{ coNodes }}" as="c" '
     'hint-placeholder-count="8">\n'
     '                <line x1="320" y1="210" sc-camel-x2="{{ c.x2 }}" '
     'sc-camel-y2="{{ c.y2 }}" stroke="#9DC3AC" '
     'sc-camel-stroke-width="{{ c.w }}" stroke-linecap="round"></line>\n'
     '              </sc-for>\n'
     '              <sc-for list="{{ coNodes }}" as="c" '
     'hint-placeholder-count="8">\n'
     '                <circle sc-camel-cx="{{ c.cx }}" sc-camel-cy="{{ c.cy }}" '
     'sc-camel-r="{{ c.r }}" fill="#ffffff" stroke="#7FB394" '
     'stroke-width="1.5"></circle>\n'
     '              </sc-for>\n'
     '              <circle cx="320" cy="210" r="34" fill="{{ accent }}">'
     '</circle>\n'
     '            </svg>\n'
     '            <div style="position:absolute;left:286px;top:194px;'
     'width:68px;text-align:center;font-size:19px;font-weight:700;'
     'color:#ffffff;pointer-events:none">{{ coCentre }}</div>\n'
     '            <sc-for list="{{ coNodes }}" as="c" '
     'hint-placeholder-count="8">\n'
     '              <div title="{{ c.title }}" style="position:absolute;'
     'left:{{ c.lleft }};top:{{ c.ltop }};width:{{ c.lwidth }};'
     'text-align:{{ c.lalign }};font-size:11.5px;line-height:1.3;'
     'color:#3A4A41">{{ c.name }} <span style="color:#8C9A92">{{ c.n }}</span>'
     '</div>\n'
     '            </sc-for>\n'
     '          </div>\n'
     '        </div>\n'
     '        </sc-if>\n'
     '        <div style="display:none">'),

    ("roster: Export this college writes a CSV",
     '<button type="button" style="background:#ffffff;color:{{ accent }};'
     'border:1px solid #C3D6CA;border-radius:6px;padding:9px 15px;'
     'font-family:Archivo,sans-serif;font-size:13.5px;font-weight:600;'
     'cursor:pointer">Export this college</button>',
     '<button type="button" sc-camel-on-click="{{ exportCollege }}" '
     'style="background:#ffffff;color:{{ accent }};'
     'border:1px solid #C3D6CA;border-radius:6px;padding:9px 15px;'
     'font-family:Archivo,sans-serif;font-size:13.5px;font-weight:600;'
     'cursor:pointer">Export this college</button>'),

    # ---- the schedule screen must describe the real schedule --------------
    # It said "Tuesday ... 06:00" and listed four typed dates. The workflow
    # runs `0 3 * * 1` -- Monday 03:00 UTC, 07:00 in Al Ain. Four literals
    # that drift out of date the moment September passes are worse than no
    # list, so they are computed from the cron the repository actually has.
    ("schedule: the next runs are computed from the real cron",
     "    const nextRuns = sched ? [\n"
     "      { when: 'Tuesday 1 September, 06:00', note: 'scheduled', dot: accent },\n"
     "      { when: 'Tuesday 8 September, 06:00', note: 'scheduled', dot: accent },\n"
     "      { when: 'Tuesday 15 September, 06:00', note: 'scheduled', dot: '#C3CCC6' },\n"
     "      { when: 'Tuesday 22 September, 06:00', note: 'scheduled', dot: '#C3CCC6' },\n"
     "    ] : [",
     "    const nextRuns = sched ? (() => {\n"
     "      // 0 3 * * 1 -- Monday 03:00 UTC, which is 07:00 in Al Ain. Four\n"
     "      // typed dates went stale the moment September passed, and said\n"
     "      // Tuesday for a job that runs on Monday.\n"
     "      const out = [];\n"
     "      const d = new Date();\n"
     "      d.setUTCHours(3, 0, 0, 0);\n"
     "      while (d.getUTCDay() !== 1 || d.getTime() <= Date.now()) {\n"
     "        d.setUTCDate(d.getUTCDate() + 1);\n"
     "        d.setUTCHours(3, 0, 0, 0);\n"
     "      }\n"
     "      for (let i = 0; i < 4; i++) {\n"
     "        const gulf = new Date(d.getTime() + 4 * 3600 * 1000);\n"
     "        out.push({\n"
     "          when: gulf.toLocaleDateString('en-GB', { weekday: 'long',\n"
     "            day: 'numeric', month: 'long', timeZone: 'UTC' }) + ', 07:00',\n"
     "          note: 'scheduled',\n"
     "          dot: i < 2 ? accent : '#C3CCC6',\n"
     "        });\n"
     "        d.setUTCDate(d.getUTCDate() + 7);\n"
     "      }\n"
     "      return out;\n"
     "    })() : ["),

    ("schedule: the time shown is the time it runs",
     '<span style="font-size:15px;font-weight:600;font-variant-numeric:'
     'tabular-nums">06:00</span>\n              <span style="font-size:12.5px;'
     'color:#63736A">after the Scopus nightly update</span>',
     '<span style="font-size:15px;font-weight:600;font-variant-numeric:'
     'tabular-nums">07:00</span>\n              <span style="font-size:12.5px;'
     'color:#63736A">Gulf time, Mondays \u00b7 03:00 UTC</span>'),

    ("roster: the college list narrows to the chosen programme",
     "    const colAuthors = (sel ? AUTHORS.filter(a => a.college === sel) : []);",
     "    const chosenProg = this.state.program || '';\n"
     "    const colAuthors = (sel ? AUTHORS.filter(a =>\n"
     "      a.college === sel && (!chosenProg\n"
     "        || (a.programs || []).indexOf(chosenProg) >= 0)) : []);"),

    ("roster: leaving a college forgets its programme",
     "backToColleges: () => this.setState({ college: null, review: false }),",
     "backToColleges: () => this.setState({ college: null, review: false,\n"
     "        program: null }),"),

    ("roster: opening a college starts on Everyone",
     "      open: () => this.setState({ college: c.name, review: false }),",
     "      open: () => this.setState({ college: c.name, review: false,\n"
     "        program: null }),"),

    # ---- the Roster stops imitating the Dashboard -----------------------
    # Two screens of white cards carrying an 800-weight figure over a bar
    # read as the same object. Everything below is chosen so they differ on
    # an axis the eye resolves before it reads a word: the Dashboard's rail
    # runs along the top and grows sideways, the Roster's runs down the left
    # and grows downward; the Dashboard's hero number is papers, the
    # Roster's is people; the Dashboard's cards cascade in 30ms apart, the
    # Roster's eight bars grow in unison.
    ("roster: the eight bars grow as a chord, not an arpeggio",
     "      delay: (0.04 * i).toFixed(2) + 's',",
     "      delay: '0s',"),

    # The Roster's own title, onto the same ramp as everywhere else. 25px at
    # 700 is the heaviest thing on either screen and it is a caption.
    ("roster: heading onto the type ramp",
     '<div style="font-size:25px;font-weight:700;letter-spacing:-.02em;'
     'margin-top:6px">{{ rosterHead }}</div>',
     '<div style="font-size:22px;font-weight:600;letter-spacing:-.022em;'
     'margin-top:8px">{{ rosterHead }}</div>'),
]
