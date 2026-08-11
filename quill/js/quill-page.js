(function () {
  "use strict";

  const API_URL = "https://quill-scheduler.chris-ba5.workers.dev/episodes?show=quill";

  const FORMAT_LABEL = { battle: "Battle", trial: "Trial", chapters: "My Lost Chapters" };

  // RULING-2: every value that reaches innerHTML - text node or attribute -
  // passes through esc() first. See task-13-report.md for the audited site list.
  function esc(s) {
    return String(s).replace(/[&<>"']/g, function (c) {
      return {'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c];
    });
  }

  function formatViews(n) {
    if (n === null || n === undefined) return "";
    if (n >= 1000) return (n / 1000).toFixed(n % 1000 === 0 ? 0 : 1) + "K views";
    return n + " views";
  }

  // THE VIEW NUMBER IS CROSS-PLATFORM, NOT YOUTUBE.
  //
  // `view_count` is the main YouTube video alone. `total_view_count` adds
  // SUM(social_assets.view_count) - every other published asset for that
  // story: YouTube shorts, Instagram Reels, the Instagram announce post, and
  // TikTok. It deliberately excludes the (youtube, video) social row, because
  // `view_count` already IS that video's count and summing both double-counts
  // it. That exclusion is load-bearing and lives in TheQuill's
  // worker/src/index.js:600-620 - do not "fix" it from this side.
  //
  // The gap is not cosmetic: at time of writing Toller reads 5 on YouTube and
  // 2,145 everywhere, and ranking Most Popular on the YouTube field alone put
  // the wrong story first.
  //
  // Coalesced rather than read bare so the page degrades to today's
  // YouTube-only behaviour instead of blanking if the field ever leaves the
  // response. Null semantics are identical: when a story has no social rows
  // the API falls through to `view_count` including its null-ness, so the
  // empty-state guard below keeps working unchanged.
  function totalViews(ep) {
    return ep.total_view_count ?? ep.view_count;
  }

  // The three marks are a UNIT on the number - they say "this count is
  // measured across YouTube, Instagram and TikTok", the same way the word
  // "views" says what is being counted. They are NOT a claim that this
  // particular story was published to all three: the API returns the
  // aggregate only, with no per-platform breakdown, so a presence claim is
  // not something this page can honestly make. My Lost Chapters has no shorts
  // and no crossposts, and its total legitimately equals its YouTube count.
  //
  // aria-hidden on the marks, with the meaning carried in sr-only text, so a
  // screen reader hears "2.1K views across YouTube, Instagram and TikTok"
  // rather than three unlabelled graphics.
  const PLATFORM_ICON_IDS = ["icon-yt", "icon-ig", "icon-tt"];

  function platformMarksHtml() {
    return '<span class="views-platforms" aria-hidden="true">' +
      PLATFORM_ICON_IDS.map(function (id) {
        return '<svg class="platform-icon" viewBox="0 0 24 24" role="img">' +
          '<use href="#' + id + '"></use></svg>';
      }).join("") +
      "</span>" +
      '<span class="sr-only"> across YouTube, Instagram and TikTok</span>';
  }

  function formatDate(iso) {
    const d = new Date(iso);
    return d.toLocaleDateString("en-US", { month: "short", day: "numeric", year: "numeric" });
  }

  // Formats never linked a fourth show format to this page; fall back to the
  // raw value rather than rendering the literal string "undefined".
  function formatLabel(fmt) {
    return Object.prototype.hasOwnProperty.call(FORMAT_LABEL, fmt) ? FORMAT_LABEL[fmt] : fmt;
  }

  function watchUrl(videoId) {
    return "https://www.youtube.com/watch?v=" + encodeURIComponent(videoId);
  }

  // Published YouTube titles carry two suffixes that earn their keep on YouTube
  // and only cost readability here: a "(Human-Written)" provenance tag and a
  // " | <Series>" trailer. This page shows the episode title alone.
  //
  // Deliberately NOT "strip any trailing parenthetical". One real title is
  // "The Day My Son Became a Boy (Not the Way You Think)", where the
  // parenthetical IS the title - a generic rule would silently gut it. Only the
  // provenance tag is named, so an unrecognised parenthetical always survives.
  //
  // DISPLAY-ONLY. The D1 row, the API response, and the YouTube title itself
  // are untouched; those suffixes are load-bearing for search on YouTube and
  // belong to TheQuill (see docs/quill-web-page-handoff.md, "the seam").
  const PROVENANCE_TAG = /\s*\(\s*human[\s-]*written\s*\)\s*$/i;

  function displayTitle(raw) {
    const full = String(raw === null || raw === undefined ? "" : raw);
    const stripped = full.split("|")[0].replace(PROVENANCE_TAG, "").trim();
    // A title that is nothing BUT suffix would render an empty heading. Falling
    // back to the raw string keeps the card honest instead of blank.
    return stripped || full.trim();
  }

  // The two images per episode are NOT crops of each other. `thumbnail_url` is
  // 3000x3000 square podcast cover art; the YouTube still is a separately
  // composed 16:9 frame. The hero renders 16:9, so it must use the YouTube
  // still - forcing the square art into a 16:9 box is exactly the stretch this
  // revision removes. Square slots (Most Popular, All Stories) keep the cover
  // art. Requires https://i.ytimg.com in the _headers CSP img-src.
  function youtubeThumb(videoId) {
    return "https://i.ytimg.com/vi/" + encodeURIComponent(videoId) + "/maxresdefault.jpg";
  }

  function thumbHtml(src, wrapClass) {
    const inner = src
      ? '<img src="' + esc(src) + '" alt="" loading="lazy">'
      : '<div class="placeholder-thumb"></div>';
    return '<div class="' + wrapClass + '">' + inner + "</div>";
  }

  function cornerMarkup() {
    const tpl = document.getElementById("corner-svg-template").innerHTML;
    return ["tl", "tr", "bl", "br"].map(function (pos) {
      return '<span class="corner corner-' + pos + '" aria-hidden="true">' + tpl + "</span>";
    }).join("");
  }

  function pillHtml(fmt) {
    return '<span class="format-pill" data-format="' + esc(fmt) + '">' +
      esc(formatLabel(fmt)) + "</span>";
  }

  function renderLatestCard(ep) {
    const slot = document.getElementById("latest-slot");
    if (!ep) {
      document.getElementById("latest-section").remove();
      return;
    }
    const viewsText = formatViews(totalViews(ep));
    const viewsBlock = viewsText
      ? '<span class="hero-views"><span class="ember-dot" aria-hidden="true"></span>' +
          esc(viewsText) + platformMarksHtml() + "</span>"
      : "<span></span>";

    const card =
      '<article id="latest-card" class="frame">' +
        cornerMarkup() +
        '<div class="latest-card-inner">' +
          thumbHtml(ep.video_id ? youtubeThumb(ep.video_id) : null, "hero-thumb-wrap") +
          '<div class="hero-meta-row">' +
            pillHtml(ep.format) +
            '<span class="hero-context">' + esc(formatDate(ep.published_at)) + "</span>" +
          "</div>" +
          '<h3 class="font-display hero-title">' + esc(ep.title) + "</h3>" +
          '<div class="hero-views-row">' +
            viewsBlock +
            '<span class="tap-arrow" aria-hidden="true">&#8250;</span>' +
          "</div>" +
        "</div>" +
      "</article>";

    // The whole card is the link. Without a video_id there is nothing to link
    // to, so the card renders unwrapped rather than as a dead anchor.
    slot.innerHTML = ep.video_id
      ? '<a class="card-link" href="' + esc(watchUrl(ep.video_id)) + '" target="_blank" ' +
        'rel="noopener noreferrer" aria-label="Watch ' + esc(ep.title) + ' on YouTube">' +
        card + "</a>"
      : card;
  }

  function renderPopular(episodes) {
    const wrap = document.getElementById("popular-scroll");
    episodes.forEach(function (ep) {
      const viewsText = formatViews(totalViews(ep));
      const viewsBlock = viewsText
        ? '<span class="popular-views"><span class="ember-dot" aria-hidden="true"></span>' +
            esc(viewsText) + platformMarksHtml() + "</span>"
        : "<span></span>";

      const card = document.createElement("div");
      card.className = "popular-card";
      const inner =
        '<div class="frame">' +
          cornerMarkup() +
          '<div class="popular-card-inner">' +
            thumbHtml(ep.thumbnail_url, "popular-thumb-wrap") +
            '<h3 class="font-display popular-title">' + esc(ep.title) + "</h3>" +
            '<div class="popular-bottom-row">' +
              viewsBlock +
              '<span class="tap-arrow" aria-hidden="true">&#8250;</span>' +
            "</div>" +
          "</div>" +
        "</div>";

      card.innerHTML = ep.video_id
        ? '<a class="card-link" href="' + esc(watchUrl(ep.video_id)) + '" target="_blank" ' +
          'rel="noopener noreferrer" aria-label="Watch ' + esc(ep.title) + ' on YouTube">' +
          inner + "</a>"
        : inner;
      wrap.appendChild(card);
    });
  }

  function renderList(episodes) {
    const listWrap = document.getElementById("episode-list");
    episodes.forEach(function (ep) {
      const row = document.createElement("a");
      row.href = watchUrl(ep.video_id);
      row.target = "_blank";
      row.rel = "noopener noreferrer";
      row.dataset.format = ep.format;
      row.className = "episode-row tap";
      row.setAttribute("aria-label", "Watch " + ep.title + " on YouTube");
      const viewsText = formatViews(totalViews(ep));
      const metaText = esc(formatDate(ep.published_at)) +
        (viewsText ? " &middot; " + esc(viewsText) + platformMarksHtml() : "");
      row.innerHTML =
        thumbHtml(ep.thumbnail_url, "row-thumb-wrap") +
        '<div class="row-body">' +
          '<div class="row-title-line">' +
            '<h3 class="font-display row-title">' + esc(ep.title) + "</h3>" +
          "</div>" +
          '<p class="row-meta">' + pillHtml(ep.format) + "<span>" + metaText + "</span></p>" +
        "</div>" +
        '<span class="row-arrow" aria-hidden="true">&#8250;</span>';
      listWrap.appendChild(row);
    });
  }

  // Single-select. The resting state is "nothing selected, everything
  // visible": clicking a chip isolates that format, clicking the same chip
  // again returns to the unfiltered state, and clicking a different chip
  // switches to it. The previous behaviour started with all three chips
  // pressed and toggled them OFF, so a first click read as "remove this
  // format" - the inverse of what a filter chip is expected to do.
  function wireFilter() {
    const chips = document.querySelectorAll(".chip");
    const rows = document.querySelectorAll("#episode-list > a");
    const emptyState = document.getElementById("empty-state");

    function apply(selected) {
      let visibleCount = 0;
      rows.forEach(function (row) {
        const show = selected === null || row.dataset.format === selected;
        row.classList.toggle("row-hidden", !show);
        if (show) visibleCount++;
      });
      emptyState.classList.toggle("show", visibleCount === 0);
    }

    chips.forEach(function (chip) {
      chip.addEventListener("click", function () {
        const wasSelected = chip.getAttribute("aria-pressed") === "true";
        chips.forEach(function (c) { c.setAttribute("aria-pressed", "false"); });
        if (wasSelected) {
          apply(null);
          return;
        }
        chip.setAttribute("aria-pressed", "true");
        apply(chip.dataset.format);
      });
    });

    apply(null);
  }

  // Reached from two different failure shapes: a genuinely empty catalog
  // (episodes.length === 0) and a fetch/parse failure (bad response, 5xx,
  // network error, malformed JSON) caught below. Those are not the same
  // claim - "nothing published yet" is true in the first case and false in
  // the second - so isFetchFailure picks the honest copy for each. Same
  // "absent section is honest" rule as renderLatestCard/renderPopular: also
  // drops the filter chips, since wireFilter() never ran to give them
  // handlers and three inert buttons over an error message is its own
  // small dishonesty.
  function renderError(isFetchFailure) {
    ["latest-section", "popular-section", "filter-section"].forEach(function (id) {
      const el = document.getElementById(id);
      if (el) el.remove();
    });
    const message = isFetchFailure
      ? "Couldn't load stories right now - check back soon, or find us on "
      : "Stories are on the way - check back soon, or find us on ";
    document.getElementById("episode-list").insertAdjacentHTML("beforeend",
      '<p class="tagline">' + message
      + '<a href="https://www.youtube.com/@thequilltruestories" style="color:#D97C4E">YouTube</a>.</p>');
  }

  fetch(API_URL, { credentials: "omit" })
    .then(function (res) {
      if (!res.ok) throw new Error("episode fetch failed: " + res.status);
      return res.json();
    })
    .then(function (episodes) {
      if (episodes.length === 0) {
        renderError(false);
        return;
      }
      // Normalised once at the boundary rather than at each render site: the
      // title reaches the DOM from six places (three headings, three aria
      // labels), and cleaning it here means none of them can drift.
      episodes.forEach(function (ep) {
        ep.title = displayTitle(ep.title);
      });
      const byLatest = episodes.slice().sort(function (a, b) {
        return new Date(b.published_at) - new Date(a.published_at);
      });
      renderLatestCard(byLatest[0]);

      // "Most Popular" is a ranking claim. If every episode has a null/
      // undefined count (e.g. the daily view-count refresh hasn't run
      // yet), there is no real ranking to show - sort() would just return
      // the stable input order (published_at DESC) under a label asserting
      // it's popularity-ordered. Drop the section rather than ship that.
      //
      // Ranked on the consolidated number, not the YouTube one: a "most
      // popular" claim that ignores most of a story's actual audience is the
      // less defensible of the two.
      const hasViewData = episodes.some(function (ep) {
        const v = totalViews(ep);
        return v !== null && v !== undefined;
      });
      if (hasViewData) {
        const popular = episodes.slice().sort(function (a, b) {
          return (totalViews(b) ?? -1) - (totalViews(a) ?? -1);
        }).slice(0, 3);
        renderPopular(popular);
      } else {
        document.getElementById("popular-section").remove();
      }

      renderList(byLatest);

      wireFilter();
    })
    .catch(function () {
      renderError(true);
    });
})();
