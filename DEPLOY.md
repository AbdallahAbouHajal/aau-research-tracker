# Hosting this

The whole website is the `docs/` folder. It is three files and no build step,
so it runs unchanged on anything that can serve static files.

## Where it is now

    https://abdallahabouhajal.github.io/aau-research-tracker/

Served by GitHub Pages from the `docs/` folder of the `main` branch. Free, HTTPS,
no expiry. Anyone with the link can open it; no account is needed.

To publish a change: edit, commit, `git push`. The site updates in under a minute.

## Moving it to Al Ain University's own servers

Copy the **contents** of `docs/` into the web root. That is all — there is no
database, no backend, no environment file, and nothing to configure.

**Apache** — drop the files in `/var/www/html/`. Nothing else to do.

**nginx**

    server {
      listen 443 ssl;
      server_name tracker.aau.ac.ae;
      root /var/www/aau-tracker;
      index index.html;
    }

**IIS** — copy into the site folder and set `index.html` as the default document.

**Any other free host** — the same folder works as-is on Cloudflare Pages,
Netlify, Vercel and Render. None of them need a build command; set the publish
directory to `docs` and leave the build command empty.

## Putting it behind a login

`docs/robots.txt` and the `noindex` meta tag keep the page out of search
engines, but the URL itself is open to anyone who has it. If it needs to be
genuinely restricted:

- **Cloudflare Access** — free for a small number of users, sits in front of the
  site and asks for an AAU email before letting anyone through. No code change.
- **nginx basic auth** — two lines, if AAU hosts it themselves:

      auth_basic "AAU Research Tracker";
      auth_basic_user_file /etc/nginx/.htpasswd;

- **A university SSO proxy** — the page is static, so any reverse proxy in front
  of it works without touching the app.

## Things that will break it

- **Renaming `index.html`.** Every host looks for that name by default.
- **Serving it through a CDN that "optimises" or minifies HTML.** This file must
  be served byte-for-byte: it carries a JSON payload that a minifier corrupts.
- **Jekyll.** GitHub Pages runs it by default and it mangles some paths. The
  empty `docs/.nojekyll` file in this repo turns it off. Keep that file.
- **A CSP that forbids `data:` fonts or inline scripts.** The page inlines both
  on purpose so it works offline. If AAU has a strict CSP, allow
  `script-src 'unsafe-inline'` and `font-src data:` for this path, or unpack the
  bundle into ordinary files first.
- **Editing `docs/index.html` by hand.** See the warning at the end of README.md.
