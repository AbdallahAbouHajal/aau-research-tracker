/**
 * AAU Research Tracker — run proxy.
 *
 * GitHub will not start a workflow without a credential, and a credential on a
 * public page is a credential everyone has. So the token lives here, as a
 * Worker secret, and never reaches a browser. A reader proves they are allowed
 * with a passphrase you give them — no GitHub account, nothing installed.
 *
 *   POST /run            { passphrase, years?, scope?, date_from?, date_to? }
 *   POST /roster/add     { passphrase, name, college, title?, url? }
 *   POST /roster/import  { passphrase, csv }
 *   POST /roster/remove  { passphrase, name }
 *   GET  /status                                    -> the live run, stage by stage
 *
 * The roster endpoints commit to the repository, so the passphrase can change
 * who counts as faculty. That is deliberate and was asked for. What it cannot
 * do is anything else: it appends a person or replaces the roster, both onto a
 * file whose every previous version is in git history, and it touches no other
 * path. Scopus resolution is NOT done here -- the next run finds the new
 * person through their aau.ac.ae page, the same route the engine already uses.
 *
 * /status needs no passphrase: it only reports what the workflow is doing, and
 * the page has to poll it to move the progress bar. It cannot start anything.
 *
 * Secrets (wrangler secret put …):
 *   GITHUB_TOKEN     fine-grained PAT, this repo only, Actions: Read and write
 *   RUN_PASSPHRASE   whatever you tell the professor
 * Vars (wrangler.toml):
 *   REPO, WORKFLOW, ALLOWED_ORIGIN
 */

const GH = 'https://api.github.com';

// AAU's eight. A college outside this list is a typo, not a new college.
const COLLEGES = [
  'College of Engineering', 'College of Pharmacy', 'College of Law',
  'College of Education, Humanities and Social Sciences',
  'College of Business', 'College of Communication and Media',
  'College of Dentistry', 'College of Nursing',
];

/** Minimal CSV -> roster rows. Quoted fields with commas are handled; anything
 *  without a name and a college is dropped rather than guessed at. */
function parseCsv(text) {
  const lines = String(text).replace(/\r\n?/g, '\n').split('\n').filter((l) => l.trim());
  if (lines.length < 2) return [];
  const cut = (line) => {
    const out = []; let cur = '', q = false;
    for (let i = 0; i < line.length; i++) {
      const c = line[i];
      if (q) {
        if (c === '"' && line[i + 1] === '"') { cur += '"'; i++; }
        else if (c === '"') q = false;
        else cur += c;
      } else if (c === '"') q = true;
      else if (c === ',') { out.push(cur); cur = ''; }
      else cur += c;
    }
    out.push(cur);
    return out.map((v) => v.trim());
  };
  const head = cut(lines[0]).map((h) => h.toLowerCase().replace(/^﻿/, ''));
  const at = (r, n) => { const i = head.indexOf(n); return i < 0 ? '' : (r[i] || ''); };
  const rows = [];
  const seen = new Set();
  for (let i = 1; i < lines.length; i++) {
    const r = cut(lines[i]);
    const name = at(r, 'name').replace(/\s*,?\s*\b(Ph\.?\s?D|M\.?\s?Sc|MBA|MD|DDS)\.?\s*$/i, '').trim();
    const college = snapCollege(at(r, 'college'));
    if (!name || !college) continue;
    const k = name.toLowerCase().replace(/[^a-z ]/g, '');
    if (seen.has(k)) continue;
    seen.add(k);
    rows.push({
      name: name.slice(0, 120), college,
      title: at(r, 'title').slice(0, 120),
      email: at(r, 'email').slice(0, 160),
      department: at(r, 'department').slice(0, 120),
      profile_url: at(r, 'profile_url').slice(0, 300),
      staff_type: /admin/i.test(at(r, 'staff_type')) ? 'administrative' : 'academic',
      is_academic: !/admin/i.test(at(r, 'staff_type')),
      colleges: [college],
      scopus_auid: '', auid_tier: '', auid_candidates: [],
    });
  }
  return rows;
}

/** "engineering", "Eng.", "College of Engineering" -> the same college. */
function snapCollege(raw) {
  const t = String(raw || '').toLowerCase();
  if (!t.trim()) return '';
  const map = [['engineer', 0], ['pharmac', 1], ['law', 2], ['education', 3],
    ['humanities', 3], ['social', 3], ['business', 4], ['communicat', 5],
    ['media', 5], ['dentist', 6], ['nurs', 7]];
  for (const [k, i] of map) if (t.includes(k)) return COLLEGES[i];
  return '';
}

function cors(res, origin) {
  const h = new Headers(res.headers);
  h.set('Access-Control-Allow-Origin', origin || '*');
  h.set('Access-Control-Allow-Headers', 'Content-Type');
  h.set('Access-Control-Allow-Methods', 'GET, POST, OPTIONS');
  h.set('Vary', 'Origin');
  return new Response(res.body, { status: res.status, headers: h });
}

function json(obj, status = 200) {
  return new Response(JSON.stringify(obj), {
    status,
    headers: { 'Content-Type': 'application/json', 'Cache-Control': 'no-store' },
  });
}

/** Constant-time compare, so a wrong passphrase cannot be found one character
 *  at a time by measuring how long the answer took. */
function sameSecret(a, b) {
  const x = new TextEncoder().encode(String(a || ''));
  const y = new TextEncoder().encode(String(b || ''));
  if (x.length !== y.length) return false;
  let diff = 0;
  for (let i = 0; i < x.length; i++) diff |= x[i] ^ y[i];
  return diff === 0;
}

function ghHeaders(env) {
  return {
    Authorization: `Bearer ${env.GITHUB_TOKEN}`,
    Accept: 'application/vnd.github+json',
    'X-GitHub-Api-Version': '2022-11-28',
    'User-Agent': 'aau-research-tracker-worker',
  };
}

export default {
  async fetch(request, env) {
    const origin = env.ALLOWED_ORIGIN || '*';
    if (request.method === 'OPTIONS') {
      return cors(new Response(null, { status: 204 }), origin);
    }

    const url = new URL(request.url);
    const path = url.pathname.replace(/\/+$/, '') || '/';

    // ---- what the run is doing. No secret: it starts nothing. -------------
    if (path === '/status' && request.method === 'GET') {
      try {
        const runs = await fetch(
          `${GH}/repos/${env.REPO}/actions/workflows/${env.WORKFLOW}/runs?per_page=1`,
          { headers: ghHeaders(env) },
        ).then((r) => r.json());
        const run = (runs.workflow_runs || [])[0];
        if (!run) return cors(json({ running: false, run: null }), origin);

        const jobs = await fetch(`${GH}/repos/${env.REPO}/actions/runs/${run.id}/jobs`, {
          headers: ghHeaders(env),
        }).then((r) => r.json());
        const job = (jobs.jobs || [])[0] || {};
        // Only the six census steps: the page draws six stages, and checkout
        // and setup-python are not stages a reader has any use for.
        const steps = (job.steps || []).map((s) => ({
          name: s.name,
          status: s.status,
          conclusion: s.conclusion,
        }));
        return cors(json({
          running: run.status !== 'completed',
          status: run.status,
          conclusion: run.conclusion,
          started: run.run_started_at,
          url: run.html_url,
          steps,
        }), origin);
      } catch (e) {
        return cors(json({ error: String(e && e.message || e) }, 502), origin);
      }
    }

    // ---- start a run ------------------------------------------------------
    if (path === '/run' && request.method === 'POST') {
      let body = {};
      try { body = await request.json(); } catch (e) { body = {}; }

      if (!env.RUN_PASSPHRASE) {
        return cors(json({ error: 'the proxy has no passphrase set' }, 500), origin);
      }
      if (!sameSecret(body.passphrase, env.RUN_PASSPHRASE)) {
        // Deliberately slow and vague: no hint about which part was wrong.
        await new Promise((r) => setTimeout(r, 600));
        return cors(json({ error: 'That passphrase is not right.' }, 403), origin);
      }

      // Someone with the passphrase should not be able to queue fifty runs.
      // One at a time is the whole need here, and the workflow's own
      // concurrency group would serialise them anyway.
      try {
        const cur = await fetch(
          `${GH}/repos/${env.REPO}/actions/workflows/${env.WORKFLOW}/runs?per_page=1`,
          { headers: ghHeaders(env) },
        ).then((r) => r.json());
        const last = (cur.workflow_runs || [])[0];
        if (last && last.status !== 'completed') {
          return cors(json({
            started: false,
            already: true,
            message: 'A run is already going. Watch it rather than starting another.',
            url: last.html_url,
          }), origin);
        }
      } catch (e) { /* if the check fails, let the dispatch decide */ }

      const years = String(body.years || '').replace(/[^0-9,]/g, '').slice(0, 24);
      const scope = body.scope === 'current' ? 'current' : 'compare';
      // YYYY-MM-DD or nothing. Anything else is dropped rather than passed on.
      const day = (v) => (/^\d{4}-\d{2}-\d{2}$/.test(String(v || '')) ? String(v) : '');
      const date_from = day(body.date_from);
      const date_to = day(body.date_to);

      const r = await fetch(
        `${GH}/repos/${env.REPO}/actions/workflows/${env.WORKFLOW}/dispatches`,
        {
          method: 'POST',
          headers: { ...ghHeaders(env), 'Content-Type': 'application/json' },
          body: JSON.stringify({ ref: 'main',
            inputs: { years, scope, date_from, date_to } }),
        },
      );
      if (r.status === 204) return cors(json({ started: true }), origin);
      const detail = await r.text();
      return cors(json({
        started: false,
        error: 'GitHub refused to start it',
        status: r.status,
        detail: detail.slice(0, 300),
      }, 502), origin);
    }

    // ---- roster edits ------------------------------------------------------
    if (path.startsWith('/roster/') && request.method === 'POST') {
      let body = {};
      try { body = await request.json(); } catch (e) { body = {}; }
      if (!env.RUN_PASSPHRASE || !sameSecret(body.passphrase, env.RUN_PASSPHRASE)) {
        await new Promise((r) => setTimeout(r, 600));
        return cors(json({ error: 'That passphrase is not right.' }, 403), origin);
      }

      const FILE = 'engine/data/roster.json';
      const get = await fetch(
        `${GH}/repos/${env.REPO}/contents/${FILE}?ref=main`,
        { headers: ghHeaders(env) },
      );
      if (!get.ok) {
        return cors(json({ error: 'could not read the roster' }, 502), origin);
      }
      const meta = await get.json();
      let blob;
      try {
        blob = JSON.parse(decodeURIComponent(escape(atob(meta.content.replace(/\n/g, '')))));
      } catch (e) {
        return cors(json({ error: 'the roster on the repo is unreadable' }, 500), origin);
      }
      const people = blob.people || [];
      const norm = (v) => String(v || '').replace(/\s+/g, ' ').trim();
      const key = (v) => norm(v).toLowerCase().replace(/[^a-z ]/g, '');
      let message = '';

      if (path === '/roster/add') {
        const name = norm(body.name).slice(0, 120);
        const college = COLLEGES.includes(norm(body.college))
          ? norm(body.college) : snapCollege(body.college);
        if (!name) {
          return cors(json({ error: 'a name is needed' }, 400), origin);
        }
        if (!college) {
          return cors(json({
            error: norm(body.college)
              ? ('"' + norm(body.college) + '" is not one of AAU\'s eight colleges')
              : 'a college is needed',
          }, 400), origin);
        }
        if (people.some((p) => key(p.name) === key(name))) {
          return cors(json({ added: false, error: name + ' is already on the roster.' }, 409), origin);
        }
        const url = norm(body.url).slice(0, 300);
        if (url && !/^https:\/\/(www\.)?aau\.ac\.ae\//i.test(url)) {
          return cors(json({ error: 'the profile link must be on aau.ac.ae' }, 400), origin);
        }
        people.push({
          name, college,
          title: norm(body.title).slice(0, 120),
          profile_url: url,
          email: '', department: '',
          staff_type: 'academic', is_academic: true,
          colleges: [college],
          scopus_auid: '', auid_tier: '', auid_candidates: [],
          added_from_page: true,
        });
        message = 'Roster: add ' + name + ' (' + college + ')';
      } else if (path === '/roster/import') {
        const csv = String(body.csv || '');
        if (csv.length > 400000) {
          return cors(json({ error: 'that file is too big' }, 413), origin);
        }
        const rows = parseCsv(csv);
        if (!rows.length) {
          return cors(json({ error: 'no rows with a name and a college' }, 400), origin);
        }
        if (rows.length > 2000) {
          return cors(json({ error: 'that is more people than AAU has' }, 400), origin);
        }
        blob.people = rows;
        blob.replaced_from_page = new Date().toISOString();
        message = 'Roster: import ' + rows.length + ' people';
      } else if (path === '/roster/dismiss') {
        const name = norm(body.name).slice(0, 120);
        if (!name) return cors(json({ error: 'which person?' }, 400), origin);
        const F2 = 'engine/data/not_faculty.json';
        const g2 = await fetch(`${GH}/repos/${env.REPO}/contents/${F2}?ref=main`,
          { headers: ghHeaders(env) });
        let list = [], sha2 = undefined;
        if (g2.ok) {
          const m2 = await g2.json();
          sha2 = m2.sha;
          try {
            list = JSON.parse(decodeURIComponent(escape(atob(m2.content.replace(/\n/g, '')))));
          } catch (e) { list = []; }
        }
        if (!Array.isArray(list)) list = [];
        if (!list.some((n) => key(n) === key(name))) list.push(name);
        const put2 = await fetch(`${GH}/repos/${env.REPO}/contents/${F2}`, {
          method: 'PUT',
          headers: { ...ghHeaders(env), 'Content-Type': 'application/json' },
          body: JSON.stringify({
            message: 'Roster: ' + name + ' is not faculty\n\nMade from the published page.',
            content: btoa(unescape(encodeURIComponent(JSON.stringify(list, null, 1)))),
            sha: sha2,
            branch: 'main',
          }),
        });
        if (!put2.ok) {
          const t2 = await put2.text();
          return cors(json({ error: 'the change was refused', detail: t2.slice(0, 240) }, 502), origin);
        }
        return cors(json({ ok: true, dismissed: name, total: list.length }), origin);
      } else if (path === '/roster/remove') {
        const name = norm(body.name).slice(0, 120);
        if (!name) return cors(json({ error: 'which person?' }, 400), origin);
        const before = people.length;
        const kept = people.filter((p) => key(p.name) !== key(name));
        if (kept.length === before) {
          return cors(json({ error: name + ' is not on the roster.' }, 404), origin);
        }
        if (kept.length === 0) {
          return cors(json({ error: 'that would empty the roster' }, 400), origin);
        }
        blob.people = kept;
        people.length = 0;
        kept.forEach((x) => people.push(x));
        message = 'Roster: remove ' + name;
      } else {
        return cors(json({ error: 'not found' }, 404), origin);
      }

      blob.people = blob.people || people;
      if (path === '/roster/add') blob.people = people;
      const put = await fetch(`${GH}/repos/${env.REPO}/contents/${FILE}`, {
        method: 'PUT',
        headers: { ...ghHeaders(env), 'Content-Type': 'application/json' },
        body: JSON.stringify({
          message: message + '\n\nMade from the published page.',
          content: btoa(unescape(encodeURIComponent(JSON.stringify(blob, null, 1)))),
          sha: meta.sha,
          branch: 'main',
        }),
      });
      if (!put.ok) {
        const t = await put.text();
        return cors(json({ error: 'the change was refused', detail: t.slice(0, 240) }, 502), origin);
      }
      return cors(json({ ok: true, people: blob.people.length, message }), origin);
    }

    return cors(json({ error: 'not found' }, 404), origin);
  },
};
