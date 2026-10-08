"""Where long-term datasets live under ``data/`` -- the one place that knows the layout.

    data/raid/<patch>/<tier>/general.json                      zone + encounter order and ids
    data/raid/<patch>/<tier>/<nn>_<slug>/journal.json          one file per encounter
    data/raid/<patch>/<tier>/<nn>_<slug>/timers.json
    data/raid/<patch>/<tier>/<nn>_<slug>/profiles/<spec>-<difficulty>.json
    data/raid/<patch>/<tier>/<nn>_<slug>/plan_suggestions/<spec>-<difficulty>.json
    data/classes/<class>/<spec>/<patch>_talents.json           (and _cooldowns, _loot_sources)
    data/classes/specs.json                                    class/spec ids -> directory names
    data/items/<patch>/items.json                              item tooltip cache

Tools take the same slugs they always did (``--zone venomous-abyss``, ``--spec
balance-druid``) and resolve them here, so a reorganisation of ``data/`` is a change to this
file rather than to every script. Import it after putting ``tools/`` on ``sys.path``::

    sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))
    import datalayout as D

A per-encounter file is ``{"meta": {..., "encounter": <slug>}, "encounter": {...}}``.
``load_tier`` stitches a tier's files back into the older whole-tier shape
(``{"meta": ..., "encounters": [...]}``, in encounter order) for code that wants every boss
at once.
"""

from __future__ import annotations

import json
import pathlib
from typing import Any

REPO = pathlib.Path(__file__).resolve().parent.parent
DATA = REPO / "data"
CURRENT_PATCH = "12_1"

#: Longest first, so "demon-hunter" is not read as spec "demon" of class "hunter".
CLASSES = sorted(
    [
        "death-knight", "demon-hunter", "druid", "evoker", "hunter", "mage", "monk",
        "paladin", "priest", "rogue", "shaman", "warlock", "warrior",
    ],
    key=len,
    reverse=True,
)


def _snake(s: str) -> str:
    return s.replace("-", "_")


# ---- classes -----------------------------------------------------------------------------


def spec_dir(spec: str) -> pathlib.Path:
    """``balance-druid`` -> ``data/classes/druid/balance``."""
    for cls in CLASSES:
        if spec.endswith("-" + cls):
            return DATA / "classes" / _snake(cls) / _snake(spec[: -len(cls) - 1])
    raise ValueError(f"spec slug {spec!r} does not end in a known class ({', '.join(CLASSES)})")


def spec_dir_for_ids(class_id: int, spec_id: int) -> pathlib.Path:
    """Blizzard's numeric ids -> ``data/classes/<class>/<spec>``, via data/classes/specs.json."""
    doc = json.loads((DATA / "classes" / "specs.json").read_text(encoding="utf-8"))
    for cls in doc["classes"]:
        if cls["id"] == class_id:
            for spec in cls["specs"]:
                if spec["id"] == spec_id:
                    return DATA / "classes" / str(cls["dir"]) / str(spec["dir"])
    raise SystemExit(f"class {class_id} / spec {spec_id} is not in data/classes/specs.json")


def talent_tree_path(spec: str, patch: str = CURRENT_PATCH) -> pathlib.Path:
    return spec_dir(spec) / f"{patch}_talents.json"


def spec_cooldowns_path(spec: str, patch: str = CURRENT_PATCH) -> pathlib.Path:
    return spec_dir(spec) / f"{patch}_cooldowns.json"


def loot_sources_path(spec: str, patch: str = CURRENT_PATCH) -> pathlib.Path:
    return spec_dir(spec) / f"{patch}_loot_sources.json"


def talent_tree_paths(patch: str = CURRENT_PATCH) -> list[pathlib.Path]:
    return sorted((DATA / "classes").glob(f"*/*/{patch}_talents.json"))


def spec_slug(path: pathlib.Path) -> str:
    """Inverse of ``spec_dir``: any file under ``data/classes/druid/balance/`` -> ``balance-druid``."""
    rel_parts = path.resolve().relative_to(DATA / "classes").parts
    return f"{rel_parts[1]}-{rel_parts[0]}".replace("_", "-")


def items_path(patch: str = CURRENT_PATCH) -> pathlib.Path:
    return DATA / "items" / patch / "items.json"


TALENT_SCHEMA =DATA / "classes" / "talents.schema.json"
TIMERS_SCHEMA = DATA / "raid" / "timers.schema.json"


# ---- raid tiers --------------------------------------------------------------------------


def tier_dir(zone: str) -> pathlib.Path:
    """The tier directory whose general.json carries ``zone.slug == zone``."""
    for general in sorted((DATA / "raid").glob("*/*/general.json")):
        if json.loads(general.read_text(encoding="utf-8"))["zone"]["slug"] == zone:
            return general.parent
    raise SystemExit(f"no data/raid/<patch>/<tier>/general.json has zone slug {zone!r}")


def load_general(zone: str) -> dict[str, Any]:
    doc: dict[str, Any] = json.loads((tier_dir(zone) / "general.json").read_text(encoding="utf-8"))
    return doc


def encounters(zone: str) -> list[dict[str, Any]]:
    """The tier's encounters in order, each with its ``dir`` name and every known id."""
    return list(load_general(zone)["encounters"])


def encounter_dir(zone: str, slug: str) -> pathlib.Path:
    for enc in encounters(zone):
        if enc["slug"] == slug:
            return tier_dir(zone) / str(enc["dir"])
    raise SystemExit(f"encounter {slug!r} is not in {zone}'s general.json")


def write_encounter_file(
    zone: str, slug: str, relpath: str, meta: dict[str, Any], encounter: dict[str, Any]
) -> pathlib.Path:
    out = encounter_dir(zone, slug) / relpath
    out.parent.mkdir(parents=True, exist_ok=True)
    doc = {"meta": {**meta, "encounter": slug}, "encounter": encounter}
    out.write_text(json.dumps(doc, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    return out


def write_tier(zone: str, relpath: str, meta: dict[str, Any], rows: list[dict[str, Any]]) -> list[pathlib.Path]:
    """Write one per-encounter file per row (rows are keyed by their ``slug``)."""
    return [write_encounter_file(zone, row["slug"], relpath, meta, row) for row in rows]


def load_tier(zone: str, relpath: str) -> dict[str, Any] | None:
    """Every encounter's ``relpath`` file stitched into ``{"meta", "encounters"}``.

    ``meta`` is the first file's, minus its ``encounter`` key. Encounters with no such file
    are left out; ``None`` when no encounter has one.
    """
    meta: dict[str, Any] | None = None
    rows = []
    for enc in encounters(zone):
        path = tier_dir(zone) / enc["dir"] / relpath
        if not path.exists():
            continue
        doc = json.loads(path.read_text(encoding="utf-8"))
        if meta is None:
            meta = {k: v for k, v in doc["meta"].items() if k != "encounter"}
        rows.append(doc["encounter"])
    return None if meta is None else {"meta": meta, "encounters": rows}


def rel(path: pathlib.Path) -> str:
    """Repo-relative, forward-slashed -- what goes into a dataset's own ``meta``."""
    resolved = path.resolve()
    return resolved.relative_to(REPO).as_posix() if resolved.is_relative_to(REPO) else str(resolved)
