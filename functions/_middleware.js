// Hostname routing: quill.thegrove.media serves /quill/* transparently.
// Everything else (the thegrove.media root domain) passes through
// untouched - still pure static, zero backend, per the repo's README.
// This IS a deliberate, minimal exception to that posture for one host,
// not a general-purpose router - see decision.md's danger-trigger checklist,
// this was reviewed as NOT firing ad191 (no Postgres/credential/seam touch).
export async function onRequest(context) {
  const url = new URL(context.request.url);
  if (url.hostname === "quill.thegrove.media") {
    if (url.pathname === "/" || url.pathname === "") {
      url.pathname = "/quill/";
    } else if (!url.pathname.startsWith("/quill/")) {
      url.pathname = "/quill" + url.pathname;
    }
    return context.env.ASSETS.fetch(new Request(url, context.request));
  }
  return context.next();
}
