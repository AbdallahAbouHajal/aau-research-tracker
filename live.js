<script>
/* AAU Research Tracker -- live bridge.
 *
 * The interface was designed against fixed constants. This makes those
 * constants come from the local engine without touching a single style: the
 * arrays are mutated IN PLACE (the binding is const, the contents are not),
 * then the component is told to re-render. If no engine answers, the baked-in
 * figures stay and a badge says so, because a page that silently shows stale
 * numbers for named colleagues is worse than one that admits it is a sample.
 */
(function () {
  'use strict';

  var G = '#0A7A3A', RED = '#E0303F', INK = '#1A1A1A', META = '#63736A';
  var FONT = 'Archivo,sans-serif';
  window.__AAU = { live: false, state: null, run: null };

  /* ------------------------------------------------------------- transport */
  function api(path, body) {
    var opt = { headers: { 'Content-Type': 'application/json' } };
    if (body !== undefined) { opt.method = 'POST'; opt.body = JSON.stringify(body); }
    return fetch(path, opt).then(function (r) {
      if (!r.ok) throw new Error(path + ' -> HTTP ' + r.status);
      return r.json();
    });
  }
  window.__AAU.api = api;

  /* ------------------------------------------------------------ the badge  */
  function badge(text, color) {
    var b = document.getElementById('__aau_badge');
    if (!b) {
      b = document.createElement('div');
      b.id = '__aau_badge';
      b.style.cssText = 'position:fixed;right:14px;bottom:14px;z-index:9000;' +
        'font:600 11.5px/1 ' + FONT + ';letter-spacing:.06em;text-transform:uppercase;' +
        'padding:8px 13px;border-radius:6px;color:#fff;box-shadow:0 4px 14px -6px rgba(0,0,0,.4)';
      document.body.appendChild(b);
    }
    b.textContent = text;
    b.style.background = color;
  }
  window.__AAU.badge = badge;

  /* ------------------------------------------------------------- the modal */
  /* Built as plain DOM rather than added to the template, so the approved
   * markup stays exactly as it was authored. Styles mirror the design tokens. */
  function modal(spec) {
    var old = document.getElementById('__aau_modal');
    if (old) old.remove();

    var wrap = document.createElement('div');
    wrap.id = '__aau_modal';
    wrap.style.cssText = 'position:fixed;inset:0;z-index:9500;background:rgba(12,30,20,.55);' +
      'display:flex;align-items:center;justify-content:center;padding:24px;' +
      'font-family:' + FONT + ';animation:uiFade .18s both';

    var card = document.createElement('div');
    card.style.cssText = 'background:#fff;border-radius:8px;width:' + (spec.width || 560) + 'px;' +
      'max-width:100%;max-height:88vh;overflow:auto;box-shadow:0 30px 80px -30px rgba(0,0,0,.5);' +
      'animation:uiRise .28s cubic-bezier(.22,.7,.2,1) both';

    var head = document.createElement('div');
    head.style.cssText = 'background:' + G + ';color:#fff;padding:22px 26px 20px';
    head.innerHTML =
      '<div style="font-size:11.5px;font-weight:700;letter-spacing:.09em;' +
      'text-transform:uppercase;opacity:.75">' + esc(spec.eyebrow || 'Run') + '</div>' +
      '<div style="font-size:21px;font-weight:700;letter-spacing:-.01em;margin-top:7px">' +
      esc(spec.title) + '</div>' +
      (spec.sub ? '<div style="font-size:14px;line-height:1.5;margin-top:8px;color:#D5E8DC">' +
        esc(spec.sub) + '</div>' : '');
    card.appendChild(head);

    var body = document.createElement('div');
    body.style.cssText = 'padding:20px 26px 24px';
    card.appendChild(body);

    (spec.choices || []).forEach(function (c, i) {
      var b = document.createElement('button');
      b.type = 'button';
      b.style.cssText = 'display:block;width:100%;text-align:left;background:#fff;' +
        'border:1px solid #E4EAE6;border-radius:8px;padding:15px 17px;margin-bottom:10px;' +
        'cursor:pointer;font-family:' + FONT + ';transition:border-color .14s,background .14s;' +
        'animation:uiRise .3s both;animation-delay:' + (0.04 * i).toFixed(2) + 's';
      b.innerHTML =
        '<div style="font-size:15px;font-weight:700;color:' + INK + '">' + esc(c.label) + '</div>' +
        (c.hint ? '<div style="font-size:13px;color:' + META + ';margin-top:4px;line-height:1.45">' +
          esc(c.hint) + '</div>' : '');
      b.onmouseenter = function () { b.style.borderColor = G; b.style.background = '#F4F9F6'; };
      b.onmouseleave = function () { b.style.borderColor = '#E4EAE6'; b.style.background = '#fff'; };
      b.onclick = function () { close(); c.go && c.go(); };
      body.appendChild(b);
    });

    if (spec.input) {
      var inp = document.createElement('input');
      inp.type = 'text';
      inp.placeholder = spec.input.placeholder || '';
      inp.value = spec.input.value || '';
      inp.style.cssText = 'width:100%;box-sizing:border-box;border:1px solid #D5DED8;' +
        'border-radius:6px;padding:13px 14px;font-family:' + FONT + ';font-size:14.5px;' +
        'color:' + INK + ';outline:none';
      inp.onfocus = function () { inp.style.borderColor = G; };
      inp.onblur = function () { inp.style.borderColor = '#D5DED8'; };
      body.appendChild(inp);
      var note = document.createElement('div');
      note.style.cssText = 'font-size:12.5px;color:' + META + ';margin-top:9px;line-height:1.5;min-height:18px';
      note.textContent = spec.input.note || '';
      body.appendChild(note);
      spec.__input = inp; spec.__note = note;
      setTimeout(function () { inp.focus(); }, 60);
      inp.onkeydown = function (e) { if (e.key === 'Enter' && spec.submit) spec.submit.go(); };
    }

    if (spec.html) {
      var d = document.createElement('div');
      d.innerHTML = spec.html;
      body.appendChild(d);
    }

    var row = document.createElement('div');
    row.style.cssText = 'display:flex;gap:10px;justify-content:flex-end;margin-top:18px';
    var cancel = document.createElement('button');
    cancel.type = 'button';
    cancel.textContent = spec.cancelLabel || 'Cancel';
    cancel.style.cssText = 'background:#fff;border:1px solid #D5DED8;border-radius:6px;' +
      'padding:11px 18px;font-family:' + FONT + ';font-size:14px;font-weight:600;' +
      'color:' + INK + ';cursor:pointer';
    cancel.onclick = close;
    row.appendChild(cancel);
    if (spec.submit) {
      var ok = document.createElement('button');
      ok.type = 'button';
      ok.textContent = spec.submit.label;
      ok.style.cssText = 'background:' + G + ';border:0;border-radius:6px;padding:11px 20px;' +
        'font-family:' + FONT + ';font-size:14px;font-weight:700;color:#fff;cursor:pointer';
      ok.onclick = function () { spec.submit.go(); };
      row.appendChild(ok);
      spec.__ok = ok;
    }
    body.appendChild(row);

    wrap.appendChild(card);
    wrap.onclick = function (e) { if (e.target === wrap) close(); };
    document.body.appendChild(wrap);
    document.addEventListener('keydown', onEsc);
    function onEsc(e) { if (e.key === 'Escape') close(); }
    function close() {
      document.removeEventListener('keydown', onEsc);
      var m = document.getElementById('__aau_modal');
      if (m) m.remove();
    }
    spec.close = close;
    return spec;
  }
  window.__AAU.modal = modal;

  function esc(s) {
    return String(s == null ? '' : s).replace(/[&<>"]/g, function (c) {
      return { '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;' }[c];
    });
  }
  window.__AAU.esc = esc;

  /* --------------------------------------------------------- the run flow  */
  /* Press "Run now" and the app asks what kind of run this is, the way a
   * person would: are we adding somebody, or refreshing the people we have --
   * and if refreshing, do you want the whole picture or only what moved. */
  function askRun(component) {
    modal({
      eyebrow: 'New run',
      title: 'What would you like to do?',
      sub: 'Two kinds of update. Pick the one you need and the run is set up for it.',
      choices: [
        {
          label: 'Fetch new work for the people we already have',
          hint: 'Goes to Scopus for every resolved author and brings back what is new.',
          go: function () { askScope(component); },
        },
        {
          label: 'Add a new researcher',
          hint: 'Paste their page on aau.ac.ae and their Scopus record is found for you.',
          go: function () { askProfile(component); },
        },
      ],
    });
  }

  function askScope(component) {
    modal({
      eyebrow: 'New run',
      title: 'How should this run report?',
      sub: 'The work is the same either way. This only changes what you are shown at the end.',
      choices: [
        {
          label: 'Everything, as it stands today',
          hint: 'The full census: papers, authors, colleges, h-index and citations.',
          go: function () { askWindow(component, 'current'); },
        },
        {
          label: 'Only what changed since the last run',
          hint: 'New papers, authors never seen before, and anyone who started publishing again.',
          go: function () { askWindow(component, 'compare'); },
        },
      ],
    });
  }

  function askWindow(component, scope) {
    var y = new Date().getFullYear();
    modal({
      eyebrow: 'New run',
      title: 'Which years should it cover?',
      sub: 'A paper counts only if the paper itself prints an Al Ain University address.',
      choices: [
        {
          label: (y - 1) + ' and ' + y,
          hint: 'The rolling window. This is what the census uses.',
          go: function () { startRun(component, { mode: 'refresh', scope: scope, years: [y - 1, y] }); },
        },
        {
          label: 'This year only (' + y + ')',
          hint: 'Faster, and enough when you just want what is new.',
          go: function () { startRun(component, { mode: 'refresh', scope: scope, years: [y] }); },
        },
        {
          label: 'The last three years',
          hint: 'A wider look. Takes noticeably longer.',
          go: function () { startRun(component, { mode: 'refresh', scope: scope, years: [y - 2, y - 1, y] }); },
        },
      ],
    });
  }

  function askProfile(component) {
    var m = modal({
      eyebrow: 'Add a researcher',
      title: 'Paste their page on aau.ac.ae',
      sub: 'Their own profile page is the most reliable route: it usually links their Scopus record, and lists their publications when it does not.',
      input: {
        placeholder: 'https://aau.ac.ae/en/staff/…',
        note: 'The link from the staff directory.',
      },
      submit: {
        label: 'Find them',
        go: function () {
          var url = (m.__input.value || '').trim();
          if (!/aau\.ac\.ae\/.*\/staff\//.test(url)) {
            m.__note.textContent = 'That does not look like an aau.ac.ae staff page.';
            m.__note.style.color = RED;
            return;
          }
          m.__ok.disabled = true;
          m.__ok.textContent = 'Looking…';
          m.__note.style.color = META;
          m.__note.textContent = 'Reading the page, then checking Scopus. This takes a few seconds.';
          api('/api/faculty/add', { url: url })
            .then(function (r) { m.close(); showFound(component, r); })
            .catch(function (e) {
              m.__ok.disabled = false;
              m.__ok.textContent = 'Find them';
              m.__note.style.color = RED;
              m.__note.textContent = String(e.message || e);
            });
        },
      },
    });
  }

  function showFound(component, r) {
    if (!r.found) {
      modal({
        eyebrow: 'Add a researcher',
        title: 'No Scopus record for that page',
        sub: r.name ? (r.name + ' was read from the page, but nothing on it points to a Scopus author, and no paper in the window carries their name.') : 'That page could not be read.',
        choices: [{
          label: 'Add them anyway, with no Scopus id',
          hint: 'They join the roster and count as faculty. Their papers appear once an id is known.',
          go: function () {
            api('/api/faculty/add', { url: r.url, force: true })
              .then(function () { refresh(component); });
          },
        }],
      });
      return;
    }
    var v = r.verify || {};
    modal({
      eyebrow: 'Add a researcher',
      title: r.name,
      sub: 'Found on Scopus. Check this is the right person before adding them.',
      html:
        '<div style="border:1px solid #E4EAE6;border-radius:8px;padding:16px 18px;font-family:' + FONT + '">' +
        row2('Scopus author id', r.auid) +
        row2('Papers on Scopus', v.total) +
        row2('Of those, printing an AAU address', v.aau) +
        row2('In the current window', v.recent) +
        row2('How it was found', (r.tier || '').split(':').pop().replace(/-/g, ' ')) +
        '</div>',
      cancelLabel: 'Not them',
      submit: {
        label: 'Add to the roster',
        go: function () {
          api('/api/faculty/add', { url: r.url, auid: r.auid, confirm: true })
            .then(function () {
              document.getElementById('__aau_modal') && document.getElementById('__aau_modal').remove();
              refresh(component);
            });
        },
      },
    });
  }

  function row2(k, v) {
    return '<div style="display:flex;justify-content:space-between;gap:16px;padding:7px 0;' +
      'border-bottom:1px solid #F0F3F1;font-size:14px">' +
      '<span style="color:' + META + '">' + esc(k) + '</span>' +
      '<span style="font-weight:700;color:' + INK + '">' + esc(v == null ? '—' : v) + '</span></div>';
  }

  /* ------------------------------------------------------------ run + poll */
  function startRun(component, options) {
    api('/api/run/start', options)
      .then(function (r) {
        window.__AAU.run = r.run;
        component.setState({ running: true });
        poll(component, r.run);
      })
      .catch(function (e) { badge('run failed', RED); console.error(e); });
  }

  function poll(component, runId) {
    api('/api/run/status?run=' + encodeURIComponent(runId))
      .then(function (s) {
        window.__AAU.status = s;
        component.forceUpdate();
        if (s.running) { setTimeout(function () { poll(component, runId); }, 1200); }
        else {
          component.setState({ running: false });
          refresh(component);
        }
      })
      .catch(function () { component.setState({ running: false }); });
  }

  /* --------------------------------------------------- load the real data  */
  /* Two sources, best first:
   *   /api/state        the engine running on this machine -- can start runs
   *   data/state.json   what the engine wrote on its last GitHub Actions run
   * The published page has no process behind it, so it reads the file. That is
   * still real data produced by the real pipeline, just not on demand. */
  function refresh(component) {
    return api('/api/state').then(function (d) {
      window.__AAU.canRun = true;
      return d;
    }).catch(function () {
      return api('data/state.json').then(function (d) {
        window.__AAU.canRun = false;
        window.__AAU.snapshot = true;
        return d;
      });
    }).then(function (d) {
      window.__AAU.live = true;
      window.__AAU.state = d;
      window.__AAU.suggestions = d.suggestions || [];
      if (d.stats && d.stats.years) window.__AAU.years = d.stats.years;
      if (window.__aauApply) window.__aauApply(d);
      component.forceUpdate();
      var when = d.generated ? d.generated.slice(0, 10) : '';
      badge((window.__AAU.snapshot ? 'live data · ' + when
                                   : 'connected · ' + when)
            + (d.stats ? ' · ' + d.stats.papers.toLocaleString() + ' papers' : ''), G);
      return d;
    });
  }
  window.__AAU.refresh = refresh;
  window.__AAU.askRun = askRun;

  /* ------------------------------------------------- suggested additions   */
  /* Every run ends by asking who published with an AAU address but is not on
   * the roster. The rule does not bend -- off the roster means outside faculty
   * -- but the omission is put in front of you instead of silently standing. */
  function showSuggestions(component) {
    var list = window.__AAU.suggestions || [];
    if (!list.length) return;
    var rows = list.map(function (a, i) {
      return '<div data-i="' + i + '" style="display:flex;align-items:center;gap:14px;' +
        'padding:13px 0;border-bottom:1px solid #F0F3F1">' +
        '<div style="flex:1;min-width:0">' +
        '<div style="font-size:14.5px;font-weight:700;color:' + INK + '">' + esc(a.name) + '</div>' +
        '<div style="font-size:12.5px;color:' + META + ';margin-top:3px">' +
        esc(a.college || 'no college stated') + ' · ' + esc(a.papers) + ' AAU papers · h-index ' +
        esc(a.h) + ' · ' + esc(Number(a.cites).toLocaleString()) + ' citations</div></div>' +
        '<button data-add="' + i + '" style="background:' + G + ';border:0;border-radius:5px;' +
        'padding:8px 14px;font-family:' + FONT + ';font-size:13px;font-weight:700;color:#fff;' +
        'cursor:pointer;white-space:nowrap">Add</button>' +
        '<button data-no="' + i + '" style="background:#fff;border:1px solid #D5DED8;' +
        'border-radius:5px;padding:8px 12px;font-family:' + FONT + ';font-size:13px;' +
        'color:' + META + ';cursor:pointer;white-space:nowrap">Not faculty</button></div>';
    }).join('');

    var m = modal({
      width: 680,
      eyebrow: 'Found on this run',
      title: list.length === 1 ? 'One person is missing from your roster'
                               : list.length + ' people are missing from your roster',
      sub: 'Each of these printed an Al Ain University address on a paper and publishes like staff, but the roster does not list them. Adding someone makes them faculty from the next run onward.',
      html: '<div style="max-height:46vh;overflow:auto">' + rows + '</div>',
      cancelLabel: 'Close',
    });

    m.__wrap = document.getElementById('__aau_modal');
    m.__wrap.addEventListener('click', function (e) {
      var add = e.target.getAttribute && e.target.getAttribute('data-add');
      var no = e.target.getAttribute && e.target.getAttribute('data-no');
      if (add == null && no == null) return;
      e.stopPropagation();
      var i = Number(add == null ? no : add);
      var who = list[i];
      var row = e.target.closest('div[data-i]');
      if (add != null) {
        e.target.disabled = true;
        e.target.textContent = 'Adding…';
        api('/api/faculty/add', { name: who.name, auid: who.auid,
                                  college: who.college, confirm: true })
          .then(function () { row.style.opacity = .45; e.target.textContent = 'Added'; })
          .catch(function () { e.target.textContent = 'Failed'; });
      } else {
        api('/api/faculty/dismiss', { name: who.name }).catch(function () {});
        row.style.opacity = .35;
        row.querySelector('[data-add]').disabled = true;
      }
    });
  }
  window.__AAU.showSuggestions = showSuggestions;

  /* ------------------------------------------------------------- exports   */
  function exportOne(component, kind) {
    badge('building ' + kind + '…', G);
    return api('/api/export', { kind: String(kind).toLowerCase() })
      .then(function (r) {
        badge('saved ' + (r.path || '').split('/').pop(), G);
        modal({
          eyebrow: 'Export', title: 'Saved',
          sub: 'Written to ' + (r.path || ''),
          cancelLabel: 'Close',
        });
      })
      .catch(function (e) { badge('export failed', RED); console.error(e); });
  }
  function exportAll(component) {
    return exportOne(component, 'xlsx')
      .then(function () { return exportOne(component, 'pptx'); });
  }
  window.__AAU.exportOne = exportOne;
  window.__AAU.exportAll = exportAll;

  /* ------------------------------------------------------- review decision */
  function decide(component, c) {
    if (!c || !c.auid) return;
    api('/api/faculty/resolve', { auid: c.auid, name: c.name })
      .then(function () { refresh(component); badge('resolved ' + c.auid, G); })
      .catch(function () { badge('could not save', RED); });
  }
  window.__AAU.decide = decide;

  /* ---------------------------------------------------------- import a CSV */
  function importCsv(component) {
    var f = document.createElement('input');
    f.type = 'file';
    f.accept = '.csv,text/csv';
    f.onchange = function () {
      var file = f.files && f.files[0];
      if (!file) return;
      var r = new FileReader();
      r.onload = function () {
        badge('importing roster…', G);
        api('/api/faculty', { csv: String(r.result) })
          .then(function (res) {
            refresh(component);
            modal({ eyebrow: 'Roster', title: 'Roster imported',
                    sub: (res.count || 0) + ' people read from ' + file.name + '.',
                    cancelLabel: 'Close' });
          })
          .catch(function (e) { badge('import failed', RED); console.error(e); });
      };
      r.readAsText(file);
    };
    f.click();
  }
  window.__AAU.importCsv = importCsv;

  function stop() {
    if (window.__AAU.run) api('/api/run/stop', { run: window.__AAU.run }).catch(function () {});
  }
  window.__AAU.stop = stop;

  function demoNote() {
    var st = window.__AAU.state || {};
    var when = st.generated ? st.generated.slice(0, 10) : 'the last run';
    modal({
      eyebrow: 'Run',
      title: 'This page reads the last run',
      sub: 'The figures here are real, from the run finished on ' + when +
        '. The engine itself runs on GitHub, on a schedule and on demand -- a '
        + 'published page has no process behind it, so it cannot start one.',
      choices: [
        {
          label: 'Start a run on GitHub now',
          hint: 'Opens the Actions tab. Press "Run workflow" and it fetches '
            + 'Scopus, rebuilds the census and updates this page.',
          go: function () {
            window.open('https://github.com/AbdallahAbouHajal/'
              + 'aau-research-tracker/actions/workflows/refresh.yml', '_blank');
          },
        },
        {
          label: 'Run it on your own machine instead',
          hint: 'Open the project and launch it. The same page then drives the '
            + 'pipeline directly and every button works, including exports.',
          go: function () {},
        },
      ],
      cancelLabel: 'Close',
    });
  }
  window.__AAU.demoNote = demoNote;
})();
</script>
