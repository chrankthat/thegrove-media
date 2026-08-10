(function () {
  "use strict";

  const API_URL = "https://quill-scheduler.chris-ba5.workers.dev/episodes?show=quill";

  const FORMAT_LABEL = { battle: "Battle", trial: "Trial", chapters: "My Lost Chapters" };

  const FORMAT_ICON = {
    battle: '<svg width="11" height="11" viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg"><path d="M4 20L14 10" stroke="currentColor" stroke-width="2" stroke-linecap="round"/><path d="M13 4L20 11" stroke="currentColor" stroke-width="2" stroke-linecap="round"/><path d="M4 4L20 20" stroke="currentColor" stroke-width="2" stroke-linecap="round"/></svg>',
    trial: '<svg width="11" height="11" viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg"><path d="M12 3V21" stroke="currentColor" stroke-width="2" stroke-linecap="round"/><path d="M5 7H19" stroke="currentColor" stroke-width="2" stroke-linecap="round"/><path d="M3 7L6 13H2L5 7Z" stroke="currentColor" stroke-width="1.6" stroke-linejoin="round"/><path d="M17 7L20 13H16L19 7Z" stroke="currentColor" stroke-width="1.6" stroke-linejoin="round"/></svg>',
    chapters: '<svg width="11" height="11" viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg"><path d="M12 5C10 3.8 6.5 3.5 4 4.2V17.5C6.5 16.8 10 17.1 12 18.3C14 17.1 17.5 16.8 20 17.5V4.2C17.5 3.5 14 3.8 12 5Z" stroke="currentColor" stroke-width="1.5" stroke-linejoin="round"/><path d="M12 5V18.3" stroke="currentColor" stroke-width="1.5"/></svg>',
  };

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

  function formatDate(iso) {
    const d = new Date(iso);
    return d.toLocaleDateString("en-US", { month: "short", day: "numeric", year: "numeric" });
  }

  // Formats never linked a fourth show format to this page; fall back to the
  // raw value rather than rendering the literal string "undefined".
  function formatLabel(fmt) {
    return Object.prototype.hasOwnProperty.call(FORMAT_LABEL, fmt) ? FORMAT_LABEL[fmt] : fmt;
  }

  function formatIcon(fmt) {
    return Object.prototype.hasOwnProperty.call(FORMAT_ICON, fmt) ? FORMAT_ICON[fmt] : "";
  }

  function cornerMarkup() {
    const tpl = document.getElementById("corner-svg-template").innerHTML;
    return ["tl", "tr", "bl", "br"].map(function (pos) {
      return '<span class="corner corner-' + pos + '" aria-hidden="true">' + tpl + "</span>";
    }).join("");
  }

  document.getElementById("masthead").insertAdjacentHTML("afterbegin", cornerMarkup());

  function thumbHtml(ep, className) {
    if (!ep.thumbnail_url) return '<div class="placeholder-thumb ' + className + '"></div>';
    return '<img class="' + className + '" src="' + esc(ep.thumbnail_url) + '" alt="" width="320" height="180" loading="lazy">';
  }

  function renderLatestCard(ep) {
    const latestCard = document.getElementById("latest-card");
    if (!ep) {
      latestCard.closest("section").remove();
      return;
    }
    const viewsText = formatViews(ep.view_count);
    const viewsBlock = viewsText
      ? '<div class="hero-views">' +
          '<span class="ember-dot" aria-hidden="true"></span><span>' + esc(viewsText) + "</span>" +
        "</div>"
      : "";
    latestCard.innerHTML =
      cornerMarkup() +
      thumbHtml(ep, "hero-thumb") +
      '<div class="hero-meta-row">' +
        '<span class="format-pill" data-format="' + esc(ep.format) + '">' +
          formatIcon(ep.format) + "<span>" + esc(formatLabel(ep.format)) + "</span>" +
        "</span>" +
        '<span class="tagline">' + esc(formatDate(ep.published_at)) + "</span>" +
      "</div>" +
      '<h3 class="font-display hero-title">' + esc(ep.title) + "</h3>" +
      viewsBlock;
  }

  function renderPopular(episodes) {
    const wrap = document.getElementById("popular-scroll");
    episodes.forEach(function (ep) {
      const card = document.createElement("article");
      card.className = "frame popular-card";
      const viewsText = formatViews(ep.view_count);
      const viewsBlock = viewsText
        ? '<div class="card-views">' +
            '<span class="ember-dot" aria-hidden="true"></span><span>' + esc(viewsText) + "</span>" +
          "</div>"
        : "";
      card.innerHTML =
        cornerMarkup() +
        thumbHtml(ep, "card-thumb") +
        '<h3 class="font-display card-title">' + esc(ep.title) + "</h3>" +
        viewsBlock;
      wrap.appendChild(card);
    });
  }

  function renderList(episodes) {
    const listWrap = document.getElementById("episode-list");
    episodes.forEach(function (ep) {
      const row = document.createElement("a");
      row.href = "https://www.youtube.com/watch?v=" + encodeURIComponent(ep.video_id);
      row.target = "_blank";
      row.rel = "noopener noreferrer";
      row.dataset.format = ep.format;
      row.className = "episode-row tap";
      const viewsText = formatViews(ep.view_count);
      const metaText = esc(formatDate(ep.published_at)) + (viewsText ? " &middot; " + esc(viewsText) : "");
      row.innerHTML =
        thumbHtml(ep, "row-thumb") +
        '<div class="row-body">' +
          '<div class="row-title-line">' +
            '<h3 class="font-display row-title">' + esc(ep.title) + "</h3>" +
            '<span class="format-pill" data-format="' + esc(ep.format) + '">' +
              formatIcon(ep.format) + "<span>" + esc(formatLabel(ep.format)) + "</span>" +
            "</span>" +
          "</div>" +
          '<p class="row-meta">' + metaText + "</p>" +
        "</div>";
      listWrap.appendChild(row);
    });
  }

  function wireFilter() {
    const active = { battle: true, trial: true, chapters: true };
    const chips = document.querySelectorAll(".chip");
    const rows = document.querySelectorAll("#episode-list > a");
    const emptyState = document.getElementById("empty-state");

    function applyFilter() {
      let visibleCount = 0;
      rows.forEach(function (row) {
        const show = active[row.dataset.format];
        row.classList.toggle("row-hidden", !show);
        if (show) visibleCount++;
      });
      emptyState.classList.toggle("show", visibleCount === 0);
    }

    chips.forEach(function (chip) {
      chip.addEventListener("click", function () {
        const fmt = chip.dataset.format;
        active[fmt] = !active[fmt];
        chip.setAttribute("aria-pressed", String(active[fmt]));
        applyFilter();
      });
    });

    applyFilter();
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
    document.getElementById("latest-section").remove();
    document.querySelectorAll("section").forEach(function (section) {
      if (section.querySelector("#popular-scroll")) section.remove();
      if (section.querySelector(".filter-row")) section.remove();
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
      const latest = episodes.slice().sort(function (a, b) {
        return new Date(b.published_at) - new Date(a.published_at);
      })[0];
      renderLatestCard(latest);

      // "Most Popular" is a ranking claim. If every episode has a null/
      // undefined view_count (e.g. the daily view-count refresh hasn't run
      // yet), there is no real ranking to show - sort() would just return
      // the stable input order (published_at DESC) under a label asserting
      // it's popularity-ordered. Drop the section rather than ship that.
      const hasViewData = episodes.some(function (ep) {
        return ep.view_count !== null && ep.view_count !== undefined;
      });
      if (hasViewData) {
        const popular = episodes.slice().sort(function (a, b) {
          return (b.view_count ?? -1) - (a.view_count ?? -1);
        }).slice(0, 3);
        renderPopular(popular);
      } else {
        document.getElementById("popular-scroll").closest("section").remove();
      }

      const byLatest = episodes.slice().sort(function (a, b) {
        return new Date(b.published_at) - new Date(a.published_at);
      });
      renderList(byLatest);

      wireFilter();
    })
    .catch(function () {
      renderError(true);
    });
})();
