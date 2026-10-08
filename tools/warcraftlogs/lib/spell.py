"""Fetch spell/aura tooltip text by spell ID, from Wowhead's tooltip API.

Same endpoint the `wow-talent-data` skill uses to enrich talent nodes with
descriptions (see .claude/skills/wow-talent-data/SKILL.md) - reused here so a
check can print what a talent/spell actually does instead of just its ID.

**Trap** (documented in that skill, applies here too): the endpoint WITHOUT
`/ptr/` silently serves the LIVE tooltip even for a spell that was redesigned
on PTR - no error, just wrong text. `ptr=True` is the default because this
project's data is PTR-first; pass `ptr=False` explicitly for live-only checks.
"""

import dataclasses
import html
import json
import os
import re
import urllib.request

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", ".."))
CACHE = os.path.join(ROOT, ".wclcache", "spells")


@dataclasses.dataclass
class Spell:
    id: int
    name: str
    icon: str
    description: str


@dataclasses.dataclass
class Aura:
    id: int
    name: str
    icon: str
    description: str


def _strip_html(text):
    text = re.sub(r"<br\s*/?>", "\n", text)
    text = re.sub(r"<[^>]+>", "", text)
    return html.unescape(text).strip()


def _fetch(spell_id, ptr, refresh=False):
    os.makedirs(CACHE, exist_ok=True)
    p = os.path.join(CACHE, f"{'ptr' if ptr else 'live'}_{spell_id}.json")
    if not refresh and os.path.exists(p):
        try:
            return json.load(open(p, encoding="utf-8"))
        except Exception:
            pass
    path = f"/ptr/tooltip/spell/{spell_id}" if ptr else f"/tooltip/spell/{spell_id}"
    req = urllib.request.Request(f"https://nether.wowhead.com{path}",
                                  headers={"User-Agent": "wow-analysis/1.0"})
    with urllib.request.urlopen(req, timeout=30) as r:
        data = json.loads(r.read().decode())
    json.dump(data, open(p, "w", encoding="utf-8"))
    return data


def get_spell(spell_id, ptr=True, refresh=False):
    """Fetch a castable spell's name/icon/tooltip by ID."""
    d = _fetch(spell_id, ptr, refresh)
    return Spell(id=spell_id, name=d.get("name", "?"), icon=d.get("icon", ""),
                 description=_strip_html(d.get("tooltip", "")))


def get_aura(spell_id, ptr=True, refresh=False):
    """Fetch a buff/debuff's name/icon/tooltip by ID.

    Same tooltip endpoint as get_spell - Wowhead doesn't distinguish auras from
    castable spells by ID. Kept as a separate call so check code can say what
    kind of thing it's looking up.
    """
    d = _fetch(spell_id, ptr, refresh)
    return Aura(id=spell_id, name=d.get("name", "?"), icon=d.get("icon", ""),
                description=_strip_html(d.get("tooltip", "")))
