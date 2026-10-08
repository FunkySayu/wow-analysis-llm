#!/usr/bin/env python3
"""Fetch the talent-tree background art for a spec.

The in-game talent UI paints one piece of Blizzard art behind the class and spec trees
together. Our editor renders three separate ``<svg>`` elements on a flat surface, which
makes the tree hard to read: with no art, every node sits on the same neutral ground and
there is nothing to orient against.

Where the art comes from
------------------------
Wowhead's Dragonflight talent calculator serves the Blizzard textures from a stable path
under ``wow.zamimg.com``. It is *not* an API and there is no manifest, so the file list is
recovered from the calculator's own stylesheet::

    https://wow.zamimg.com/css/standard/tools/talent-calc-dragonflight.css

whose rules read (verbatim, for Balance Druid)::

    .dragonflight-talent-trees[data-class-spec=druid-balance]:not([data-narrow]){
      background-image:linear-gradient(180deg,rgba(0,0,0,.6),transparent 90px),
                       url("/images/tools/dragonflight-talent-calc/blizzard/talentbg-druid-balance.jpg")}

Two facts that matter to the consumer and are easy to get wrong:

1. **One image covers class *and* spec, side by side** -- it is not a per-tree background.
   The measured Balance Druid asset is 1614x776. A caller that sets it on each tree
   separately will draw it twice and align neither. The frontend puts it on the element
   that wraps both trees; see ``site/frontend/src/features/talents/TalentTree.module.css``.
2. **The hero tree has no art of its own.** Blizzard draws the hero panel on the same
   stone surface, not on the spec background, so this tool fetches nothing for it.

Naming is derived, never hardcoded: Wowhead keys the file by ``<class>-<spec>`` in kebab
case ("Death Knight" -> ``death-knight``, "Beast Mastery" -> ``beast-mastery``), which is a
plain slugify of the class and spec names this repo already stores in
``data/classes/<class>/<spec>/<patch>_talents.json``. That ordering is the *reverse* of this project's own
spec slug (``balance-druid``), which is exactly the kind of silent mismatch worth stating
out loud rather than discovering through a 404.

HTTP 200 is not proof of correct data (CLAUDE.md): a miss on this CDN returns a 146-byte
``text/html`` error page with status 404, but a *wrong* name could plausibly return some
other spec's art with status 200. So the fetch asserts the payload is really a JPEG and
really has plausible dimensions, and records the sha256 alongside it.

Usage
-----
    python3 tools/raidbots/talent_background_sync.py balance-druid
    python3 tools/raidbots/talent_background_sync.py --all # every tree under data/classes/
"""

from __future__ import annotations

import argparse
import hashlib
import json
import pathlib
import re
import struct
import sys
import urllib.error
import urllib.request

REPO = pathlib.Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO / "tools"))

import datalayout as D  # noqa: E402

OUT = REPO / "site" / "frontend" / "public" / "talents"
MANIFEST = OUT / "index.json"

BASE = "https://wow.zamimg.com/images/tools/dragonflight-talent-calc/blizzard"
CSS = "https://wow.zamimg.com/css/standard/tools/talent-calc-dragonflight.css"

#: A JPEG under ~20 KB is an error page or a placeholder, not 1600px of art; over 4 MB is
#: not a background. Both bounds are deliberately loose -- they exist to catch a wrong
#: *kind* of response, not to police compression.
MIN_BYTES = 20_000
MAX_BYTES = 4_000_000
MIN_WIDTH = 800

UA = {"User-Agent": "Mozilla/5.0 (wow-analysis talent_background_sync)", "Referer": "https://www.wowhead.com/"}


def slugify(name: str) -> str:
    """"Beast Mastery" -> "beast-mastery". Wowhead's own key format."""
    return re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-")


def jpeg_size(blob: bytes) -> tuple[int, int]:
    """(width, height) of a JPEG, by walking its segment markers.

    Written out rather than pulled from Pillow because this is the only image work in the
    repo and the check it powers -- "is this really art and not an error page" -- must not
    depend on an optional third-party install to run at all.
    """
    if blob[:2] != b"\xff\xd8":
        raise ValueError("not a JPEG (no SOI marker)")
    i = 2
    while i < len(blob) - 9:
        if blob[i] != 0xFF:
            i += 1
            continue
        marker = blob[i + 1]
        # SOF0..SOF15, excluding the non-frame markers DHT (c4), JPGA (c8) and DAC (cc).
        if 0xC0 <= marker <= 0xCF and marker not in (0xC4, 0xC8, 0xCC):
            height, width = struct.unpack(">HH", blob[i + 5 : i + 9])
            return width, height
        if marker in (0xD8, 0x01) or 0xD0 <= marker <= 0xD7:
            i += 2
            continue
        (seg,) = struct.unpack(">H", blob[i + 2 : i + 4])
        i += 2 + seg
    raise ValueError("no SOF marker found")


def get(url: str) -> bytes:
    req = urllib.request.Request(url, headers=UA)
    with urllib.request.urlopen(req, timeout=30) as resp:  # noqa: S310 - fixed https host
        return resp.read()


def known_backgrounds() -> set[str]:
    """The ``<class>-<spec>`` keys the calculator's stylesheet actually references.

    Consulted before fetching so a spec whose art does not exist fails with "not in the
    stylesheet" rather than an opaque 404 -- and so a *renamed* spec is visible as a
    mismatch against a list, instead of as a missing file.
    """
    css = get(CSS).decode("utf-8", "replace")
    return set(re.findall(r"talentbg-([a-z0-9-]+)\.jpg", css))


def sync_one(spec_slug: str, available: set[str] | None) -> dict[str, object]:
    doc = json.loads(D.talent_tree_path(spec_slug).read_text(encoding="utf-8"))
    spec = doc["spec"]
    key = f"{slugify(spec['class_name'])}-{slugify(spec['spec_name'])}"

    if available is not None and key not in available:
        raise SystemExit(
            f"{spec_slug}: derived key {key!r} is not referenced by the calculator stylesheet. "
            f"Closest keys: {sorted(k for k in available if k.startswith(slugify(spec['class_name'])))}"
        )

    url = f"{BASE}/talentbg-{key}.jpg"
    try:
        blob = get(url)
    except urllib.error.HTTPError as exc:
        raise SystemExit(f"{spec_slug}: {url} returned HTTP {exc.code}") from exc

    if not (MIN_BYTES <= len(blob) <= MAX_BYTES):
        raise SystemExit(f"{spec_slug}: {url} returned {len(blob)} bytes -- outside the plausible range for art")
    width, height = jpeg_size(blob)
    if width < MIN_WIDTH:
        raise SystemExit(f"{spec_slug}: {url} is {width}x{height} -- too small to be the tree background")

    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / f"{spec_slug}.jpg").write_bytes(blob)

    return {
        "spec": spec_slug,
        "wowhead_key": key,
        "source": url,
        "bytes": len(blob),
        "width": width,
        "height": height,
        "sha256": hashlib.sha256(blob).hexdigest(),
    }


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("spec", nargs="*", help="spec slug(s), e.g. balance-druid")
    ap.add_argument("--all", action="store_true", help="every tree under data/classes/")
    args = ap.parse_args(argv)

    specs = args.spec
    if args.all:
        specs = sorted(D.spec_slug(p) for p in D.talent_tree_paths())
    if not specs:
        ap.error("give at least one spec slug, or --all")

    available = known_backgrounds()
    entries = {}
    if MANIFEST.exists():
        entries = {e["spec"]: e for e in json.loads(MANIFEST.read_text(encoding="utf-8"))["backgrounds"]}

    for slug in specs:
        entry = sync_one(slug, available)
        entries[slug] = entry
        print(f"{slug}: {entry['width']}x{entry['height']}, {entry['bytes']:,} bytes  <- {entry['source']}")

    MANIFEST.write_text(
        json.dumps(
            {
                "note": (
                    "Blizzard talent-tree art, as served by Wowhead's Dragonflight talent "
                    "calculator. One image spans the class and spec trees together; the hero "
                    "tree has none. Regenerate with tools/raidbots/talent_background_sync.py."
                ),
                "backgrounds": [entries[k] for k in sorted(entries)],
            },
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
