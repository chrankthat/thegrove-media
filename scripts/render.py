#!/usr/bin/env python3
"""Generate index.html from content/channels.json + content/icons.json.

D4 (zero build step): run this locally after any edit to content/*.json,
before committing. Cloudflare Pages serves the repo root with no build
command - index.html in git IS the deployed artifact.

    python3 scripts/render.py
"""
import hashlib
import html
import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
CHANNELS_PATH = ROOT / "content" / "channels.json"
ICONS_PATH = ROOT / "content" / "icons.json"
OUTPUT_PATH = ROOT / "index.html"

ROLE_LABELS = {"produced": "Produced by TheGrove Media"}


def esc(s):
    return html.escape(s, quote=True)


def hex_to_rgb_csv(hex_color):
    h = hex_color.lstrip("#")
    return ",".join(str(int(h[i:i + 2], 16)) for i in (0, 2, 4))


COLOR_RE = re.compile(r"^#[0-9A-Fa-f]{6}$")
NAME_RE = re.compile(r"^[A-Za-z0-9 .'-]+$")
ID_RE = re.compile(r"^[a-z0-9-]+$")


def slug(label):
    return label.lower().replace(" ", "-")


def validate_show(show):
    """Fail loud on a malformed content edit rather than emitting broken markup.

    Five of these values land inside a style="" attribute and one lands in three
    separate attributes, so a stray quote would escape the attribute and then the
    tag. Validating is cheaper and clearer than escaping colors and font names.
    """
    if not ID_RE.match(show["id"]):
        raise ValueError(f"show id {show['id']!r} must match {ID_RE.pattern}")
    for key in ("accent", "field", "ink"):
        if not COLOR_RE.match(show[key]):
            raise ValueError(f"{show['id']}.{key} = {show[key]!r} is not a 6-digit hex color")
    for key in ("display", "body"):
        if not NAME_RE.match(show[key]):
            raise ValueError(f"{show['id']}.{key} = {show[key]!r} is not a plain font name")


def render_icon_sprite(icons):
    symbols = [
        f'  <symbol id="icon-{slug(label)}" viewBox="0 0 24 24"><path d="{esc(entry["path"])}"/></symbol>'
        for label, entry in icons.items()
    ]
    return (
        '<svg aria-hidden="true" style="position:absolute;width:0;height:0;'
        'overflow:hidden;" focusable="false">\n'
        + "\n".join(symbols)
        + "\n</svg>"
    )


def render_icon_row(items, icons, action):
    lis = []
    for item in items:
        icon_key = item.get("icon")
        if not icon_key:
            continue
        entry = icons[icon_key]
        label = item["label"]
        # Discriminate on an explicit flag, NOT on the presence of a `note` key:
        # LinkedIn carries a provenance note and is an official mark, so keying
        # off `note` mislabels it as a placeholder. See fold addendum FOLD-1.
        is_generic = entry.get("placeholder") is True
        aria_suffix = " (generic placeholder icon, not an official logo)" if is_generic else ""
        title_suffix = " (generic icon)" if is_generic else ""
        # href keys off the ICONS-DICT key, not the item label - the sprite's
        # <symbol id> is built from the dict key, and label != key is legal data.
        lis.append(
            f'<li><a class="icon-link" href="{esc(item["url"])}" target="_blank" '
            f'rel="noopener noreferrer" aria-label="{esc(action)} on {esc(label)}{esc(aria_suffix)}" '
            f'title="{esc(label)}{esc(title_suffix)}"><svg class="icon" viewBox="0 0 24 24">'
            f'<use href="#icon-{slug(icon_key)}"></use></svg></a></li>'
        )
    return "\n".join(lis)


def render_link_list(items):
    return "\n".join(
        f'<li><a href="{esc(i["url"])}" target="_blank" rel="noopener noreferrer">{esc(i["label"])}</a></li>'
        for i in items
    )


def render_schedule_block(cadence):
    # Intentionally renders ONLY `display`. `source`/`verified` are read by
    # the deferred O6 /smoke predicate, not shown to readers - Chris's
    # 2026-08-04 direction, see plan "Deviations from decision.md / spec".
    return "\n".join(
        f'<div class="cadence-entry"><p class="cadence-display">{esc(c["display"])}</p></div>'
        for c in cadence
    )


def render_latest_block(latest):
    if latest:
        items = "\n".join(f"<li>{esc(i)}</li>" for i in latest)
        return f'<ul class="latest-list">\n{items}\n</ul>'
    return '<p class="latest-empty">New episodes will appear here.</p>'


def render_show(show, icons):
    validate_show(show)
    style = (
        f'--field:{show["field"]}; --ink:{show["ink"]}; --accent:{show["accent"]}; '
        f'--accent-rgb:{hex_to_rgb_csv(show["accent"])}; '
        f'--display:\'{show["display"]}\',serif; --body-font:\'{show["body"]}\',sans-serif;'
    )
    show_id = esc(show["id"])
    eyebrow = ROLE_LABELS[show["role"]]

    lead_html = ""
    if show.get("lead"):
        lines = "\n".join(f"<p>{esc(l)}</p>" for l in show["lead"])
        lead_html = f'<div class="lead-lines">{lines}</div>'

    extra_html = ""
    if show.get("extraLine"):
        extra_html = f'<p class="extra-line">{esc(show["extraLine"])}</p>'

    cohost_html = ""
    if show.get("cohost"):
        c = show["cohost"]
        cohost_html = (
            '<div class="cohost-credit">'
            f'<img class="cohost-photo" src="{esc(c["photo"])}" alt="Photo of {esc(c["name"])}" '
            'width="32" height="32" loading="lazy">'
            f'<p>Co-hosted with <a href="{esc(c["url"])}" target="_blank" '
            f'rel="noopener noreferrer">{esc(c["name"])}</a></p></div>'
        )

    listen_html = render_icon_row(show["listen"], icons, "Listen") if show["listen"] else ""
    listen_block = ""
    if listen_html:
        listen_block = (
            '<div class="sidebar-block"><h3 class="sidebar-label">'
            '<span class="dot" aria-hidden="true"></span>Listen</h3>'
            f'<ul class="icon-row">\n{listen_html}\n</ul></div>'
        )

    return f'''      <section id="{show_id}" class="show" style="{style}">
        <div class="chapter-inner">
          <input type="checkbox" id="disc-{show_id}" class="disc">
          <div class="chapter-grid">
            <div class="chapter-main">
              <label for="disc-{show_id}" class="opener">
                <span class="mark-wrap" aria-hidden="true"><img class="mark" src="{esc(show["mark"])}" alt="" width="116" height="116" loading="lazy"></span>
                <span class="eyebrow">{esc(eyebrow)}</span>
                <span class="opener-text">
                  <span class="tile-name" role="heading" aria-level="2">{esc(show["name"])}</span>
                  <span class="tile-tagline">{esc(show["tagline"])}</span>
                </span>
                <svg class="chevron" viewBox="0 0 20 20" fill="none" aria-hidden="true"><path d="M5 7.5 10 12.5 15 7.5" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"/></svg>
              </label>
              <div class="panel">
                {lead_html}<p class="chapter-blurb">{esc(show["blurb"])}</p>{extra_html}{cohost_html}
              </div>
            </div>
            <aside class="sidebar" aria-label="{esc(show["name"])} - schedule and links">
              <div class="sidebar-block"><h3 class="sidebar-label"><span class="dot" aria-hidden="true"></span>Schedule</h3>
                {render_schedule_block(show["cadence"])}
              </div>
              <div class="sidebar-block"><h3 class="sidebar-label"><span class="dot" aria-hidden="true"></span>Latest Episodes</h3>
                <hr class="latest-rule">
                {render_latest_block(show["latest"])}
              </div>
              <div class="sidebar-block"><h3 class="sidebar-label"><span class="dot" aria-hidden="true"></span>Watch</h3>
                <ul class="link-list">
{render_link_list(show["watch"])}
                </ul>
              </div>{listen_block}
              <div class="sidebar-block"><h3 class="sidebar-label"><span class="dot" aria-hidden="true"></span>Socials</h3>
                <ul class="icon-row">
{render_icon_row(show["socials"], icons, "Follow")}
                </ul>
              </div>
            </aside>
          </div>
        </div>
      </section>'''
