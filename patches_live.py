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
    window.__AAU.refresh(self).catch(function () {
      window.__AAU.badge('sample data · engine not running', '#63736A');
      self.setState({ demo: true });
    });
  }
"""

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
     "      color: f.kind === 'bad' ? '#E0303F'\n"
     "        : (f.kind === 'warn' ? '#E8A33D' : accent),\n"
     "    })) : running ? ["),

    ("dashboard: the run caption reflects the real run",
     "      runTitle: running ? 'Run in progress' : 'Last run finished',",
     "      runTitle: running ? 'Run in progress'\n"
     "        : ((window.__AAU && (window.__AAU.status\n"
     "            || (window.__AAU.state && window.__AAU.state.generated)))\n"
     "           ? 'Last run finished'\n"
     "           : (window.__AAU && window.__AAU.live ? 'No run yet'\n"
     "              : 'Last run finished')),"),

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

BANNER_PATCH = (
    "roster: banner offering the people a run found who are not on the roster",
    '\n    <div style="display:grid;grid-template-columns:repeat(4,'
    'minmax(0,1fr));gap:14px">\n'
    '      <sc-for list="{{ rosterCols }}" as="c" hint-placeholder-count="8">',
    SUGGEST_BANNER +
    '    <div style="display:grid;grid-template-columns:repeat(4,'
    'minmax(0,1fr));gap:14px">\n'
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
     "        : (running && d[2] > 0 && d[2] < 100);"),

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
]
