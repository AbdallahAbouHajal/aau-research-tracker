# AAU Research Tracker — site build checkpoint

## Status
- [x] zip extracted to `_extracted/handoff/`
- [x] two removals applied to the bundle payload (welcome chips, Powered-by badge)
- [x] rendered and verified in Chrome at 1440x960: welcome, dashboard, roster, workflow
- [x] zero app console errors (the 8 seen are a crypto-wallet Chrome extension)
- [ ] hosting chosen + deployed
- [ ] handoff docs written

## The one non-obvious thing about editing this file
`site/index.html` is a self-unpacking bundle. The real page is a JSON string on
**line 382**, inside `<script type="__bundler/template">`. To edit it you must
re-encode the way the bundler does, or the page dies with
"Error unpacking: Unterminated string in JSON":

    json.dumps(s, ensure_ascii=False).replace("</", "<\\u002F")

`ensure_ascii=False` matters (em-dashes ship raw, not `—`) and the `</`
escape matters (an inner `</script>` would close the host script tag early).
Both were verified byte-identical against the untouched original before editing.
Line 370 is the asset manifest (502 KB of base64 fonts and images) — leave it alone.

## Edits made (exactly what the user asked for, nothing else)
1. `welcomeChips` — dropped `1,336 papers in the census` and
   `511 authors, 161 on the roster`; kept `8 colleges covered`.
2. Removed the `Powered by [Elsevier Scopus]` badge from the welcome screen.
   NOTE: a second identical lockup labelled **Data sources** sits on the Workflow
   screen. That one is real attribution and was deliberately kept.
3. Added `<title>AAU Research Tracker</title>` (the bundle had none) and
   `<meta name="robots" content="noindex, nofollow">`.

## Known cosmetic artifact (not changed — needs the user's call)
The fake window chrome reads **"AAU Research Tracker — localhost:8765"**. It is
part of the Claude Design mockup. On a real hosted URL it reads as a leftover.
