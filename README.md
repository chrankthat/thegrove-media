# thegrove.media

Static landing page for TheGrove Media (Human in the Loop, The Quill, The Little Feather).
Zero backend, zero build step. Cloudflare Pages serves this repo's root directly.

> **`index.html` is generated. Never edit it directly.** It is built from
> `content/channels.json` + `content/icons.json` + `css/` by `scripts/render.py`.
> After changing any of those, run `python3 scripts/render.py` and commit the
> regenerated `index.html` in the same commit. A hand edit to `index.html` will
> be silently destroyed the next time the generator runs, and
> `scripts/tests/test_render_page.py::test_committed_index_html_is_not_stale`
> will fail in the meantime.

## Content model

All rendered content lives in `content/channels.json`. Nothing is hardcoded in
`index.html` except the page shell (masthead/about/footer scaffolding).

## Editing content

1. Edit `content/channels.json` (and `content/icons.json` if adding a new
   listen/social platform).
2. Regenerate `index.html`:
   ```
   python3 scripts/render.py
   ```
3. Commit both the JSON and the regenerated `index.html` together. A push to
   `main` auto-deploys via Cloudflare Pages - there is no build step, so the
   committed `index.html` IS what ships.

## Adding a fourth show

Add an entry to `channels.json`'s `shows` array with a unique `id` and
`order`, plus a mark image in `assets/marks/`. `scripts/render.py`'s
`render_show()` is fully data-driven - no code change is needed for a normal
show addition.

## Verification

- `python3 -m unittest discover scripts/tests` - content shape + generator
  unit tests.
- `python3 scripts/check_links.py` - every external link resolves.
- `python3 scripts/verify_render.py` - Playwright rendering, no-JS, and
  console-error checks against a local serve.
- `python3 scripts/verify_deploy.py` - confirms the live site's content-hash
  meta tag matches the local `content/channels.json`, after a push.

## Governance

Cross-domain ad191 danger trigger fires on this repo's existence - see
`wiki/decisions/ad200.md` in `TheGrove`. Sprint artifacts:
`TheGrove/domains/site/thegrove-media/v1.1.0/`.
