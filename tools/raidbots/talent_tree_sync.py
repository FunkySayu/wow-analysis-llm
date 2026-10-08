"""Talent tree data pipeline. See docs/design/22-talent-tree-pipeline.md.

Pulls one class/spec's talent tree from Raidbots' static feed, merges in PTR-correct
Wowhead tooltip text, normalises it into one JSON file the talent editor (task 43) can
render and the loadout codec (``site/backend/app/services/talent_codec.py``, task 20) can
decode against, and validates the result before writing it.

Sources (verbatim, not guessed -- see docs/design/22-talent-tree-pipeline.md "Source"):

    https://www.raidbots.com/static/data/live/talents.json   -- current live patch
    https://www.raidbots.com/static/data/ptr/talents.json    -- current PTR

Tooltip text -- the trap that fails silently (see docs/design/00-overview.md and the
wow-talent-data skill): Wowhead's tooltip endpoint serves *live* text by default. Only the
``/ptr/`` path segment returns PTR-correct text, with no error either way -- a PTR-redesigned
talent returns the old, wrong description with a clean HTTP 200. ``--branch`` controls which
path this tool uses, and the branch used is recorded in the output's ``meta.branch`` so a
consumer can tell which text it is looking at.

Doc fixes made while implementing this (see docs/design/22-talent-tree-pipeline.md, "Doc
fixes", and docs/design/PROGRESS.md for the one-line summary):

1. ``pointLevels`` does not exist anywhere in the Raidbots feed -- confirmed against a fresh
   fetch of both live and PTR talents.json (zero occurrences of the string in either 3.2MB
   file) and against an older captured dump in this repo (``data/talents/balance_druid_12.1.json``,
   since removed; it is in git history -- it already recorded it as ``null``). The design
   doc's instruction to "derive budgets from it" is therefore unsatisfiable as written.
   ``budgets`` here is instead derived from ``max_ranks``/``free`` on the nodes actually
   present (see ``_compute_budgets`` below), clearly documented as an approximation, not
   the authoritative in-game point cap.
2. The design doc's validation bullet "every id in full_node_order appears in exactly one
   tree" does not hold -- task 20 already discovered and documented this (see
   docs/design/talent-string-format.md, "fullNodeOrder spans the whole class, not just one
   spec"): a Druid spec's 282-entry fullNodeOrder spans all four specs' nodes plus 2 ids
   (91046, 91047) with no definition anywhere in the feed. This tool's output only carries
   one spec's own ~120 nodes, so most of full_node_order's ids are expected to resolve to
   nothing in ``trees`` at all. The corrected check (``_validate_full_node_order_membership``)
   only requires that ids which *do* belong to this spec's own node groups resolve to
   exactly one tree, never zero or two.
3. Raw nodes carry a ``freeNode`` flag (granted without spending a point) that the design
   doc's node shape had no field for, and the hero-subtree-picker node (type ``subtree``)
   has the same "doesn't cost a point" property despite not being flagged ``freeNode`` in
   the raw feed. Added a ``free: bool`` field to the node shape (see ``_schema.json``) so
   ``budgets`` (which excludes free ranks) is auditable from the node list alone rather than
   silently baking that exclusion into an opaque number.
4. Two raw entry shapes exist under one node type: the hero-subtree-picker node's entries
   (Elune's Chosen / Keeper of the Grove, etc.) have no ``spellId``/``icon`` at all -- they
   select a subtree, not a spell. ``entry.spell_id`` is therefore nullable, and such an
   entry's ``description`` is synthesised locally ("Commit to the <name> hero talent tree.")
   rather than fetched, since there is no spell to fetch a tooltip for.
5. No field in the feed carries a patch/version string, so ``meta.patch`` is operator-supplied
   via ``--patch`` (defaulted to the project's currently-tracked patch), not derived.

Everything else in the design doc's field list, node shape and validation list matched the
feed as fetched.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
import time
import urllib.error
import urllib.request
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Literal, cast

REPO_ROOT = Path(__file__).resolve().parents[2]
CACHE_DIR = REPO_ROOT / ".talent_tree_cache"
SCHEMA_PATH = REPO_ROOT / "data" / "classes" / "talents.schema.json"

Branch = Literal["live", "ptr"]
BRANCHES: tuple[Branch, ...] = ("live", "ptr")

FEED_URLS: dict[Branch, str] = {
    "live": "https://www.raidbots.com/static/data/live/talents.json",
    "ptr": "https://www.raidbots.com/static/data/ptr/talents.json",
}
TOOLTIP_URL_TEMPLATES: dict[Branch, str] = {
    "live": "https://nether.wowhead.com/tooltip/spell/{spell_id}",
    "ptr": "https://nether.wowhead.com/ptr/tooltip/spell/{spell_id}",
}
ICON_URL_TEMPLATE = "https://wow.zamimg.com/images/wow/icons/medium/{icon}.jpg"

# The doc's validation bullet "every entry has a non-empty description" is unconditional --
# kept at 0 tolerance rather than a soft threshold. Each fetch is retried a few times first
# (see _fetch_tooltip_text) so a single transient Wowhead hiccup doesn't need this at all;
# raise this only if real-world flakiness makes that retry insufficient.
MAX_TOOLTIP_FETCH_FAILURES = 0
TOOLTIP_FETCH_RETRIES = 3
TOOLTIP_FETCH_RETRY_DELAY_SECONDS = 1.0

DEFAULT_PATCH = "12.1"  # operator-supplied default; see module docstring, doc fix 5.


class TalentTreeSyncError(Exception):
    """Raised for any validation failure. The CLI must not write a partial file."""


# ---------------------------------------------------------------------------------
# Raw feed shapes (post-parse, pre-normalisation)
# ---------------------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class RawEntry:
    id: int
    name: str
    type: str
    max_ranks: int
    spell_id: int | None
    icon: str


@dataclass(frozen=True, slots=True)
class RawNode:
    id: int
    name: str
    type: str
    pos_x: int
    pos_y: int
    max_ranks: int
    req_points: int | None
    entry_node: bool
    free: bool
    prev: tuple[int, ...]
    next: tuple[int, ...]
    entries: tuple[RawEntry, ...]


def _parse_entry(raw: dict[str, Any]) -> RawEntry:
    return RawEntry(
        id=int(raw["id"]),
        name=str(raw["name"]),
        type=str(raw["type"]),
        max_ranks=int(raw.get("maxRanks", 1)),
        spell_id=int(raw["spellId"]) if "spellId" in raw and raw["spellId"] is not None else None,
        icon=str(raw.get("icon", "")),
    )


def _parse_node(raw: dict[str, Any]) -> RawNode:
    node_type = str(raw["type"])
    entries = tuple(_parse_entry(e) for e in raw.get("entries", []))
    # The hero-subtree-picker node in `subTreeNodes[0]` uses a different entry shape
    # (traitSubTreeId/nodes[] instead of spellId/icon) -- normalise it into the same
    # RawEntry shape here so downstream code never special-cases it. See doc fix 4.
    if node_type == "subtree" and not entries:
        entries = tuple(
            RawEntry(
                id=int(e["id"]),
                name=str(e["name"]),
                type=str(e["type"]),
                max_ranks=1,
                spell_id=None,
                icon="",
            )
            for e in raw.get("entries", [])
        )
    return RawNode(
        id=int(raw["id"]),
        name=str(raw["name"]),
        type=node_type,
        pos_x=int(raw["posX"]),
        pos_y=int(raw["posY"]),
        # The subtree-picker node carries no maxRanks in the raw feed at all; default to 1
        # (it is always a single, unranked "commit to this subtree" pick). Confirmed
        # consistent with task 20's own fixture (site/shared/fixtures/loadout_strings.json),
        # which recorded the same node (id 99808 for Balance) as max_ranks=1.
        max_ranks=int(raw.get("maxRanks", 1)),
        req_points=int(raw["reqPoints"]) if raw.get("reqPoints") is not None else None,
        entry_node=bool(raw.get("entryNode", False)),
        # `free`: raw `freeNode`, or a subtree-picker node -- see doc fix 3.
        free=bool(raw.get("freeNode", False)) or node_type == "subtree",
        prev=tuple(int(x) for x in raw.get("prev", [])),
        next=tuple(int(x) for x in raw.get("next", [])),
        entries=entries,
    )


# ---------------------------------------------------------------------------------
# Network + cache
# ---------------------------------------------------------------------------------


def _iso_now() -> str:
    return datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")


def _http_get(url: str, *, method: str = "GET", timeout: float = 30.0) -> tuple[int, bytes]:
    request = urllib.request.Request(url, method=method, headers={"User-Agent": "wow-analysis-talent-tree-sync/1.0"})
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            return int(response.status), cast(bytes, response.read())
    except urllib.error.HTTPError as exc:
        return exc.code, b""


def fetch_feed_bytes(branch: Branch, *, use_cache: bool, cache_dir: Path = CACHE_DIR) -> tuple[bytes, str]:
    """Fetch the raw talents.json for ``branch``. Returns ``(raw_bytes, fetched_at)``.

    Cached to disk keyed by branch so a warm rerun makes zero network requests (see the
    "byte-identical rerun" acceptance criterion) -- ``fetched_at`` is the timestamp of the
    original fetch, replayed from cache, so it stays stable across reruns rather than
    reading "now" every time.
    """
    cache_file = cache_dir / branch / "talents.json"
    meta_file = cache_dir / branch / "talents.meta.json"
    if use_cache and cache_file.exists() and meta_file.exists():
        cached_meta = json.loads(meta_file.read_text(encoding="utf-8"))
        return cache_file.read_bytes(), str(cached_meta["fetched_at"])

    status, raw = _http_get(FEED_URLS[branch])
    if status != 200:
        raise TalentTreeSyncError(f"GET {FEED_URLS[branch]} returned HTTP {status}, expected 200")
    # HTTP 200 is not proof of correct data (see docs/design/00-overview.md) -- a minimal
    # shape check so a redirect-to-an-HTML-error-page doesn't silently pass as "the feed".
    if not raw.lstrip().startswith(b"["):
        raise TalentTreeSyncError(f"GET {FEED_URLS[branch]} returned HTTP 200 but the body isn't a JSON array")

    fetched_at = _iso_now()
    cache_file.parent.mkdir(parents=True, exist_ok=True)
    cache_file.write_bytes(raw)
    meta_file.write_text(json.dumps({"fetched_at": fetched_at}), encoding="utf-8")
    return raw, fetched_at


class TooltipFetchError(Exception):
    def __init__(self, spell_id: int, reason: str) -> None:
        self.spell_id = spell_id
        self.reason = reason
        super().__init__(f"spell {spell_id}: {reason}")


def _strip_tooltip_html(html: str) -> str:
    text = re.sub(r"<br\s*/?>", "\n", html)
    text = re.sub(r"<[^>]+>", "", text)
    text = text.replace("\\/", "/").replace('\\"', '"').replace("&nbsp;", " ")
    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


def fetch_tooltip_text(
    spell_id: int,
    branch: Branch,
    *,
    use_cache: bool,
    cache_dir: Path = CACHE_DIR,
    retries: int = TOOLTIP_FETCH_RETRIES,
) -> str:
    """Fetch and plain-text-ify one spell's Wowhead tooltip, cached to disk.

    Cache key is ``(branch, spellId)`` per docs/design/22-talent-tree-pipeline.md, so
    adding one new talent to the tree doesn't re-fetch the other ~129.
    """
    cache_file = cache_dir / branch / "tooltips" / f"{spell_id}.txt"
    if use_cache and cache_file.exists():
        return cache_file.read_text(encoding="utf-8")

    url = TOOLTIP_URL_TEMPLATES[branch].format(spell_id=spell_id)
    last_error = ""
    for attempt in range(retries):
        status, raw = _http_get(url)
        if status == 200 and raw:
            try:
                payload = json.loads(raw)
            except json.JSONDecodeError as exc:
                last_error = f"HTTP 200 but body isn't JSON: {exc}"
            else:
                tooltip_html = payload.get("tooltip", "")
                text = _strip_tooltip_html(tooltip_html)
                if text:
                    cache_file.parent.mkdir(parents=True, exist_ok=True)
                    cache_file.write_text(text, encoding="utf-8")
                    return text
                last_error = "HTTP 200 but tooltip field was empty after stripping HTML"
        else:
            last_error = f"HTTP {status}"
        if attempt + 1 < retries:
            time.sleep(TOOLTIP_FETCH_RETRY_DELAY_SECONDS)
    raise TooltipFetchError(spell_id, last_error)


def check_icon_url(icon: str) -> bool:
    """HEAD the medium-icon URL for ``icon``. Returns True if it resolves (not a 404)."""
    if not icon:
        return False
    status, _ = _http_get(ICON_URL_TEMPLATE.format(icon=icon), method="HEAD")
    return status == 200


# ---------------------------------------------------------------------------------
# Selecting + splitting the raw feed
# ---------------------------------------------------------------------------------


def select_spec_entry(feed: list[dict[str, Any]], class_id: int, spec_id: int) -> dict[str, Any]:
    matches = [e for e in feed if e.get("classId") == class_id and e.get("specId") == spec_id]
    if not matches:
        available = sorted((e["classId"], e["specId"]) for e in feed)
        raise TalentTreeSyncError(f"no entry for classId={class_id} specId={spec_id}; available: {available}")
    if len(matches) > 1:
        raise TalentTreeSyncError(f"multiple entries for classId={class_id} specId={spec_id}")
    return matches[0]


def _slugify(name: str) -> str:
    slug = name.lower().replace("'", "")
    slug = re.sub(r"[^a-z0-9]+", "-", slug).strip("-")
    return slug


@dataclass(frozen=True, slots=True)
class HeroSubtree:
    slug: str
    name: str
    sub_tree_id: int
    node_ids: tuple[int, ...]


def split_hero_subtrees(spec_entry: dict[str, Any]) -> tuple[HeroSubtree, ...]:
    """Split heroNodes into its (undifferentiated in the raw feed) subtrees.

    Per docs/design/22-talent-tree-pipeline.md: use ``subTreeNodes[0].entries[]``, each of
    which lists its member node ids in ``.nodes[]``.
    """
    subtree_nodes = spec_entry.get("subTreeNodes") or []
    if len(subtree_nodes) != 1:
        raise TalentTreeSyncError(f"expected exactly one subTreeNodes selector, found {len(subtree_nodes)}")
    subtrees = []
    for entry in subtree_nodes[0]["entries"]:
        subtrees.append(
            HeroSubtree(
                slug=_slugify(entry["name"]),
                name=str(entry["name"]),
                sub_tree_id=int(entry["traitSubTreeId"]),
                node_ids=tuple(int(n) for n in entry["nodes"]),
            )
        )
    return tuple(subtrees)


def find_apex_node_id(spec_nodes: list[RawNode]) -> int:
    """The apex talent: highest reqPoints, type 'tiered', entries' icon contains 'apextalent'.

    Per docs/design/22-talent-tree-pipeline.md: lives in specNodes. The icon string does not
    change when the talent is redesigned, so it identifies the *node*, not the current name.
    """
    candidates = [
        n
        for n in spec_nodes
        if n.type == "tiered" and any("apextalent" in e.icon for e in n.entries)
    ]
    if not candidates:
        raise TalentTreeSyncError("no apex talent candidate found in specNodes (type=tiered, icon has 'apextalent')")
    candidates.sort(key=lambda n: n.req_points or 0, reverse=True)
    return candidates[0].id


# ---------------------------------------------------------------------------------
# Grid coordinates
# ---------------------------------------------------------------------------------


def assign_grid_coords(nodes: list[RawNode]) -> dict[int, tuple[int, int]]:
    """Map each node's (posX, posY) to 0-based (col, row) indices.

    Per docs/design/22-talent-tree-pipeline.md: collect the distinct values per tree, sort
    them, and map to indices -- not a hardcoded divisor, since posX/posY spacing has no
    documented fixed step and a future tree with half-step positions would silently break one.
    """
    xs = sorted({n.pos_x for n in nodes})
    ys = sorted({n.pos_y for n in nodes})
    col_of = {x: i for i, x in enumerate(xs)}
    row_of = {y: i for i, y in enumerate(ys)}
    return {n.id: (col_of[n.pos_x], row_of[n.pos_y]) for n in nodes}


# ---------------------------------------------------------------------------------
# Building the output document
# ---------------------------------------------------------------------------------


@dataclass
class _FetchFailures:
    spell_ids: list[int] = field(default_factory=list)


def _build_entry_json(
    entry: RawEntry,
    node: RawNode,
    *,
    branch: Branch,
    use_cache: bool,
    cache_dir: Path,
    failures: _FetchFailures,
) -> dict[str, Any]:
    if entry.spell_id is None:
        # Hero-subtree-picker entry -- no spell to fetch a tooltip for. See doc fix 4.
        description = f"Commit to the {entry.name} hero talent tree."
    else:
        try:
            description = fetch_tooltip_text(entry.spell_id, branch, use_cache=use_cache, cache_dir=cache_dir)
        except TooltipFetchError as exc:
            failures.spell_ids.append(exc.spell_id)
            description = ""
    return {
        "id": entry.id,
        "spell_id": entry.spell_id,
        "name": entry.name,
        "icon": entry.icon,
        "type": entry.type,
        "max_ranks": entry.max_ranks,
        "description": description,
    }


def _build_node_json(
    node: RawNode,
    *,
    apex_id: int,
    grid: dict[int, tuple[int, int]],
    branch: Branch,
    use_cache: bool,
    cache_dir: Path,
    failures: _FetchFailures,
) -> dict[str, Any]:
    col, row = grid[node.id]
    return {
        "id": node.id,
        "name": node.name,
        "type": node.type,
        "x": node.pos_x,
        "y": node.pos_y,
        "col": col,
        "row": row,
        "max_ranks": node.max_ranks,
        "req_points": node.req_points,
        "entry_node": node.entry_node,
        "is_apex": node.id == apex_id,
        "free": node.free,
        "prev": list(node.prev),
        "next": list(node.next),
        "entries": [
            _build_entry_json(e, node, branch=branch, use_cache=use_cache, cache_dir=cache_dir, failures=failures)
            for e in node.entries
        ],
    }


def _compute_budgets(trees: dict[str, Any]) -> dict[str, int]:
    """Derive a best-effort point budget per tree. See module docstring, doc fix 1.

    class/spec: sum of max_ranks over every non-free node in the tree -- the cost to
    acquire literally everything the tree offers (a real upper bound: reqPoints gates in
    this feed are cumulative thresholds on a single shared path, not a fork you must choose
    between, so this is achievable by one hypothetical character, unlike hero below).

    hero: hero subtrees genuinely fork -- a character can only ever be in one subtree, so
    summing across both (as the class/spec formula would) overcounts by roughly 2x. Instead
    take the max, across subtrees, of that subtree's own non-free max_ranks sum.
    """

    def non_free_sum(nodes: list[dict[str, Any]]) -> int:
        return sum(n["max_ranks"] for n in nodes if not n["free"])

    class_budget = non_free_sum(trees["class"]["nodes"])
    spec_budget = non_free_sum(trees["spec"]["nodes"])

    hero_nodes_by_id = {n["id"]: n for n in trees["hero"]["nodes"]}
    hero_budget = 0
    for subtree in trees["hero"]["subtrees"]:
        subtree_nodes = [hero_nodes_by_id[nid] for nid in subtree["node_ids"]]
        hero_budget = max(hero_budget, non_free_sum(subtree_nodes))

    return {"class": class_budget, "spec": spec_budget, "hero": hero_budget}


def build_document(
    class_id: int,
    spec_id: int,
    branch: Branch,
    *,
    patch: str | None,
    use_cache: bool,
    cache_dir: Path = CACHE_DIR,
) -> dict[str, Any]:
    raw_bytes, fetched_at = fetch_feed_bytes(branch, use_cache=use_cache, cache_dir=cache_dir)
    source_sha256 = hashlib.sha256(raw_bytes).hexdigest()
    feed = json.loads(raw_bytes)

    spec_entry = select_spec_entry(feed, class_id, spec_id)
    class_nodes = [_parse_node(n) for n in spec_entry["classNodes"]]
    spec_nodes = [_parse_node(n) for n in spec_entry["specNodes"]]
    hero_nodes = [_parse_node(n) for n in spec_entry["heroNodes"]]
    subtree_selector_raw = spec_entry["subTreeNodes"][0]
    subtree_selector = _parse_node(subtree_selector_raw)
    subtrees = split_hero_subtrees(spec_entry)
    hero_node_ids = {n.id for n in hero_nodes}

    apex_id = find_apex_node_id(spec_nodes)

    grid = {
        **assign_grid_coords(class_nodes),
        **assign_grid_coords(spec_nodes),
        **assign_grid_coords([*hero_nodes, subtree_selector]),
    }

    failures = _FetchFailures()
    trees: dict[str, Any] = {
        "class": {
            "nodes": [
                _build_node_json(
                    n,
                    apex_id=apex_id,
                    grid=grid,
                    branch=branch,
                    use_cache=use_cache,
                    cache_dir=cache_dir,
                    failures=failures,
                )
                for n in class_nodes
            ]
        },
        "spec": {
            "nodes": [
                _build_node_json(
                    n,
                    apex_id=apex_id,
                    grid=grid,
                    branch=branch,
                    use_cache=use_cache,
                    cache_dir=cache_dir,
                    failures=failures,
                )
                for n in spec_nodes
            ]
        },
        "hero": {
            "subtrees": [
                {
                    "slug": st.slug,
                    "name": st.name,
                    "sub_tree_id": st.sub_tree_id,
                    # The feed's subtree lists can name a node with no definition in
                    # heroNodes (Frostfire: 94636 on Fire, 109956 on Frost, as of
                    # 2026-10-08). Keep them out of node_ids so every id resolves, but
                    # record them so the omission is visible rather than silent.
                    "node_ids": [nid for nid in st.node_ids if nid in hero_node_ids],
                    "undefined_node_ids": [nid for nid in st.node_ids if nid not in hero_node_ids],
                }
                for st in subtrees
            ],
            "nodes": [
                _build_node_json(
                    n,
                    apex_id=apex_id,
                    grid=grid,
                    branch=branch,
                    use_cache=use_cache,
                    cache_dir=cache_dir,
                    failures=failures,
                )
                for n in [*hero_nodes, subtree_selector]
            ],
        },
    }

    if failures.spell_ids and len(failures.spell_ids) > MAX_TOOLTIP_FETCH_FAILURES:
        raise TalentTreeSyncError(
            f"{len(failures.spell_ids)} tooltip fetch(es) failed permanently after "
            f"{TOOLTIP_FETCH_RETRIES} attempts each (max tolerated: {MAX_TOOLTIP_FETCH_FAILURES}): "
            f"spellIds={sorted(failures.spell_ids)}"
        )

    doc: dict[str, Any] = {
        "meta": {
            "branch": branch,
            "patch": patch,
            "fetched_at": fetched_at,
            "source_sha256": source_sha256,
            "trait_tree_id": int(spec_entry["traitTreeId"]),
        },
        "spec": {
            "slug": f"{_slugify(spec_entry['specName'])}-{_slugify(spec_entry['className'])}",
            "class_id": class_id,
            "spec_id": spec_id,
            "class_name": spec_entry["className"],
            "spec_name": spec_entry["specName"],
        },
        "budgets": _compute_budgets(trees),
        "full_node_order": list(spec_entry["fullNodeOrder"]),
        "trees": trees,
    }
    return doc


# ---------------------------------------------------------------------------------
# Validation
# ---------------------------------------------------------------------------------


def _all_tree_nodes(doc: dict[str, Any]) -> dict[str, list[dict[str, Any]]]:
    return {
        "class": doc["trees"]["class"]["nodes"],
        "spec": doc["trees"]["spec"]["nodes"],
        "hero": doc["trees"]["hero"]["nodes"],
    }


def validate_full_node_order_membership(doc: dict[str, Any]) -> list[str]:
    """Corrected per doc fix 2: only ids that belong to *this spec's own* trees must be
    unique across them -- most of full_node_order belongs to other specs sharing the same
    traitTreeId and is expected to resolve to nothing here at all."""
    problems: list[str] = []
    by_tree = _all_tree_nodes(doc)
    seen_in: dict[int, list[str]] = {}
    for tree_name, nodes in by_tree.items():
        for node in nodes:
            seen_in.setdefault(node["id"], []).append(tree_name)
    for node_id, tree_names in seen_in.items():
        if len(tree_names) > 1:
            problems.append(f"node {node_id} appears in more than one tree: {tree_names}")
    return problems


def validate_edges_resolve(doc: dict[str, Any]) -> list[str]:
    problems: list[str] = []
    for tree_name, nodes in _all_tree_nodes(doc).items():
        ids = {n["id"] for n in nodes}
        for node in nodes:
            for edge_id in [*node["prev"], *node["next"]]:
                if edge_id not in ids:
                    problems.append(
                        f"{tree_name} node {node['id']}: edge to {edge_id} does not resolve within {tree_name}"
                    )
    return problems


def validate_hero_subtree_partition(doc: dict[str, Any]) -> list[str]:
    problems: list[str] = []
    hero = doc["trees"]["hero"]
    proper_hero_ids = {n["id"] for n in hero["nodes"] if n["type"] != "subtree"}
    seen: set[int] = set()
    for subtree in hero["subtrees"]:
        node_ids = set(subtree["node_ids"])
        overlap = seen & node_ids
        if overlap:
            problems.append(f"hero subtree {subtree['slug']!r} overlaps another subtree on ids {sorted(overlap)}")
        seen |= node_ids
    leftover = proper_hero_ids - seen
    if leftover:
        problems.append(f"hero nodes not claimed by any subtree: {sorted(leftover)}")
    extra = seen - proper_hero_ids
    if extra:
        problems.append(f"subtree node_ids reference ids not present in hero.nodes: {sorted(extra)}")
    return problems


def validate_single_apex(doc: dict[str, Any]) -> list[str]:
    apex_ids = [n["id"] for nodes in _all_tree_nodes(doc).values() for n in nodes if n["is_apex"]]
    if len(apex_ids) != 1:
        return [f"expected exactly one is_apex node, found {len(apex_ids)}: {apex_ids}"]
    return []


def validate_descriptions_present(doc: dict[str, Any]) -> list[str]:
    problems: list[str] = []
    for tree_name, nodes in _all_tree_nodes(doc).items():
        for node in nodes:
            for entry in node["entries"]:
                if not entry["description"]:
                    problems.append(f"{tree_name} node {node['id']} entry {entry['id']} has an empty description")
    return problems


def validate_budgets_consistent(doc: dict[str, Any]) -> list[str]:
    recomputed = _compute_budgets(doc["trees"])
    if recomputed != doc["budgets"]:
        return [f"budgets {doc['budgets']} does not match recomputed {recomputed}"]
    return []


VALIDATORS: tuple[Any, ...] = (
    validate_full_node_order_membership,
    validate_edges_resolve,
    validate_hero_subtree_partition,
    validate_single_apex,
    validate_descriptions_present,
    validate_budgets_consistent,
)


def validate_document(doc: dict[str, Any]) -> None:
    """Run every validator; raise with every problem found (not just the first)."""
    problems: list[str] = []
    for validator in VALIDATORS:
        problems.extend(validator(doc))
    if problems:
        joined = "\n  - ".join(problems)
        raise TalentTreeSyncError(f"{len(problems)} validation problem(s):\n  - {joined}")


# ---------------------------------------------------------------------------------
# JSON Schema validation (no third-party dependency -- see _schema.json's own description)
# ---------------------------------------------------------------------------------


def load_schema(path: Path = SCHEMA_PATH) -> dict[str, Any]:
    with path.open(encoding="utf-8") as f:
        return cast(dict[str, Any], json.load(f))


def _resolve_ref(ref: str, root: dict[str, Any]) -> dict[str, Any]:
    assert ref.startswith("#/")
    node: Any = root
    for part in ref[2:].split("/"):
        node = node[part]
    return cast(dict[str, Any], node)


def _validate_schema_node(
    value: Any, schema: dict[str, Any], root: dict[str, Any], path: str, problems: list[str]
) -> None:
    if "$ref" in schema:
        _validate_schema_node(value, _resolve_ref(schema["$ref"], root), root, path, problems)
        return

    expected_types = schema.get("type")
    if expected_types is not None:
        types = [expected_types] if isinstance(expected_types, str) else expected_types
        if not _matches_any_type(value, types):
            problems.append(f"{path}: expected type in {types}, got {type(value).__name__}")
            return

    if "enum" in schema and value not in schema["enum"]:
        problems.append(f"{path}: {value!r} not in enum {schema['enum']}")

    if isinstance(value, str):
        if "minLength" in schema and len(value) < schema["minLength"]:
            problems.append(f"{path}: string shorter than minLength {schema['minLength']}")
        if "pattern" in schema and not re.match(schema["pattern"], value):
            problems.append(f"{path}: {value!r} does not match pattern {schema['pattern']}")

    if isinstance(value, int) and not isinstance(value, bool) and "minimum" in schema and value < schema["minimum"]:
        problems.append(f"{path}: {value} below minimum {schema['minimum']}")

    if isinstance(value, list):
        if "minItems" in schema and len(value) < schema["minItems"]:
            problems.append(f"{path}: array shorter than minItems {schema['minItems']}")
        item_schema = schema.get("items")
        if item_schema is not None:
            for i, item in enumerate(value):
                _validate_schema_node(item, item_schema, root, f"{path}[{i}]", problems)

    if isinstance(value, dict):
        required = schema.get("required", [])
        for key in required:
            if key not in value:
                problems.append(f"{path}: missing required key {key!r}")
        properties = schema.get("properties", {})
        if schema.get("additionalProperties") is False:
            for key in value:
                if key not in properties:
                    problems.append(f"{path}: unexpected key {key!r}")
        for key, sub_schema in properties.items():
            if key in value:
                _validate_schema_node(value[key], sub_schema, root, f"{path}.{key}", problems)


def _matches_any_type(value: Any, types: list[str]) -> bool:
    for t in types:
        if t == "null" and value is None:
            return True
        if t == "string" and isinstance(value, str):
            return True
        if t == "integer" and isinstance(value, int) and not isinstance(value, bool):
            return True
        if t == "number" and isinstance(value, int | float) and not isinstance(value, bool):
            return True
        if t == "boolean" and isinstance(value, bool):
            return True
        if t == "array" and isinstance(value, list):
            return True
        if t == "object" and isinstance(value, dict):
            return True
    return False


def validate_against_schema(doc: dict[str, Any], schema: dict[str, Any]) -> list[str]:
    problems: list[str] = []
    _validate_schema_node(doc, schema, schema, "$", problems)
    return problems


# ---------------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------------


def list_class_specs(branch: Branch = "live", *, use_cache: bool = True) -> list[tuple[int, int, str, str]]:
    raw, _ = fetch_feed_bytes(branch, use_cache=use_cache)
    feed = json.loads(raw)
    return sorted((e["classId"], e["specId"], e["className"], e["specName"]) for e in feed)


def run_check_icons(doc: dict[str, Any]) -> list[str]:
    icons = {e["icon"] for nodes in _all_tree_nodes(doc).values() for n in nodes for e in n["entries"] if e["icon"]}
    missing = []
    for icon in sorted(icons):
        if not check_icon_url(icon):
            missing.append(icon)
    return missing


def _build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0] if __doc__ else "")
    parser.add_argument("--class", dest="class_id", type=int, help="Raidbots classId")
    parser.add_argument("--spec", dest="spec_id", type=int, help="Raidbots specId")
    parser.add_argument("--branch", choices=BRANCHES, default="live")
    parser.add_argument("--patch", default=DEFAULT_PATCH, help="Operator-supplied; not derivable from the feed")
    parser.add_argument("--out", type=Path, help="Output path, e.g. data/classes/druid/balance/12_1_talents.json")
    parser.add_argument("--check-icons", action="store_true")
    parser.add_argument("--no-cache", action="store_true")
    parser.add_argument("--list", action="store_true", help="Print all classId/specId pairs and exit")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = _build_arg_parser().parse_args(argv)

    if args.list:
        for class_id, spec_id, class_name, spec_name in list_class_specs(use_cache=not args.no_cache):
            print(f"{class_id}/{spec_id} {class_name} - {spec_name}")
        return 0

    if args.class_id is None or args.spec_id is None or args.out is None:
        print("--class, --spec and --out are required (or use --list)", file=sys.stderr)
        return 2

    try:
        doc = build_document(
            args.class_id,
            args.spec_id,
            args.branch,
            patch=args.patch,
            use_cache=not args.no_cache,
        )
        validate_document(doc)
        schema_problems = validate_against_schema(doc, load_schema())
        if schema_problems:
            raise TalentTreeSyncError("schema validation failed:\n  - " + "\n  - ".join(schema_problems))
    except TalentTreeSyncError as exc:
        print(f"talent_tree_sync: {exc}", file=sys.stderr)
        return 1

    if args.check_icons:
        missing = run_check_icons(doc)
        if missing:
            print(f"talent_tree_sync: {len(missing)} icon(s) HEAD as non-200: {missing}", file=sys.stderr)

    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(doc, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(f"wrote {args.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
