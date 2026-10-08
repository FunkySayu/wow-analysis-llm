#!/usr/bin/env python3
"""Extract a class/spec-filtered zone -> item-pool map from the KeystoneLoot addon's own
bundled loot databases, and write it to data/classes/<class>/<spec>/12_1_loot_sources.json.

Python port of tools/keystoneloot/extract_source_data.pl --
read that script's header comment first, it documents the *why* (the KeystoneLoot v3
export string carries no sourceId, so "which boss drops this item" has to come from
somewhere else) in more depth than is repeated here. This port adds one thing the Perl
script never needed: an `encounterSlug` per raid boss, so
`site/backend/app/services/keystoneloot.py` can join straight to this site's own
`encounters.slug` without a second lookup table.

Usage:
    python tools/keystoneloot/keystoneloot_sources_sync.py     # classId 11 (Druid), specId 102 (Balance)
    python tools/keystoneloot/keystoneloot_sources_sync.py --class-id 8 --spec-id 62   # Arcane Mage

Reads from the addon install (default path below, override with the
KEYSTONELOOT_ADDON_PATH env var or --addon-path).

Zone/boss display names and encounter slugs are NOT in the addon's data files --
dungeons.lua/raids.lua only carry a `--[[name = "..."]]` Lua *comment*, auto-generated in
whatever locale the addon author's client was running (German, in the copy this was
built against). The DUNGEON_NAME / RAID_ZONE_NAME / BOSS_NAME / BOSS_ENCOUNTER_SLUG
tables below are hand-verified instead, cross-checked against
.claude/knowledge/raid/12_1/venomous_abyss/venomous-abyss-12.1.md and docs/design/00-overview.md's "Seed reality check" (the
canonical nine-encounter slug list). If KeystoneLoot ships a new season, this table goes
stale silently -- it resolves to "Unknown dungeon/boss/raid <id>" rather than erroring,
which is the signal to re-verify and update it by hand.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT / "tools"))

import datalayout as D  # noqa: E402
DEFAULT_ADDON_PATH = Path(r"E:\World of Warcraft\_retail_\Interface\AddOns\KeystoneLoot")

DUNGEON_NAME: dict[int, str] = {
    249: "Kings' Rest",
    250: "Temple of Sethraliss",
    399: "Ruby Life Pools",
    584: "The Blinding Vale",
    585: "Voidscar Arena",
    586: "Den of Nalorakk",
    587: "Murder Row",
    588: "Altar of Fangs",
}

RAID_ZONE_NAME: dict[int, str] = {
    1317: "Tidebound Grotto",  # Lair (single boss)
    1320: "The Venomous Abyss",
}

BOSS_NAME: dict[int, str] = {
    2849: "Nymrissa Wavecaller",
    2888: "Nek'zali the Soulcoiler",
    2874: "Entombed Sentinels",
    2894: "The Lost Explorers",
    2882: "Vashnik the Malignant",
    2871: "Sszorak",
    2887: "The Twin Fangs",
    2883: "The Coiled Altar",
    2895: "Ula'tek",
}

#: This site's `encounters.slug` for each raid boss -- see docs/design/00-overview.md's "Seed reality
#: check". All nine encounters (including the Tidebound Grotto lair boss) are seeded
#: under the single `venomous-abyss` zone.
BOSS_ENCOUNTER_SLUG: dict[int, str] = {
    2849: "nymrissa",
    2888: "nekzali",
    2874: "sentinels",
    2894: "explorers",
    2882: "vashnik",
    2871: "sszorak",
    2887: "twinfangs",
    2883: "coiledaltar",
    2895: "ulatek",
}


def _slurp(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def _parse_usable_items(items_lua: str, class_id: int, spec_id: int) -> dict[int, int | None]:
    """itemId -> slotId, only for items usable by this class+spec.

    `classes[classId]` existing is not the same as this spec being able to equip the
    item -- some entries list only a subset of a class's specs (e.g. `[8] = {62, 63}`,
    no 64), so the spec id is checked explicitly rather than just the class key.
    """
    usable: dict[int, int | None] = {}
    for match in re.finditer(r"\[(\d+)\]\s*=\s*\{(.*?)\},\s*$", items_lua, re.MULTILINE):
        item_id, body = int(match.group(1)), match.group(2)
        class_block = re.search(rf"\[{class_id}\]\s*=\s*\{{([^}}]*)\}}", body)
        if class_block is None:
            continue
        specs = [int(s) for s in re.findall(r"\d+", class_block.group(1))]
        if spec_id not in specs:
            continue
        slot_match = re.search(r"slotId\s*=\s*(-?\d+)", body)
        usable[item_id] = int(slot_match.group(1)) if slot_match else None
    return usable


def _parse_dungeon_zones(dungeons_lua: str, usable: dict[int, int | None]) -> list[dict[str, object]]:
    zones: list[dict[str, object]] = []
    for match in re.finditer(
        r"challengeModeId\s*=\s*(\d+),.*?lootTable\s*=\s*\{([^}]*)\}", dungeons_lua, re.DOTALL
    ):
        challenge_mode_id, loot_str = int(match.group(1)), match.group(2)
        item_ids = [int(i) for i in re.findall(r"\d+", loot_str) if int(i) in usable]
        if not item_ids:
            continue
        zones.append(
            {
                "type": "dungeon",
                "key": f"dungeon:{challenge_mode_id}",
                "zoneName": DUNGEON_NAME.get(challenge_mode_id, f"Unknown dungeon {challenge_mode_id}"),
                "bossName": None,
                "encounterSlug": None,  # Mythic+ has no seeded `encounters` row
                "items": [{"itemId": i, "slotId": usable[i]} for i in item_ids],
            }
        )
    return zones


#: Both a raid entry and each boss inside its `bossList` start with the identical
#: "{ --[[name = " comment shape -- only indentation (4 spaces for the raid, 12 for a
#: boss within it) tells them apart, so the split is anchored to exactly 4 leading
#: spaces. Splitting on the comment alone shreds every boss out of its parent raid.
_RAID_BLOCK_SPLIT = re.compile(r"(?=\n {4}\{\s*--\[\[name = )")


def _parse_raid_zones(raids_lua: str, usable: dict[int, int | None]) -> list[dict[str, object]]:
    zones: list[dict[str, object]] = []
    for raid_block in _RAID_BLOCK_SPLIT.split(raids_lua):
        journal_match = re.search(r"journalInstanceId\s*=\s*(\d+)", raid_block)
        if journal_match is None:
            continue
        journal_instance_id = int(journal_match.group(1))
        zone_name = RAID_ZONE_NAME.get(journal_instance_id, f"Unknown raid {journal_instance_id}")

        for boss_match in re.finditer(
            r"bossId\s*=\s*(\d+),\s*lootTable\s*=\s*\{(.*?)\n\s*\}\s*\}", raid_block, re.DOTALL
        ):
            boss_id, loot_block = int(boss_match.group(1)), boss_match.group(2)
            seen: set[int] = set()
            item_ids: list[int] = []
            for raw_id in re.findall(r"\d+", loot_block):
                item_id = int(raw_id)
                if item_id in usable and item_id not in seen:
                    seen.add(item_id)
                    item_ids.append(item_id)
            if not item_ids:
                continue
            zones.append(
                {
                    "type": "raid",
                    "key": f"raid:{boss_id}",
                    "zoneName": zone_name,
                    "bossName": BOSS_NAME.get(boss_id, f"Unknown boss {boss_id}"),
                    "encounterSlug": BOSS_ENCOUNTER_SLUG.get(boss_id),
                    "items": [{"itemId": i, "slotId": usable[i]} for i in item_ids],
                }
            )
    return zones


def build_source_table(addon_path: Path, class_id: int, spec_id: int) -> dict[str, object]:
    usable = _parse_usable_items(_slurp(addon_path / "data" / "items.lua"), class_id, spec_id)
    print(f"items.lua: {len(usable)} items usable by classId={class_id} specId={spec_id}")

    zones = _parse_dungeon_zones(_slurp(addon_path / "data" / "dungeons.lua"), usable)
    zones += _parse_raid_zones(_slurp(addon_path / "data" / "raids.lua"), usable)

    for zone in zones:
        label = f"{zone['zoneName']} - {zone['bossName']}" if zone.get("bossName") else zone["zoneName"]
        print(f"  {label}: {len(zone['items'])} items")  # type: ignore[arg-type]

    return {"classId": class_id, "specId": spec_id, "zones": zones}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--class-id", type=int, default=11, help="WoW class id (default 11 = Druid)")
    parser.add_argument("--spec-id", type=int, default=102, help="WoW spec id (default 102 = Balance)")
    parser.add_argument(
        "--addon-path",
        type=Path,
        default=Path(os.environ.get("KEYSTONELOOT_ADDON_PATH", str(DEFAULT_ADDON_PATH))),
        help="Path to the installed KeystoneLoot addon folder",
    )
    parser.add_argument(
        "--out",
        type=Path,
        default=None,
        help="Output path (default: data/classes/<class>/<spec>/<patch>_loot_sources.json)",
    )
    args = parser.parse_args()

    table = build_source_table(args.addon_path, args.class_id, args.spec_id)
    if args.out is None:
        args.out = D.spec_dir_for_ids(args.class_id, args.spec_id) / f"{D.CURRENT_PATCH}_loot_sources.json"
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(table, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(f"\n{args.out} written - {len(table['zones'])} zones.")  # type: ignore[arg-type]


if __name__ == "__main__":
    main()
