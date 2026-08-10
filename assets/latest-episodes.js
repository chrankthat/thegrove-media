// Progressive-enhancement widget: fetches the latest 3 episodes for any show
// with an episodeApi configured (content/channels.json) and renders them into
// that show's reserved "Latest Episodes" sidebar slot. Fails silently on any
// error - the static watch/listen/social links around this slot always work
// regardless, per the originating spec's fail-soft design. Same-origin only
// (script-src 'self' in _headers) - no external script host, no framework.
(function () {
  "use strict";

  function renderEpisodes(container, episodes) {
    if (episodes.length === 0) {
      container.closest(".sidebar-block").remove();
      return;
    }
    const items = episodes.map(function (ep) {
      const li = document.createElement("li");
      const a = document.createElement("a");
      a.href = "https://www.youtube.com/watch?v=" + encodeURIComponent(ep.video_id);
      a.target = "_blank";
      a.rel = "noopener noreferrer";
      a.textContent = ep.title;
      li.appendChild(a);
      return li;
    });
    container.replaceChildren.apply(container, items);
  }

  document.querySelectorAll("[data-episode-api]").forEach(function (container) {
    const apiUrl = container.dataset.episodeApi;
    fetch(apiUrl + "&limit=3", { credentials: "omit" })
      .then(function (res) {
        if (!res.ok) throw new Error("episode fetch failed: " + res.status);
        return res.json();
      })
      .then(function (episodes) {
        renderEpisodes(container, episodes);
      })
      .catch(function () {
        // Fail-soft: the block stays out of the DOM. It was rendered by
        // render.py already collapsed to empty when no static `latest` data
        // existed (see render_latest_block), so removing it on fetch failure
        // matches that same "an absent section is honest" rule at runtime
        // instead of build time.
        const block = container.closest(".sidebar-block");
        if (block) block.remove();
      });
  });
})();
