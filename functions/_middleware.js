// Hostname routing: quill.thegrove.media serves /quill/* transparently.
// Everything else (the thegrove.media root domain) passes through untouched -
// still pure static, zero backend, per the repo's README. This IS a deliberate,
// minimal exception to that posture for one host, not a general-purpose router.
//
// WHY THE FALLBACK EXISTS. The first version prefixed every non-/quill/ path
// with /quill and served whatever came back. Cloudflare Pages answers a miss by
// falling back to the ROOT index.html at status 200, so every path that did not
// exist under /quill/ silently served the WRONG SITE with a success status:
//
//   /assets/og-image.png  -> /quill/assets/og-image.png  -> miss -> studio homepage, 200, text/html
//   /robots.txt           -> /quill/robots.txt           -> miss -> studio homepage, 200, text/plain
//   /quill                -> /quill/quill                -> miss -> studio homepage, 200
//   /nonexistent-page-xyz -> /quill/nonexistent-page-xyz -> miss -> studio homepage, 200
//
// All four measured live 2026-08-10. The 200 is the dangerous part: a crawler,
// a monitor and a browser all read it as "this page exists".
//
// The fix is a two-step resolve - try the quill-namespaced path, and on a miss
// retry the path unprefixed so shared root assets (/assets/*, /robots.txt)
// resolve for this host too. If both miss, return the namespaced 404 rather
// than the root index.html.
//
// This depends on 404.html existing at the repo root and at quill/404.html.
// Those are what make the asset binding return a real 404 for a miss instead of
// the 200-index.html fallback - without them there is nothing here to branch on
// and this middleware degrades to the old behaviour.
export async function onRequest(context) {
  const url = new URL(context.request.url);

  if (url.hostname !== "quill.thegrove.media") {
    return context.next();
  }

  const path = url.pathname;

  // The host's home. "/quill" (no trailing slash) is included because it used
  // to become "/quill/quill" and serve the studio homepage.
  if (path === "" || path === "/" || path === "/quill" || path === "/quill/") {
    return fetchAsset(context, "/quill/");
  }

  // Already namespaced - serve as-is. A miss here is a genuine 404 for a
  // /quill/ path and must not be retried unprefixed, or /quill/index.html
  // style typos would start resolving to root files.
  if (path.startsWith("/quill/")) {
    return fetchAsset(context, path);
  }

  const namespaced = await fetchAsset(context, "/quill" + path);
  if (namespaced.status !== 404) {
    return namespaced;
  }

  // Shared root asset (/assets/*, /robots.txt, ...) - resolve it unprefixed.
  const bare = await fetchAsset(context, path);
  if (bare.status !== 404) {
    return bare;
  }

  // Neither exists. Return the quill-namespaced 404 so a visitor on this host
  // gets the quill 404 page, not the studio's.
  return namespaced;
}

function fetchAsset(context, pathname) {
  const url = new URL(context.request.url);
  url.pathname = pathname;
  // GET/HEAD only in practice (pure static site), so re-deriving the Request
  // from the original for a second lookup carries no consumed-body risk.
  return context.env.ASSETS.fetch(new Request(url, context.request));
}
