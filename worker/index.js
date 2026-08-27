/**
 * AAU Research Tracker — run proxy.
 *
 * GitHub will not start a workflow without a credential, and a credential on a
 * public page is a credential everyone has. So the token lives here, as a
 * Worker secret, and never reaches a browser. A reader proves they are allowed
 * with a passphrase you give them — no GitHub account, nothing installed.
 *
 *   POST /run     { passphrase, years?, scope? }  -> starts a run
 *   GET  /status                                   -> the live run, stage by stage
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

      const r = await fetch(
        `${GH}/repos/${env.REPO}/actions/workflows/${env.WORKFLOW}/dispatches`,
        {
          method: 'POST',
          headers: { ...ghHeaders(env), 'Content-Type': 'application/json' },
          body: JSON.stringify({ ref: 'main', inputs: { years, scope } }),
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

    return cors(json({ error: 'not found' }, 404), origin);
  },
};
