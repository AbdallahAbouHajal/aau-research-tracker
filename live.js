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
  var lastBadge = 'live data';

  /* ------------------------------------------------------------- transport */
  // The generated stamp of the data now on screen. Used to bust the CDN on
  // the lazy files and to notice, from a HEAD, that a run has published.
  function stamp() {
    var st = window.__AAU.state;
    return (st && st.generated) || '0';
  }

  function api(path, body) {
    var opt = { headers: { 'Content-Type': 'application/json' },
                // A run finishes, the page immediately re-reads
                // data/state.json, and the edge or the disk cache serves the
                // bytes from before the run -- so the numbers do not move and
                // the badge still says "live data".
                cache: 'no-store' };
    if (body !== undefined) { opt.method = 'POST'; opt.body = JSON.stringify(body); }
    return fetch(path, opt).then(function (r) {
      if (!r.ok) throw new Error(path + ' -> HTTP ' + r.status);
      return r.json();
    });
  }
  window.__AAU.api = api;

  /* ------------------------------------------------------ a face per person */
  /* AAU publishes a portrait for most of its academic staff, and the roster
   * already holds each person's profile URL, so the join is AAU's own
   * statement of who is who -- no name matching happens in the browser at
   * all. The engine resolves it through the same resolver that gave each
   * person their college, and hands the page a filename or an empty string.
   *
   * `src` must NEVER be set to '': an empty src resolves to the document URL,
   * so on a screen of 500 rows that is 500 fetches of index.html. The absent
   * case is a 43-byte transparent GIF plus display:none -- and a hidden lazy
   * image is never fetched at all. */
  var BLANK = 'data:image/gif;base64,'
            + 'R0lGODlhAQABAIAAAAAAAP///yH5BAEAAAAALAAAAAABAAEAAAIBRAA7';
  window.__AAU.faceOf = function (a) {
    var f = a && a.photo;
    return f ? { src: 'photos/' + f, show: 'block' }
             : { src: BLANK, show: 'none' };
  };
  /* The same rule the author panel already uses, so a person's monogram is
   * identical wherever it is drawn. */
  window.__AAU.initialsOf = function (name) {
    return String(name || '').split(' ')
      .filter(function (w) { return /^[A-Z]/.test(w); })
      .slice(0, 2).map(function (w) { return w[0]; }).join('');
  };

  /* --------------------------------------------------- a mark per college */
  /* Eight colleges already carry a hue each, and a hue on its own is hard to
   * name -- you learn it, you do not read it. A mark says which college
   * before the words do, and it survives where colour cannot: greyscale
   * print, a colour-blind reader, a 3px rail seen at arm's length.
   * One per college, from what the college actually does. */
  var COLLEGE_ICON = {
    'College of Engineering': '\u2699\ufe0f',
    'College of Pharmacy': '\ud83d\udc8a',
    'College of Law': '\u2696\ufe0f',
    'College of Education, Humanities and Social Sciences': '\ud83c\udf93',
    'College of Business': '\ud83d\udcc8',
    'College of Communication and Media': '\ud83c\udf99\ufe0f',
    'College of Dentistry': '\ud83e\uddb7',
    'College of Nursing': '\ud83e\ude7a',
  };
  window.__AAU.collegeIcon = function (name) {
    // Anything unrecognised gets the neutral one rather than an empty gap,
    // so a college added later still lines up with the other eight.
    return COLLEGE_ICON[name] || '\ud83c\udfdb\ufe0f';
  };

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
  // The close() of whichever modal is open, so opening another can retire
  // it properly instead of orphaning its Escape handler on document.
  var openModal = null;

  function modal(spec) {
    // Removing the node left the previous modal's Escape handler bound to
    // document forever, so walking a three-step wizard left three stale
    // handlers, each ready to close whatever was open next.
    if (openModal) { try { openModal(); } catch (e) { /* already gone */ } }
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
      // iOS capitalises the first letter of a text input by default and the
      // worker compares byte for byte, so a correct passphrase typed on an
      // iPad was rejected -- and the failure path then wiped what was typed,
      // so the professor could loop on this forever.
      inp.setAttribute('autocapitalize', 'none');
      inp.setAttribute('autocorrect', 'off');
      inp.setAttribute('autocomplete', 'off');
      inp.setAttribute('spellcheck', 'false');
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
      // Resolving #__aau_modal at call time meant a slow lookup's close()
      // deleted whichever modal happened to be open several clicks later, and
      // replaced it with its own result. A modal closes the node it built.
      document.removeEventListener('keydown', onEsc);
      if (openModal === close) openModal = null;
      if (wrap && wrap.parentNode) wrap.parentNode.removeChild(wrap);
    }
    openModal = close;
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
          hint: window.__AAU.canRun
            ? 'Paste their page on aau.ac.ae and their Scopus record is found for you.'
            : 'Needs the app running on your own machine, so it can write to the roster.',
          go: function () {
            if (window.__AAU.canRun) { askProfile(component); return; }
            modal({
              eyebrow: 'Add a researcher',
              title: 'Do it on the Roster screen',
              sub: 'Adding somebody changes the roster, which the published '
                + 'page can only read. On the Roster screen you can add one '
                + 'person by hand or import a whole CSV — from the tracker '
                + 'running on your own machine.',
              choices: [
                { label: 'Show me the Roster screen',
                  hint: 'Import a CSV, or add one person, or clear the review queue.',
                  go: function () { component.setState({ screen: 'roster' }); } },
                { label: 'What does the CSV need?',
                  hint: 'The columns, with an example and a template.',
                  go: function () { csvHelp(); } },
              ],
              cancelLabel: 'Close',
            });
          },
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
      title: 'Which papers should it cover?',
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
          label: 'Choose exact dates',
          hint: 'Any window down to the day — a quarter, a semester, since a review.',
          go: function () { askDates(component, scope); },
        },
      ],
    });
  }

  /* Month and year is the useful grain: Scopus prints a cover date whose day
   * is often the first of the month anyway, and nobody asks for "papers since
   * the 14th". The month is expanded to its full span before filtering, so
   * "March 2025 to June 2026" means 2025-03-01 through 2026-06-30 inclusive. */
  function monthEnd(ym) {                    // '2026-06' -> '2026-06-30'
    var y = +ym.slice(0, 4), m = +ym.slice(5, 7);
    return ym + '-' + String(new Date(y, m, 0).getDate()).padStart(2, '0');
  }

  function askDates(component, scope) {
    var today = new Date();
    var ym = function (d) {
      return d.getFullYear() + '-' + String(d.getMonth() + 1).padStart(2, '0');
    };
    var deflt_to = ym(today);
    var deflt_from = ym(new Date(today.getFullYear() - 1, today.getMonth(), 1));

    var field = function (id, label, val) {
      return '<div style="flex:1;min-width:0">'
        + '<div style="font-size:11.5px;font-weight:700;letter-spacing:.07em;'
        + 'text-transform:uppercase;color:' + META + ';margin-bottom:6px">'
        + esc(label) + '</div>'
        + '<input id="' + id + '" type="month" value="' + esc(val) + '" '
        + 'style="width:100%;box-sizing:border-box;border:1px solid #D5DED8;'
        + 'border-radius:6px;padding:11px 12px;font-family:' + FONT + ';'
        + 'font-size:14.5px;color:' + INK + ';outline:none;background:#fff"></div>';
    };

    var m = modal({
      width: 560,
      eyebrow: 'New run',
      title: 'Pick the months',
      sub: 'Papers are counted by the publication date Scopus prints on them.',
      html: '<div style="display:flex;gap:14px;align-items:flex-end">'
        + field('aauFrom', 'From', deflt_from)
        + field('aauTo', 'To', deflt_to)
        + '</div>'
        + '<div id="aauDateNote" style="font-size:12.5px;color:' + META
        + ';margin-top:10px;line-height:1.5;min-height:18px">Both months are '
        + 'included, start to end. A wider window takes longer.</div>',
      submit: {
        label: 'Run it',
        go: function () {
          var box = document.getElementById('__aau_modal');
          var f = box.querySelector('#aauFrom').value;
          var t = box.querySelector('#aauTo').value;
          var note = box.querySelector('#aauDateNote');
          if (!f || !t) {
            note.style.color = RED;
            note.textContent = 'Pick both months.';
            return;
          }
          if (f > t) {
            note.style.color = RED;
            note.textContent = 'The first month is after the second one.';
            return;
          }
          var months = (+t.slice(0, 4) - +f.slice(0, 4)) * 12
            + (+t.slice(5, 7) - +f.slice(5, 7));
          if (months > 72) {
            note.style.color = RED;
            note.textContent = 'That is more than six years. Narrow it, or the run will take a very long time.';
            return;
          }
          m.close();
          startRun(component, { mode: 'refresh', scope: scope,
                                date_from: f + '-01', date_to: monthEnd(t) });
        },
      },
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
  /* ---------------------------------------------------------- run on GitHub
   * The published page has no engine, but the engine runs on GitHub Actions --
   * so "Run now" there starts a real run by dispatching that workflow. It
   * needs a token, which lives only in this browser's localStorage: never in
   * the repo, never sent anywhere but api.github.com.
   */
  var WORKER = 'https://aau-tracker-run.abouhajal.workers.dev';
  var PASS_KEY = 'aau_run_pass';

  /* No GitHub account, no token, nothing installed. The GitHub credential
   * lives as a secret on the proxy and never reaches a browser; a reader
   * proves they are allowed with a passphrase. Asking the proxy what the run
   * is doing needs no passphrase at all, because reporting starts nothing --
   * so the progress bar moves for everyone. */
  function pass() {
    try { return localStorage.getItem(PASS_KEY) || ''; } catch (e) { return ''; }
  }
  function setPass(v) {
    try { v ? localStorage.setItem(PASS_KEY, v) : localStorage.removeItem(PASS_KEY); }
    catch (e) {}
  }
  window.__AAU.forgetPassphrase = function () {
    setPass(''); badge('passphrase cleared', META);
  };

  function askPass(then) {
    var m = modal({
      width: 560,
      eyebrow: 'One-time setup',
      title: 'The passphrase for starting a run',
      sub: 'Whoever set this up will have given you one. It is remembered in '
        + 'this browser, so you are asked once.',
      input: { placeholder: 'passphrase', note: 'Kept in this browser only.' },
      submit: {
        label: 'Save and continue',
        go: function () {
          var v = (m.__input.value || '').trim();
          if (!v) { m.__note.textContent = 'Type the passphrase.'; return; }
          setPass(v);
          m.close();
          then();
        },
      },
    });
  }

  function dispatch(options, comp) {
    badge('asking for a run…', G);
    fetch(WORKER + '/run', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        passphrase: pass(),
        years: (options.years || []).join(','),
        scope: options.scope || 'compare',
        date_from: options.date_from || '',
        date_to: options.date_to || '',
      }),
    }).then(function (r) {
      return r.json().then(function (j) { return { ok: r.ok, j: j }; });
    }).then(function (res) {
      if (res.j && res.j.already) {
        badge('a run is already going', G);
        watchRun(comp);
        return;
      }
      if (!res.ok || !res.j || !res.j.started) {
        var msg = (res.j && res.j.error) || 'The run could not be started.';
        badge('could not start the run', RED);
        if (/passphrase/i.test(msg)) setPass('');
        modal({
          eyebrow: 'Run', title: 'It did not start', sub: msg,
          cancelLabel: 'Close',
        });
        return;
      }
      watchRun(comp, true);
    }).catch(function (e) {
      badge('could not reach the run service', RED);
      console.error(e);
    });
  }

  var STAGE_NAMES = ['Read the faculty roster', 'Find each person in Scopus',
    'Collect the papers', 'Check the extra papers found',
    'Sort faculty from students', 'Build the census and compare'];

  // The two steps that decide whether anyone SEES the new numbers -- the
  // commit and the check that it landed -- are not among the six stages, so a
  // run that computed everything and then failed to publish drew six green
  // ticks over the previous census.
  var PUBLISH_STEPS = ['Commit the new state', 'Verify the refresh actually landed'];

  function publishFailure(steps) {
    for (var i = 0; i < (steps || []).length; i++) {
      var st = steps[i];
      if (PUBLISH_STEPS.indexOf(st.name) >= 0 && st.status === 'completed'
          && st.conclusion && st.conclusion !== 'success'
          && st.conclusion !== 'skipped') {
        return st.name;
      }
    }
    return '';
  }

  function stagesFromSteps(steps) {
    return STAGE_NAMES.map(function (name) {
      var st = null;
      for (var i = 0; i < (steps || []).length; i++) {
        if (steps[i].name === name) { st = steps[i]; break; }
      }
      if (!st) return { pct: 0, active: false, label: 'Waiting' };
      if (st.status === 'completed') {
        return st.conclusion === 'success'
          ? { pct: 100, active: false, label: 'Done' }
          : { pct: 100, active: false, label: st.conclusion || 'failed' };
      }
      if (st.status === 'in_progress') return { pct: 55, active: true, label: 'Working' };
      return { pct: 0, active: false, label: 'Waiting' };
    });
  }

  // Every call used to start its own independent poll chain, so pressing Run
  // twice left two of them alive, each free to navigate the reader away.
  var watchToken = 0;
  function watchOff() {
    watchToken += 1;
    window.__AAU.status = null;
  }
  window.__AAU.watchOff = watchOff;

  function watchRun(component, announce) {
    var started = Date.now();
    watchToken += 1;
    var mine = watchToken;
    if (announce) {
      modal({
        eyebrow: 'Run started',
        title: 'It is running now',
        sub: 'The census is being rebuilt. It takes a few minutes, and this '
          + 'page updates itself when it lands. You can close this and keep '
          + 'reading.',
        cancelLabel: 'Close',
      });
    }
    if (component) component.setState({ running: true });
    (function poll() {
      if (mine !== watchToken) return;          // a newer watch replaced this one
      if (Date.now() - started > 50 * 60 * 1000) {
        badge('stopped watching this run after 50 minutes', RED);
        if (component) component.setState({ running: false });
        return;
      }
      fetch(WORKER + '/status', { cache: 'no-store' }).then(function (r) {
        return r.json().then(function (j) {
          if (!r.ok) throw new Error(j && j.error ? j.error : 'HTTP ' + r.status);
          return j;
        });
      })
        .then(function (d) {
          // GitHub creates a dispatched run asynchronously, and /status
          // answers with the NEWEST run -- which for the first few seconds is
          // the previous, completed, successful one. Taken at face value that
          // announced "run finished", reloaded unchanged figures and dropped
          // the reader on the Dashboard before the real run had even started.
          if (announce && d.started && Date.parse(d.started) < started - 15000) {
            badge('waiting for the run to appear', G);
            return setTimeout(poll, 4000);
          }
          var st = stagesFromSteps(d.steps);
          window.__AAU.status = {
            running: !!d.running, stages: st,
            findings: (window.__AAU.state || {}).findings || [],
          };
          if (component) component.forceUpdate();
          var done = st.filter(function (x) { return x.pct >= 100; }).length;
          if (d.running) {
            badge('running · stage ' + Math.min(6, done + 1) + ' of 6', G);
            return setTimeout(poll, 6000);
          }
          window.__AAU.status.running = false;
          if (component) component.setState({ running: false });
          if (d.conclusion === 'success') {
            badge('run finished · loading the new figures', G);
            refresh(component).then(function () {
              window.__AAU.status = null;
              if (component) component.setState({ screen: 'dash', running: false });
            }).catch(function () { location.reload(); });
          } else {
            var pf = publishFailure(d.steps);
            if (pf) {
              badge('the census was built but not published', RED);
              modal({
                eyebrow: 'The run',
                title: 'It finished the work but could not publish it',
                sub: 'Every stage of the census completed, then "' + pf
                  + '" failed. The figures on this page are still the '
                  + 'previous run\'s. Nothing was lost -- the run can be '
                  + 'repeated -- but nothing on screen has moved.',
                cancelLabel: 'Close',
              });
              return;
            }
            badge('run ' + (d.conclusion || 'failed'), RED);
          }
        })
        .catch(function (e) {
          badge(String((e && e.message) || 'cannot reach the run service')
                .slice(0, 70), RED);
          setTimeout(poll, 12000);
        });
    })();
  }

  /* Pressing Run now with no passphrase yet. Say what the schedule already
   * does before asking anyone for anything -- most readers need nothing. */
  /* ------------------------------------------------- the roster, two ways  */
  var COLLEGES = [
    'College of Engineering', 'College of Pharmacy', 'College of Law',
    'College of Education, Humanities and Social Sciences',
    'College of Business', 'College of Communication and Media',
    'College of Dentistry', 'College of Nursing',
  ];

  /* Two columns are required and five are optional, and the importer is
   * forgiving about the college wording -- "engineering" or "Eng." both land
   * on College of Engineering. Say so before someone builds a file blind. */
  /* Roster edits go through the proxy when the page has no engine behind it.
   * The passphrase is the same one that starts a run: it was deliberately
   * given this reach, so somebody with it can fix the roster from anywhere. */
  function viaProxy(path, payload, onOk, onErr) {
    var send = function () {
      return fetch(WORKER + path, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(Object.assign({ passphrase: pass() }, payload)),
      }).then(function (r) {
        return r.json().then(function (j) { return { ok: r.ok, j: j }; });
      }).then(function (res) {
        if (!res.ok || !res.j || res.j.error) {
          var msg = (res.j && res.j.error) || 'It was refused.';
          if (/passphrase/i.test(msg)) setPass('');
          onErr(msg);
          return;
        }
        onOk(res.j);
      }).catch(function (e) { onErr(String(e.message || e)); });
    };
    if (!pass()) { askPass(send); return; }
    send();
  }

  function csvHelp() {
    var row = function (n, req, what) {
      return '<tr>'
        + '<td style="padding:7px 12px 7px 0;font-weight:700;color:' + INK
        + ';white-space:nowrap;vertical-align:top">' + esc(n) + '</td>'
        + '<td style="padding:7px 12px 7px 0;color:' + (req ? G : META)
        + ';white-space:nowrap;vertical-align:top;font-size:12.5px">'
        + (req ? 'required' : 'optional') + '</td>'
        + '<td style="padding:7px 0;color:' + META + ';line-height:1.45">'
        + esc(what) + '</td></tr>';
    };
    modal({
      width: 680,
      eyebrow: 'Roster file',
      title: 'What the CSV needs',
      sub: 'One row per person, a header row on top. Extra columns are ignored, '
        + 'so a directory export usually works as it comes.',
      html:
        '<table style="width:100%;border-collapse:collapse;font-size:13.5px">'
        + row('name', true, 'As the university writes it. Degree suffixes like ", Ph.D" are stripped for you — Scopus never prints them.')
        + row('college', true, 'Any recognisable spelling. "engineering", "Eng.", "College of Engineering" all land on the same college.')
        + row('title', false, 'Professor, Assistant Professor, Dean…')
        + row('staff_type', false, 'academic or administrative. Anything else is treated as academic.')
        + row('profile_url', false, 'Their page on aau.ac.ae. Worth including — it is how someone with no name match is still found.')
        + row('email', false, 'Role mailboxes like Engineering@aau.ac.ae are flagged and never used to identify a person.')
        + row('department', false, 'Kept, not used for anything yet.')
        + '</table>'
        + '<div style="margin-top:16px;padding:13px 15px;background:#F4F6F5;'
        + 'border-radius:6px;font:12.5px/1.6 ui-monospace,SFMono-Regular,Menlo,monospace;'
        + 'color:' + INK + ';overflow-x:auto;white-space:pre">'
        + esc('name,college,title,staff_type,profile_url\n'
            + 'Mosab Tabash,College of Business,Professor,academic,https://aau.ac.ae/en/staff/mosab-tabash\n'
            + 'Sara Khoury,Pharmacy,Assistant Professor,academic,')
        + '</div>'
        + '<div style="font-size:12.5px;color:' + META + ';margin-top:12px;line-height:1.5">'
        + 'A person listed under two colleges is one person: the first listing '
        + 'is their home college, the second is kept as a cross-listing.</div>',
      choices: [{
        label: 'Download a template',
        hint: 'A CSV with the header row and one example, ready to fill in.',
        go: function () {
          var csv = 'name,college,title,staff_type,profile_url,email\n'
            + 'Example Person,College of Engineering,Assistant Professor,academic,https://aau.ac.ae/en/staff/example,\n';
          var a = document.createElement('a');
          a.href = 'data:text/csv;charset=utf-8,' + encodeURIComponent(csv);
          a.download = 'aau_roster_template.csv';
          document.body.appendChild(a); a.click(); a.remove();
        },
      }],
      cancelLabel: 'Close',
    });
  }
  window.__AAU.csvHelp = csvHelp;

  /* Adding one person by hand. A whole CSV is the wrong shape for "we hired
   * someone in March". */
  function addPerson(component) {
    var opts = COLLEGES.map(function (c) {
      return '<option value="' + esc(c) + '">' + esc(c) + '</option>';
    }).join('');
    var m = modal({
      width: 600,
      eyebrow: 'Roster',
      title: 'Add one person',
      sub: 'Their Scopus record is looked up for you. A link to their page on '
        + 'aau.ac.ae makes that much more reliable.',
      html:
        '<div style="display:flex;flex-direction:column;gap:12px">'
        + fieldRow('apName', 'Name', 'text', 'As the university writes it', '')
        + '<div><div style="font-size:11.5px;font-weight:700;letter-spacing:.07em;'
        + 'text-transform:uppercase;color:' + META + ';margin-bottom:6px">College</div>'
        + '<select id="apCollege" style="width:100%;box-sizing:border-box;'
        + 'border:1px solid #D5DED8;border-radius:6px;padding:11px 12px;'
        + 'font-family:' + FONT + ';font-size:14.5px;color:' + INK + ';background:#fff">'
        + opts + '</select></div>'
        + fieldRow('apTitle', 'Title', 'text', 'Assistant Professor', '')
        + fieldRow('apUrl', 'Page on aau.ac.ae', 'url', 'https://aau.ac.ae/en/staff/…', '')
        + '</div>'
        + '<div id="apNote" style="font-size:12.5px;color:' + META
        + ';margin-top:12px;line-height:1.5;min-height:18px"></div>',
      submit: {
        label: 'Find and add',
        go: function () {
          var box = document.getElementById('__aau_modal');
          var name = box.querySelector('#apName').value.trim();
          var note = box.querySelector('#apNote');
          if (!name) { note.style.color = RED; note.textContent = 'A name at least.'; return; }
          var payload = {
            name: name,
            college: box.querySelector('#apCollege').value,
            title: box.querySelector('#apTitle').value.trim(),
            url: box.querySelector('#apUrl').value.trim(),
          };
          note.style.color = META;

          var done = function (auid) {
            m.close();
            refresh(component);
            modal({
              eyebrow: 'Roster', title: 'Added: ' + name,
              sub: auid
                ? ('Scopus author ' + auid + '. Their papers appear on the next run.')
                : 'On the roster from now on. Their Scopus record is looked up on '
                  + 'the next run — from their aau.ac.ae page if you gave one, '
                  + 'which is the most reliable route.',
              cancelLabel: 'Close',
            });
          };
          // `note` was captured before any await. If the passphrase prompt
          // opens, THIS form is torn out of the document first, so the error
          // was written into an orphaned node and the professor saw nothing at
          // all: no message, no badge, no person added. Write to the live node
          // if it is still there, and say it out loud if it is not.
          var failed = function (msg) {
            var live = document.getElementById('apNote');
            if (live) {
              live.style.color = RED;
              live.textContent = msg;
            } else {
              badge(String(msg).slice(0, 70), RED);
              modal({ eyebrow: 'Roster', title: 'That person was not added',
                      sub: msg, cancelLabel: 'Close' });
            }
          };

          if (window.__AAU.canRun) {
            note.textContent = 'Looking them up in Scopus…';
            api('/api/faculty/add', Object.assign({ confirm: true }, payload))
              .then(function (r) { done(r.auid); })
              .catch(function (e) { failed(String(e.message || e)); });
          } else {
            note.textContent = 'Writing them to the roster…';
            viaProxy('/roster/add', payload, function () { done(null); }, failed);
          }
        },
      },
    });
  }
  window.__AAU.addPerson = addPerson;

  function fieldRow(id, label, type, ph, val) {
    return '<div><div style="font-size:11.5px;font-weight:700;letter-spacing:.07em;'
      + 'text-transform:uppercase;color:' + META + ';margin-bottom:6px">'
      + esc(label) + '</div>'
      + '<input id="' + id + '" type="' + type + '" placeholder="' + esc(ph)
      + '" value="' + esc(val) + '" style="width:100%;box-sizing:border-box;'
      + 'border:1px solid #D5DED8;border-radius:6px;padding:11px 12px;'
      + 'font-family:' + FONT + ';font-size:14.5px;color:' + INK + ';outline:none"></div>';
  }

  /* Taking somebody off the roster. Not a deletion: their papers stay in the
   * census, they simply stop counting as faculty -- which is the whole meaning
   * of the roster. Worth saying, because "remove" reads like erasure. */
  function removePerson(component, name, college) {
    if (!name) return;
    modal({
      width: 560,
      eyebrow: 'Roster',
      title: 'Take ' + name + ' off the roster?',
      sub: 'Their papers stay in the census. They stop counting as faculty and '
        + 'become outside faculty from the next run, and they show up again in '
        + 'the "not on your roster" list if they keep publishing with an AAU '
        + 'address. Every previous version of the roster is kept, so this can '
        + 'be undone.',
      choices: [{
        label: 'Take them off',
        hint: college ? ('Currently listed under ' + college + '.') : '',
        go: function () {
          badge('updating the roster…', G);
          var ok = function () {
            refresh(component);
            badge('removed ' + name, G);
          };
          var bad = function (msg) {
            badge('could not remove', RED);
            modal({ eyebrow: 'Roster', title: 'Not removed', sub: msg,
                    cancelLabel: 'Close' });
          };
          if (window.__AAU.canRun) {
            api('/api/faculty/remove', { name: name })
              .then(ok).catch(function (e) { bad(String(e.message || e)); });
          } else {
            viaProxy('/roster/remove', { name: name }, ok, bad);
          }
        },
      }],
      cancelLabel: 'Keep them',
    });
  }
  window.__AAU.removePerson = removePerson;

  function needsLocal(what) {
    modal({
      eyebrow: 'Roster',
      title: what + ' has to happen on your own machine',
      sub: 'The published page can only read. Open the tracker locally, do it '
        + 'on the Roster screen there, and the next run carries it everywhere.',
      cancelLabel: 'Close',
    });
  }
  window.__AAU.needsLocal = needsLocal;

  function explainSchedule(component, options) {
    var st = window.__AAU.state || {};
    var when = st.generated ? st.generated.slice(0, 10) : 'recently';
    modal({
      width: 600,
      eyebrow: 'Run',
      title: 'This updates itself every Monday',
      sub: 'The census is rebuilt at 07:00 Gulf time each Monday, and whenever '
        + 'someone asks for it. The figures on screen are from the run on '
        + when + '. Nothing is needed from you to read them.',
      choices: [
        {
          label: 'Start a run now',
          hint: 'Needs the passphrase you were given, once. No GitHub account '
            + 'and nothing to install.',
          go: function () { askPass(function () { dispatch(options, component); }); },
        },
      ],
      cancelLabel: 'Close',
    });
  }

  function startRun(component, options) {
    if (!window.__AAU.canRun) {          // published page -> run it on GitHub
      if (!pass()) { explainSchedule(component, options); return; }
      dispatch(options, component);
      return;
    }
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
      if (component && component.forceUpdate) component.forceUpdate();
      // A new stamp means new files behind the two lazy screens as well.
      // Drop them, then reload whichever one is open right now so the reader
      // sees the change instead of a screen that quietly disagrees with the
      // Dashboard.
      if (d.generated && d.generated !== lazyStamp) {
        lazyStamp = d.generated;
        dropLazy();
        seenNetTag = null;   // a new census supersedes the old backfill
        component = component || window.__AAU.component;
        var scr = component && component.state && component.state.screen;
        if (scr === 'papers') window.__AAU.needCorpus(component);
        if (scr === 'net') window.__AAU.needNetwork(component);
      }
      var when = d.generated ? d.generated.slice(0, 10) : '';
      lastBadge = (window.__AAU.snapshot ? 'live data · ' + when
                                          : 'connected · ' + when)
            + (d.stats ? ' · ' + d.stats.papers.toLocaleString() + ' papers' : '');
      badge(lastBadge, G);
      return d;
    });
  }
  window.__AAU.refresh = refresh;

  /* ------------------------------------------- noticing a run on its own  */
  /* Until now the figures moved only when this tab had watched the run it
   * started. A run begun on a phone, the Monday schedule, or the same run
   * after the reader had navigated away all left the page sitting on old
   * numbers until someone thought to hard-reload -- and a plain reload was
   * not enough, because GitHub Pages sends `max-age=600` and the browser
   * simply served the copy it already had.
   *
   * So the page asks. A HEAD costs headers only, and the ETag changes
   * exactly when the published file does. It runs only while the tab is
   * visible -- a backgrounded tab has nobody to tell -- and checks at once
   * when the reader comes back, which is when they would otherwise have
   * reached for reload. */
  var seenTag = null;
  var seenNetTag = null;
  var watchTimer = null;
  var headFails = 0;

  /* The collaboration file has its own publisher and its own clock. Reading
   * every paper's institutions takes about a second each, so it is a second
   * job that lands its checkpoints for twenty minutes AFTER the run is done
   * -- and it rewrites network.json ALONE, leaving state.json untouched.
   * Watching only state.json therefore misses every one of those: the census
   * would arrive and the collaboration screen would sit on the coverage it
   * had when the run finished until someone reloaded. So it is watched
   * separately. */
  function checkNetwork(component, announceIt) {
    return fetch('data/network.json?v=' + Date.now(),
                 { method: 'HEAD', cache: 'no-store' })
      .then(function (r) {
        if (!r.ok) return;
        var tag = r.headers.get('etag') || r.headers.get('last-modified') || '';
        if (seenNetTag === null && tag) { seenNetTag = tag; return; }
        if (!tag || tag === seenNetTag) return;
        seenNetTag = tag;
        lazy.net = null;                  // whatever is held is now stale
        var scr = component && component.state && component.state.screen;
        if (scr !== 'net') return;        // the next visit will fetch it
        window.__AAU.needNetwork(component);
        if (announceIt !== false) badge('collaboration updated', G);
      })
      .catch(function () {});
  }

  function checkForNewData(component, announceIt) {
    // The run watcher owns the page while a run it started is going; two
    // refreshes racing would fight over the screen.
    if (window.__AAU.status && window.__AAU.status.running) return;
    if (document.hidden) return;
    component = component || window.__AAU.component;
    checkNetwork(component, announceIt);
    return fetch('data/state.json?v=' + Date.now(),
                 { method: 'HEAD', cache: 'no-store' })
      .then(function (r) {
        if (!r.ok) throw new Error('HTTP ' + r.status);
        headFails = 0;
        var tag = r.headers.get('etag') || r.headers.get('last-modified') || '';
        // First call of the session: the file IS what we are displaying.
        if (seenTag === null && tag) { seenTag = tag; return; }
        if (tag && tag === seenTag) return;      // nothing moved
        seenTag = tag;
        return api('data/state.json').then(function (d) {
          var showing = (window.__AAU.state || {}).generated;
          if (!d.generated || d.generated === showing) return;   // our own
          return refresh(component).then(function () {
            // Deliberately does NOT move the reader. They may be halfway
            // through the Roster; the figures update underneath them and the
            // badge says why. Only a run this tab started earns a screen
            // change.
            if (announceIt !== false) {
              var st = window.__AAU.state || {};
              badge('new figures published'
                    + (st.stats ? ' · ' + st.stats.papers.toLocaleString()
                       + ' papers' : ''), G);
            }
          });
        });
      })
      .catch(function () {
        // A local engine serves /api/state and has no data/state.json to
        // HEAD. Two failures and this stops asking rather than logging a
        // 404 every minute for the rest of the session.
        if (++headFails >= 2 && watchTimer) {
          clearInterval(watchTimer); watchTimer = null;
        }
      });
  }
  window.__AAU.checkForNewData = checkForNewData;

  function watchForNewData(component) {
    window.__AAU.component = component;    // a timer has no `this` to use
    if (watchTimer) return;
    watchTimer = setInterval(function () {
      checkForNewData(component);
    }, 60000);
    document.addEventListener('visibilitychange', function () {
      if (!document.hidden) checkForNewData(component);
    });
    // Establish the baseline without announcing anything.
    checkForNewData(component, false);
  }
  window.__AAU.watchForNewData = watchForNewData;

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
      var btn = e.target;

      /* Asking for the passphrase opens a modal, which would replace this
       * list. So ask first, then put the list back where it was. */
      if (!window.__AAU.canRun && !pass()) {
        m.close();
        askPass(function () { showSuggestions(component); });
        return;
      }

      var settled = function (label) {
        btn.textContent = label;
        row.style.opacity = .45;
        var other = row.querySelector(add != null ? '[data-no]' : '[data-add]');
        if (other) other.disabled = true;
        refresh(component);
      };
      var failed = function (msg) {
        btn.disabled = false;
        btn.textContent = add != null ? 'Add' : 'Not faculty';
        badge(String(msg).slice(0, 60), RED);
      };

      btn.disabled = true;
      btn.textContent = add != null ? 'Adding…' : 'Saving…';

      if (add != null) {
        var payload = { name: who.name, college: who.college, auid: who.auid };
        if (window.__AAU.canRun) {
          api('/api/faculty/add', Object.assign({ confirm: true }, payload))
            .then(function () { settled('Added'); })
            .catch(function (e2) { failed(e2.message || e2); });
        } else {
          viaProxy('/roster/add', payload,
                   function () { settled('Added'); }, failed);
        }
      } else {
        if (window.__AAU.canRun) {
          api('/api/faculty/dismiss', { name: who.name })
            .then(function () { settled('Not faculty'); })
            .catch(function (e2) { failed(e2.message || e2); });
        } else {
          viaProxy('/roster/dismiss', { name: who.name },
                   function () { settled('Not faculty'); }, failed);
        }
      }
    });
  }

  window.__AAU.showSuggestions = showSuggestions;

  /* ------------------------------------------------------------- exports   */
  /* Every run writes the three files next to the data, under a stable name,
   * so the published page can hand them over with an ordinary download. When
   * the engine is running locally it rebuilds them first. */
  var FILES = {
    xlsx:   ['downloads/AAU_Research_Tracker.xlsx', 'the workbook'],
    pptx:   ['downloads/AAU_Research_Tracker.pptx', 'the slide deck'],
    charts: ['downloads/AAU_Charts.zip', 'the chart pack'],
  };

  function grab(url, name) {
    var a = document.createElement('a');
    a.href = url; a.download = name || '';
    document.body.appendChild(a); a.click(); a.remove();
  }

  function exportOne(component, kind) {
    var k = String(kind || '').toLowerCase();
    if (k === 'chart' || k === 'chartpack' || k === 'png') k = 'charts';
    if (!FILES[k]) k = 'xlsx';
    var url = FILES[k][0], label = FILES[k][1];

    if (!window.__AAU.canRun) {                 // published page: just download
      badge('downloading ' + label + '…', G);
      grab(url, url.split('/').pop());
      setTimeout(function () { badge(lastBadge, G); }, 1800);
      return Promise.resolve();
    }
    badge('building ' + label + '…', G);        // local engine: rebuild first
    return api('/api/export', { kind: k })
      .then(function (r) {
        badge('saved ' + label, G);
        grab((r.url || url) + '?t=' + Date.now(), url.split('/').pop());
      })
      .catch(function (e) {
        console.error(e);
        badge('served the last build', G);
        grab(url, url.split('/').pop());
      });
  }

  function exportAll(component) {
    return exportOne(component, 'xlsx')
      .then(function () { return new Promise(function (r) { setTimeout(r, 900); }); })
      .then(function () { return exportOne(component, 'charts'); })
      .then(function () { return new Promise(function (r) { setTimeout(r, 900); }); })
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

  /* "Not them" -- the opposite of decide(). It used to BE decide(), so
     refusing a candidate bound the person to it. */
  function reject(component, c) {
    if (!c || !c.auid) return;
    var who = c.rosterName || c.person || '';
    if (!who) {
      badge('cannot tell which person this row is for', RED);
      return;
    }
    viaProxy('/roster/reject', { name: who, auid: String(c.auid) },
      function () {
        badge(who + ' is not author ' + c.auid, G);
        refresh(component);
      },
      function (msg) { badge(String(msg).slice(0, 60), RED); });
  }
  window.__AAU.reject = reject;

  /* "Show all" under an author's papers, and "Export this college" on the
     roster, were drawn with no handler at all -- they looked live and did
     nothing when pressed. */
  function showPapers(component) {
    var st = window.__AAU.state || {};
    var key = component && component.state ? component.state.author : null;
    var who = (st.authors || []).filter(function (a) { return a.key === key; })[0]
      || (st.authors || [])[0];
    if (!who) return;
    var rows = (st.papers || {})[who.key] || [];
    if (!rows.length) {
      modal({ eyebrow: 'Papers', title: who.name,
              sub: 'No papers for this person in the current window.',
              cancelLabel: 'Close' });
      return;
    }
    var html = rows.map(function (r, i) {
      return '<div style="display:flex;gap:10px;padding:9px 0;border-bottom:'
        + '1px solid #F0F3F1"><div style="width:22px;color:' + META
        + ';font-size:12px">' + (i + 1) + '</div><div style="flex:1;min-width:0">'
        + '<div style="font-size:13.5px;color:' + INK + '">' + esc(r[0] || '(untitled)')
        + '</div><div style="font-size:12px;color:' + META + ';margin-top:2px">'
        + esc(r[1] || '') + ' · ' + esc(r[2] || '') + ' · '
        + esc(r[3] || 0) + ' citations</div></div></div>';
    }).join('');
    var missing = Math.max(0, (who.papers || 0) - rows.length);
    modal({
      eyebrow: 'Papers', title: who.name,
      sub: rows.length + ' of ' + (who.papers || rows.length)
        + ' papers in this window'
        + (missing ? ' · the remaining ' + missing + ' are not published to '
                     + 'this page' : ''),
      html: html, cancelLabel: 'Close',
    });
  }
  window.__AAU.showPapers = showPapers;

  function exportCollege(component) {
    var st = window.__AAU.state || {};
    var col = component && component.state ? component.state.college : null;
    var rows = (st.authors || []).filter(function (a) {
      return !col || a.college === col;
    });
    if (!rows.length) { badge('nothing to export here', RED); return; }
    var head = ['Name', 'College', 'Title', 'Papers', 'h-index', 'Citations',
                'Scopus author id', 'Status'];
    var q = function (v) { return '"' + String(v === undefined || v === null ? '' : v).replace(/"/g, '""') + '"'; };
    var csv = [head.map(q).join(',')].concat(rows.map(function (a) {
      return [a.name, a.college, a.title, a.papers, a.h, a.cites, a.auid, a.tag]
        .map(q).join(',');
    })).join('\r\n');
    var name = (col || 'AAU').replace(/[^A-Za-z0-9]+/g, '_') + '_authors.csv';
    var url = URL.createObjectURL(new Blob(['\ufeff' + csv],
      { type: 'text/csv;charset=utf-8' }));
    var link = document.createElement('a');
    link.href = url; link.download = name;
    document.body.appendChild(link); link.click();
    document.body.removeChild(link);
    setTimeout(function () { URL.revokeObjectURL(url); }, 4000);
    badge('exported ' + rows.length + ' people', G);
  }
  window.__AAU.exportCollege = exportCollege;

  /* ------------------------------------------- the two lazy screens' data */
  /* The corpus is ~950KB and the collaboration file 21KB. Neither is in the
     payload every visitor pays for, so they are fetched the first time their
     screen is opened -- and only once, whatever happens after. */
  var lazy = {};
  // Which stamp the lazy files were read for. `lazy` caches each file for the
  // life of the page, which is right -- until a run publishes a new one. It
  // never was cleared, so after a run the Papers screen and the Collaboration
  // screen went on showing the corpus they had loaded BEFORE it: a 2025-2026
  // run left Papers reporting 4,285 rows from the six-year window. The
  // Dashboard moved and those two did not, which reads as the run half
  // working.
  var lazyStamp = null;
  function dropLazy() {
    lazy = {};
    window.__AAU.lazyDropped = (window.__AAU.lazyDropped || 0) + 1;
  }
  window.__AAU.dropLazy = dropLazy;
  function lazyLoad(name, file, apply, component) {
    if (lazy[name]) return lazy[name];
    // GitHub Pages answers with `Cache-Control: max-age=600`, so for ten
    // minutes after a run the browser and the edge will both hand back the
    // previous file. `no-store` forces the request but does not stop the CDN
    // returning a cached object; a stamp in the query string does, and the
    // stamp is the run's own so it changes exactly when the data does.
    lazy[name] = fetch('data/' + file + '?v='
                         + encodeURIComponent(name === 'net'
                             ? (seenNetTag || stamp()) : stamp()),
                       { cache: 'no-store' })
      .then(function (r) {
        if (!r.ok) throw new Error(file + ' -> HTTP ' + r.status);
        return r.json();
      })
      .then(function (d) {
        apply(d);
        if (component) component.forceUpdate();
        return d;
      })
      .catch(function (e) {
        lazy[name] = null;                       // a failure may be retried
        badge('could not load ' + file, RED);
        throw e;
      });
    return lazy[name];
  }
  window.__AAU.lazyLoad = lazyLoad;

  window.__AAU.needNetwork = function (component) {
    if (!window.__AAU.live) return;              // sample data: leave it alone
    lazyLoad('net', 'network.json', function (d) {
      if (window.__aauNetwork) window.__aauNetwork(d);
    }, component).catch(function () {});
  };
  window.__AAU.needCorpus = function (component) {
    if (!window.__AAU.live) return;
    lazyLoad('corpus', 'papers.json', function (d) {
      if (window.__aauCorpus) window.__aauCorpus(d);
    }, component).catch(function () {});
  };

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
        var text = String(r.result);
        var ok = function (n) {
          refresh(component);
          badge('roster imported', G);
          modal({ eyebrow: 'Roster', title: 'Roster imported',
                  sub: n + ' people read from ' + file.name
                    + '. Scopus records are matched on the next run.',
                  cancelLabel: 'Close' });
        };
        var bad = function (msg) {
          badge('import failed', RED);
          modal({ eyebrow: 'Roster', title: 'That file was not imported',
                  sub: msg, choices: [{ label: 'What does the CSV need?',
                    hint: 'The columns, with an example and a template.',
                    go: function () { csvHelp(); } }],
                  cancelLabel: 'Close' });
        };
        if (window.__AAU.canRun) {
          api('/api/faculty', { csv: text })
            .then(function (res) { ok(res.count || 0); })
            .catch(function (e) { bad(String(e.message || e)); });
        } else {
          viaProxy('/roster/import', { csv: text },
                   function (j) { ok(j.people || 0); }, bad);
        }
      };
      r.readAsText(file);
    };
    f.click();
  }
  window.__AAU.importCsv = importCsv;

  function stop() {
    // window.__AAU.run is set only by the LOCAL engine path, so on the
    // published page this was always null and Stop silently did nothing but
    // flip the button back to "Run now" -- while the GitHub run carried on and
    // the poll kept going, free to yank the reader onto the Dashboard minutes
    // later. Stopping a dispatched Actions run is not something this page can
    // do, so it says so instead of pretending, and it does end the watching.
    if (window.__AAU.run) {
      api('/api/run/stop', { run: window.__AAU.run }).catch(function () {});
      return;
    }
    watchOff();
    modal({
      eyebrow: 'The run',
      title: 'It carries on without this page',
      sub: 'The run is happening on GitHub, not in this tab, so closing or '
        + 'leaving the page does not stop it and nor does this button. This '
        + 'page has stopped watching it; reopen the Dashboard later and the '
        + 'new figures will be there.',
      cancelLabel: 'Close',
    });
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
  window.__AAU.demoNote = function (component) { askRun(component); };
})();
</script>
