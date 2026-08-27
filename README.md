# AAU Research Tracker — web build

The Al Ain University Research Tracker interface, as a website. Open
`docs/index.html` in any browser: no server, no build step, no internet.

## What is here

    docs/index.html      The whole app in ONE self-contained file (595 KB).
                         Fonts and images are inlined. This is what gets hosted.
    docs/robots.txt      Keeps the page out of search engines.
    docs/artifact.html   The same page with the outer <html>/<head>/<body>
                         removed, for hosts that supply their own skeleton.

    source/              The authored source, for whoever rebuilds this properly:
      AAU Research Tracker UI.dc.html   template first, logic class at the bottom
      support.js                        the runtime that renders it
      assets/                           AAU logo, Scopus marks
      DESIGN-NOTES.md                   design tokens, animations, screen list

## The seven screens

1. **Welcome** — full-bleed AAU green, one button into the app.
2. **Dashboard** — headline figures, the six-stage run panel with live progress,
   findings in plain sentences, papers by college, and what changed since last run.
3. **Roster** — eight college cards, then that college's authors. The review
   queue (names needing a decision) sits behind the red button.
4. **Authors** — searchable list of every person, with a detail panel.
5. **Exports** — workbook, slide deck, chart pack.
6. **Schedule** — weekly toggle, day picker, next four runs, health checks.
7. **Workflow** — the animated flowchart: two sources, name matching, two
   collection routes, the affiliation gate as a yes/no diamond, and the outputs.

## This is the interface, not the engine

Every figure on screen is from run `20260827-010252`. The buttons move between
screens and drive the animations; they do not call Scopus. The working engine is
the separate `AAU_Research_Tracker` project — this is the face that goes on it.

## Hosting

See `DEPLOY.md`. The short version: it is one static folder, so it works
unchanged on GitHub Pages, Cloudflare Pages, Netlify, Vercel, or any Apache or
nginx server — copy `docs/` to the web root.

## Editing the built file

`docs/index.html` is a self-unpacking bundle: the real page is a JSON string on
**line 382**. Edit the readable source in `source/` instead. If you must edit
the bundle directly, re-encode exactly this way or the page will not open:

```python
json.dumps(text, ensure_ascii=False).replace("</", "<\\u002F")
```

`ensure_ascii=False` keeps em-dashes raw; the `</` escape stops an inner
`</script>` from closing the host script tag early. Line 370 is the asset
manifest — 502 KB of base64 fonts and images. Leave it alone.

> `docs/` is the website. GitHub Pages is configured to serve that folder, which
> is why it is named `docs` rather than `site` — the legacy Pages builder only
> accepts the repository root or `/docs`, and `/docs` keeps the built page from
> mixing with the source.
