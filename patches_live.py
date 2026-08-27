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
     "        window.__AAU && window.__AAU.demoNote "
     "&& window.__AAU.demoNote();\n"
     "      },"),

    # ---- searchable + filterable author list -------------------------------
    ("authors: the search box actually searches",
     '<input type="text" placeholder="Search 511 people…" style="border:0;',
     '<input type="text" placeholder="{{ searchHint }}" '
     'value="{{ q }}" onInput="{{ onSearch }}" style="border:0;'),

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
     '<button type="button" onClick="{{ f.pick }}" '
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
     '<button type="button" onClick="{{ e.go }}" '
     'style="margin-top:16px;background:{{ e.btnBg }};'),

    ("exports: 'Export all three' does all three",
     '<button type="button" style="background:{{ accent }};color:#ffffff;'
     'border:0;border-radius:6px;padding:12px 24px;font-family:Archivo,'
     'sans-serif;font-size:14px;font-weight:700;cursor:pointer;'
     'white-space:nowrap">Export all three',
     '<button type="button" onClick="{{ exportAll }}" '
     'style="background:{{ accent }};color:#ffffff;'
     'border:0;border-radius:6px;padding:12px 24px;font-family:Archivo,'
     'sans-serif;font-size:14px;font-weight:700;cursor:pointer;'
     'white-space:nowrap">Export all three'),

    # ---- the review queue can actually clear a name -----------------------
    ("review: the decision buttons decide",
     '<button type="button" style="background:{{ c.btnBg }};color:{{ c.btnFg }};'
     'border:1px solid {{ c.btnBorder }};border-radius:5px;',
     '<button type="button" onClick="{{ c.go }}" '
     'style="background:{{ c.btnBg }};color:{{ c.btnFg }};'
     'border:1px solid {{ c.btnBorder }};border-radius:5px;'),

    # ---- import roster CSV -------------------------------------------------
    ("roster: 'Import roster CSV' opens a file picker",
     '<button type="button" style="background:#ffffff;color:{{ accent }};'
     'border:1px solid #C3D6CA;border-radius:6px;padding:10px 17px;',
     '<button type="button" onClick="{{ importCsv }}" '
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
    '    <button type="button" onClick="{{ openSuggestions }}" data-rise '
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
"""
