# quill.thegrove.media - consolidated cross-platform views (handoff to Trellis)

**From:** Twain (TheQuill), 2026-08-11
**To:** Trellis (TheGrove) - `thegrove-media` owns the page, so the change is yours to make.
**Ask, in Chris's words:** *"update quill.thegrove.media to pull consolidated analytics for
each video across combined views from + shorts across all three platforms."*

**The short version: the number already exists in the API response and the page ignores it.**
No worker change, no D1 change, no new endpoint. This is a front-end change of roughly six
lines in `quill/js/quill-page.js`, plus one labelling decision that is genuinely Chris's.

This is the reciprocal of your own `docs/quill-web-page-handoff.md` in TheQuill (2026-08-10),
which established the seam: the API and D1 are mine, the page is yours.

## What the page shows today, and why it is wrong

`quill/js/quill-page.js` reads `ep.view_count` in three places. That field is **the main
YouTube video's count only**. Every short, every Instagram Reel, every TikTok is invisible to
the page.

Measured live against the production endpoint, 2026-08-11 11:35 EDT:

| episode | `view_count` (shown today) | `total_view_count` (available, ignored) | ratio |
|---|---:|---:|---:|
| tq01.3-battle-toller | 5 | **2,145** | 429x |
| tq01.2-battle-sakurai | 17 | **1,879** | 111x |
| 007-battle-rabe | 26 | **1,634** | 63x |
| tq02.1-battle-nakamura | 13 | **905** | 70x |
| 004-trial-sewall | 42 | **1,071** | 26x |
| 001-battle-attu | 35 | **815** | 23x |
| 006-battle-latham | 17 | **277** | 16x |
| 002-battle-fromelles | 376 | **1,363** | 4x |
| 003-battle-albuera | 839 | **977** | 1.2x |
| 005-chapters-three-rules | 23 | **23** | 1x |

The page currently tells a visitor that The Quill's best-performing video got 839 views. The
honest number across the surfaces it actually publishes to is 2,145, on a different video.
**"Most Popular" is ranked on the wrong field**, which is why Albuera sits at the top today
and Toller does not appear at all.

`005-chapters-three-rules` showing an unchanged 23 is correct, not a gap: My Lost Chapters
is a format with no shorts and no crossposts, so it has nothing to consolidate.

## The data contract

`GET https://quill-scheduler.chris-ba5.workers.dev/episodes?show=quill` - the same URL the
page already calls at `quill-page.js:4`. No auth, `Access-Control-Allow-Origin: *`.

Every row already carries **`total_view_count`** alongside `view_count`. Definition, from
`worker/src/index.js:600-620` in the TheQuill repo:

```
total_view_count = quill_episodes.view_count            (the main YouTube video)
                 + SUM(social_assets.view_count)         (every OTHER asset for that video)
```

The sum spans all three platforms and every asset kind: YouTube shorts, Instagram Reels,
the Instagram full-video Reel, the Instagram announce post, and TikTok Reels. It
**deliberately excludes** the `(platform='youtube', kind='video')` social row, because
`quill_episodes.view_count` already is that same video's count refreshed independently, and
summing both double-counts the main video. That exclusion is live-verified and load-bearing;
it is not an oversight you should "fix" from the page side.

**Null semantics are unchanged, which matters for your honest-when-empty rule.** When a
video has no social rows at all, the CASE falls through to bare `e.view_count` including its
null-ness. So `total_view_count` is null in exactly the cases `view_count` is null today, and
your "drop the Most Popular section rather than mislabel newest-first as most-popular" guard
keeps working with no change to its logic.

## The change

All in `quill/js/quill-page.js`. Line numbers are against the current file (289 lines,
`79a9007`).

Use `ep.total_view_count ?? ep.view_count` at every site rather than the bare field, so the
page degrades to today's behaviour rather than blanking if the field ever disappears from the
response.

| line | function | today | change to |
|---|---|---|---|
| 94 | `renderLatestCard` | `formatViews(ep.view_count)` | `formatViews(ep.total_view_count ?? ep.view_count)` |
| 129 | `renderPopular` | `formatViews(ep.view_count)` | same |
| 169 | `renderList` | `formatViews(ep.view_count)` | same |
| 270-272 | `hasViewData` guard | tests `ep.view_count` | test the same coalesced value |
| 274-276 | popular sort | `(b.view_count ?? -1) - (a.view_count ?? -1)` | sort on the coalesced value |

`formatViews` itself (line 16) needs no change. Its `>= 1000` branch already renders
"2.1K views", which is where most episodes land once consolidated - today almost none of them
reach it, which is part of why the page reads as quieter than the channel is.

Nothing else in the row shape changes, so `_headers`, the CSP, the filter chips and the
two-image rule are all untouched.

## The one decision that is Chris's, not ours

**What the label should say.** A card that reads "2,145 views" and links to a YouTube video
with 5 views is accurate about the channel and potentially misleading about the link. Three
options, in the order I would recommend them:

1. **Keep the bare word "views" and add one line of context** somewhere on the page - a
   footnote near the Most Popular heading, something like "views across YouTube, Instagram
   and TikTok". Cheapest, and it keeps the card copy short, which is what the layout wants.
2. **Change the per-card label** to "views everywhere" or "total views". Honest at the point
   of the number, costs horizontal space in a row that is already tight.
3. **Show both** - the total on the card, the YouTube count on hover or in the row meta.
   Most informative, most work, and probably more numbers than the page wants.

I recommend option 1. The page's own established ethos is honest-when-empty rather than
maximally-annotated, and one contextual line serves that better than lengthening every card.

**Ranking "Most Popular" on the total is the right call and I do not think it needs a
separate decision** - a "most popular" claim that ignores 95% of a video's audience is the
less defensible of the two.

## What is NOT available, so you do not go looking for it

**There is no per-platform breakdown on any endpoint.** `/episodes` returns the aggregate
only. The underlying `social_assets` table has the full per-platform, per-asset detail
(`platform`, `kind`, `external_id`, `view_count`), but nothing exposes it over HTTP - the
only GET routes on the worker are `/episodes` and `/events`.

So if Chris wants a breakdown in the UI (a split by platform, a per-short list, a sparkline),
**that is a worker change in TheQuill, not a page change here.** Send it back to me rather
than trying to derive it. The aggregate is all the page can currently render, and it is what
the ask above describes.

## Freshness, and the one caveat worth telling a visitor nothing about

`total_view_count` is refreshed by a launchd job on Chris's machine,
`com.quill.social-metrics`, at **22:00 local, daily** (verified against the plist, not the
docs). It runs `scripts/social_metrics.py` in TheQuill, which discovers every published
asset, fetches counts from the three platforms, and POSTs them to
`/social-metrics/upsert`.

Two consequences for the page:

- **The number can be up to ~24h stale**, same as `view_count` is today. No change in
  character, so no new copy is needed.
- **It only refreshes when that one Mac is awake.** Single-host coupling is a documented,
  accepted choice in TheQuill, not a bug. The page must not assert a "last updated" time it
  cannot actually verify - the row carries no timestamp for the total.

Per-platform fetches are fail-soft: if the Meta token expires one night, Instagram counts are
simply absent from that run rather than zeroed, and the total drops for a day and recovers.
The page should not try to detect or explain that.

## Provenance of the numbers, if you need to defend one

As of 2026-08-11, every released episode also carries a manifest at
`{video_dir}/reports/published-surfaces.json` in the TheQuill repo: ten slots per video
(the video plus two shorts across YouTube, Instagram and TikTok, plus the Instagram announce
post), each with its external id and a state of `published` / `pending` / `missing` /
`absent`. If a total ever looks wrong for one episode, that file names every surface that
contributes and every one that does not, with a reason. Ask me and I will read it; you should
not need to.

## Checklist

- [ ] Five edits in `quill/js/quill-page.js` per the table above, all using
      `ep.total_view_count ?? ep.view_count`
- [ ] Confirm Most Popular re-ranks - Toller and Sakurai should displace Albuera
- [ ] Chris's call on the label (recommendation: option 1, one contextual line)
- [ ] Verify the empty-state guard still drops the section when every total is null
      (unchanged logic, but it is the one behaviour the page is on record about)
- [ ] No change needed to `_headers`, the CSP, the filter chips, or the artwork contract
