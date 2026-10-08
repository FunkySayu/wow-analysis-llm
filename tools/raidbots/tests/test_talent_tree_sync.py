"""Tests for tools/raidbots/talent_tree_sync.py. See docs/design/22-talent-tree-pipeline.md.

Covers every bullet in that doc's "Acceptance criteria" plus the "Doc fixes" made while
implementing it. Two tests (`test_real_file_*`) require the checked-in
``data/classes/druid/balance/12_1_talents.json`` to exist -- run
``python tools/raidbots/talent_tree_sync.py --class 11 --spec 102 --out data/classes/druid/balance/12_1_talents.json``
first if it's missing.
"""

from __future__ import annotations

import copy
import json
from pathlib import Path
from typing import Any

import pytest
import talent_tree_sync as sync

REPO_ROOT = Path(__file__).resolve().parents[3]
REAL_OUTPUT_PATH = REPO_ROOT / "data" / "classes" / "druid" / "balance" / "12_1_talents.json"
SCHEMA_PATH = REPO_ROOT / "data" / "classes" / "talents.schema.json"
TASK20_FIXTURE_PATH = REPO_ROOT / "site" / "shared" / "fixtures" / "loadout_strings.json"


# ---------------------------------------------------------------------------------
# A minimal, hand-built, internally-consistent doc -- deliberately tiny (a handful of
# nodes, not a real 120-node tree) so each corruption test below can mutate exactly one
# thing and stay obviously correct.
# ---------------------------------------------------------------------------------


def _entry(
    entry_id: int, spell_id: int | None, name: str, *, icon: str = "icon", description: str = "Deals damage."
) -> dict[str, Any]:
    return {
        "id": entry_id,
        "spell_id": spell_id,
        "name": name,
        "icon": icon,
        "type": "active",
        "max_ranks": 1,
        "description": description,
    }


def _node(
    node_id: int,
    name: str,
    *,
    node_type: str = "single",
    req_points: int | None = None,
    entry_node: bool = False,
    is_apex: bool = False,
    free: bool = False,
    max_ranks: int = 1,
    prev: list[int] | None = None,
    next_: list[int] | None = None,
    entries: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    return {
        "id": node_id,
        "name": name,
        "type": node_type,
        "x": node_id * 100,
        "y": 0,
        "col": node_id,
        "row": 0,
        "max_ranks": max_ranks,
        "req_points": req_points,
        "entry_node": entry_node,
        "is_apex": is_apex,
        "free": free,
        "prev": prev or [],
        "next": next_ or [],
        "entries": entries if entries is not None else [_entry(node_id * 10, node_id * 100, name)],
    }


def _minimal_trees() -> dict[str, Any]:
    class_nodes = [
        _node(1, "Class Entry", entry_node=True, next_=[2]),
        _node(2, "Class Gated", req_points=5, prev=[1]),
    ]
    spec_nodes = [
        _node(3, "Spec Entry", entry_node=True, next_=[4]),
        _node(
            4,
            "Apex Talent",
            node_type="tiered",
            req_points=5,
            prev=[3],
            max_ranks=3,
            is_apex=True,
            entries=[_entry(40, 400, "Apex Talent", icon="inv_apextalent_test")],
        ),
    ]
    hero_nodes = [
        _node(5, "Elunes Pick"),
        _node(6, "Keepers Pick"),
        _node(
            99,
            "Elune's Chosen / Keeper of the Grove",
            node_type="subtree",
            free=True,
            entries=[
                _entry(
                    991, None, "Elune's Chosen", icon="",
                    description="Commit to the Elune's Chosen hero talent tree.",
                ),
                _entry(
                    992, None, "Keeper of the Grove", icon="",
                    description="Commit to the Keeper of the Grove hero talent tree.",
                ),
            ],
        ),
    ]
    return {
        "class": {"nodes": class_nodes},
        "spec": {"nodes": spec_nodes},
        "hero": {
            "subtrees": [
                {"slug": "elunes-chosen", "name": "Elune's Chosen", "sub_tree_id": 24, "node_ids": [5]},
                {"slug": "keeper-of-the-grove", "name": "Keeper of the Grove", "sub_tree_id": 23, "node_ids": [6]},
            ],
            "nodes": hero_nodes,
        },
    }


def _minimal_doc() -> dict[str, Any]:
    trees = _minimal_trees()
    return {
        "meta": {
            "branch": "live",
            "patch": "12.1",
            "fetched_at": "2026-01-01T00:00:00Z",
            "source_sha256": "a" * 64,
            "trait_tree_id": 793,
        },
        "spec": {"slug": "test-spec", "class_id": 99, "spec_id": 1, "class_name": "Test", "spec_name": "Spec"},
        "budgets": sync._compute_budgets(trees),
        # 12345 stands in for a node belonging to another spec sharing the same traitTreeId
        # -- present in full_node_order but absent from every tree here. See doc fix 2.
        "full_node_order": [1, 2, 3, 4, 5, 6, 99, 12345],
        "trees": trees,
    }


@pytest.fixture
def valid_doc() -> dict[str, Any]:
    return _minimal_doc()


@pytest.fixture(scope="session")
def schema() -> dict[str, Any]:
    return sync.load_schema(SCHEMA_PATH)


# --- baseline: the minimal doc is actually valid ------------------------------------


def test_minimal_doc_passes_all_validators(valid_doc: dict[str, Any]) -> None:
    sync.validate_document(valid_doc)  # must not raise


def test_minimal_doc_matches_schema(valid_doc: dict[str, Any], schema: dict[str, Any]) -> None:
    assert sync.validate_against_schema(valid_doc, schema) == []


# --- validate_full_node_order_membership (doc fix 2: corrected semantics) -----------


def test_full_node_order_membership_passes_when_ids_are_unique_per_tree(valid_doc: dict[str, Any]) -> None:
    assert sync.validate_full_node_order_membership(valid_doc) == []


def test_full_node_order_membership_trips_on_duplicate_across_trees(valid_doc: dict[str, Any]) -> None:
    corrupted = copy.deepcopy(valid_doc)
    # Node 2 (a real class node) also injected into the hero tree -> appears twice.
    corrupted["trees"]["hero"]["nodes"].append(_node(2, "Duplicate"))
    problems = sync.validate_full_node_order_membership(corrupted)
    assert any("2" in p and "more than one tree" in p for p in problems)


def test_full_node_order_membership_does_not_require_full_coverage(valid_doc: dict[str, Any]) -> None:
    """The corrected check: ids in full_node_order that belong to *other* specs (never
    appearing in any of this file's trees) are expected and must not trip anything."""
    corrupted = copy.deepcopy(valid_doc)
    corrupted["full_node_order"].extend([88888, 99999])  # more foreign ids, still fine
    assert sync.validate_full_node_order_membership(corrupted) == []


# --- validate_edges_resolve ----------------------------------------------------------


def test_edges_resolve_trips_on_dangling_edge(valid_doc: dict[str, Any]) -> None:
    corrupted = copy.deepcopy(valid_doc)
    corrupted["trees"]["class"]["nodes"][0]["next"] = [777]
    problems = sync.validate_edges_resolve(corrupted)
    assert any("777" in p for p in problems)


def test_edges_resolve_trips_when_edge_crosses_trees(valid_doc: dict[str, Any]) -> None:
    corrupted = copy.deepcopy(valid_doc)
    # Point a class node's edge at a real, but spec-tree, node id -- edges must resolve
    # *within* their own tree, per docs/design/22-talent-tree-pipeline.md.
    corrupted["trees"]["class"]["nodes"][0]["next"] = [3]
    problems = sync.validate_edges_resolve(corrupted)
    assert any("3" in p for p in problems)


# --- validate_hero_subtree_partition ---------------------------------------------------


def test_hero_subtree_partition_trips_on_overlap(valid_doc: dict[str, Any]) -> None:
    corrupted = copy.deepcopy(valid_doc)
    corrupted["trees"]["hero"]["subtrees"][1]["node_ids"] = [5, 6]  # 5 now claimed twice
    problems = sync.validate_hero_subtree_partition(corrupted)
    assert any("overlaps" in p for p in problems)


def test_hero_subtree_partition_trips_on_leftover(valid_doc: dict[str, Any]) -> None:
    corrupted = copy.deepcopy(valid_doc)
    corrupted["trees"]["hero"]["subtrees"][1]["node_ids"] = []  # node 6 now unclaimed
    problems = sync.validate_hero_subtree_partition(corrupted)
    assert any("not claimed" in p for p in problems)


# --- validate_single_apex -------------------------------------------------------------


def test_single_apex_trips_on_zero_apex_nodes(valid_doc: dict[str, Any]) -> None:
    corrupted = copy.deepcopy(valid_doc)
    corrupted["trees"]["spec"]["nodes"][1]["is_apex"] = False
    problems = sync.validate_single_apex(corrupted)
    assert any("found 0" in p for p in problems)


def test_single_apex_trips_on_two_apex_nodes(valid_doc: dict[str, Any]) -> None:
    corrupted = copy.deepcopy(valid_doc)
    corrupted["trees"]["class"]["nodes"][0]["is_apex"] = True
    problems = sync.validate_single_apex(corrupted)
    assert any("found 2" in p for p in problems)


# --- validate_descriptions_present -----------------------------------------------------


def test_descriptions_present_trips_on_empty_description(valid_doc: dict[str, Any]) -> None:
    corrupted = copy.deepcopy(valid_doc)
    corrupted["trees"]["spec"]["nodes"][1]["entries"][0]["description"] = ""
    problems = sync.validate_descriptions_present(corrupted)
    assert any("empty description" in p for p in problems)


# --- validate_budgets_consistent -------------------------------------------------------


def test_budgets_consistent_trips_on_mismatch(valid_doc: dict[str, Any]) -> None:
    corrupted = copy.deepcopy(valid_doc)
    corrupted["budgets"]["class"] += 1
    problems = sync.validate_budgets_consistent(corrupted)
    assert any("does not match recomputed" in p for p in problems)


def test_budgets_hero_uses_max_subtree_not_sum_of_both(valid_doc: dict[str, Any]) -> None:
    """doc fix 1: hero subtrees fork, so the derived hero budget must be the larger single
    subtree's non-free rank sum, not both subtrees added together."""
    trees = valid_doc["trees"]
    budgets = sync._compute_budgets(trees)
    # Both hero subtrees here have exactly one 1-rank, non-free node each -> max is 1, not 2.
    assert budgets["hero"] == 1


# --- schema validation (data-driven, not just the hard-coded checks above) -------------


def test_schema_trips_on_missing_required_key(valid_doc: dict[str, Any], schema: dict[str, Any]) -> None:
    corrupted = copy.deepcopy(valid_doc)
    del corrupted["meta"]["branch"]
    problems = sync.validate_against_schema(corrupted, schema)
    assert any("missing required key 'branch'" in p for p in problems)


def test_schema_trips_on_wrong_type(valid_doc: dict[str, Any], schema: dict[str, Any]) -> None:
    corrupted = copy.deepcopy(valid_doc)
    corrupted["spec"]["class_id"] = "99"  # should be an integer
    problems = sync.validate_against_schema(corrupted, schema)
    assert any("spec.class_id" in p for p in problems)


def test_schema_trips_on_unexpected_key(valid_doc: dict[str, Any], schema: dict[str, Any]) -> None:
    corrupted = copy.deepcopy(valid_doc)
    corrupted["spec"]["surprise"] = "unexpected"
    problems = sync.validate_against_schema(corrupted, schema)
    assert any("unexpected key 'surprise'" in p for p in problems)


def test_schema_trips_on_enum_violation(valid_doc: dict[str, Any], schema: dict[str, Any]) -> None:
    corrupted = copy.deepcopy(valid_doc)
    corrupted["meta"]["branch"] = "beta"
    problems = sync.validate_against_schema(corrupted, schema)
    assert any("not in enum" in p for p in problems)


# --- small pure-function unit tests -----------------------------------------------------


def test_slugify() -> None:
    assert sync._slugify("Elune's Chosen") == "elunes-chosen"
    assert sync._slugify("Keeper of the Grove") == "keeper-of-the-grove"
    assert sync._slugify("Balance") == "balance"


def test_strip_tooltip_html_handles_the_documented_transforms() -> None:
    raw = r'Line one<br />Line two<br>Line three &nbsp;end.<b>bold</b> a\/b a\"b'
    text = sync._strip_tooltip_html(raw)
    assert "Line one\nLine two\nLine three" in text
    assert "<b>" not in text and "</b>" not in text
    assert "a/b" in text
    assert 'a"b' in text


def test_assign_grid_coords_maps_distinct_positions_to_0_based_indices() -> None:
    nodes = [
        sync.RawNode(
            id=1, name="a", type="single", pos_x=2100, pos_y=1500, max_ranks=1, req_points=None,
            entry_node=True, free=False, prev=(), next=(), entries=(),
        ),
        sync.RawNode(
            id=2, name="b", type="single", pos_x=4200, pos_y=1500, max_ranks=1, req_points=None,
            entry_node=False, free=False, prev=(), next=(), entries=(),
        ),
        sync.RawNode(
            id=3, name="c", type="single", pos_x=2100, pos_y=3000, max_ranks=1, req_points=None,
            entry_node=False, free=False, prev=(), next=(), entries=(),
        ),
    ]
    grid = sync.assign_grid_coords(nodes)
    assert grid[1] == (0, 0)
    assert grid[2] == (1, 0)
    assert grid[3] == (0, 1)


def _raw_entry(entry_id: int, spell_id: int, icon: str, *, entry_type: str = "active") -> sync.RawEntry:
    return sync.RawEntry(id=entry_id, name="x", type=entry_type, max_ranks=1, spell_id=spell_id, icon=icon)


def _raw_node(
    node_id: int, *, node_type: str, req_points: int | None, max_ranks: int, entries: tuple[sync.RawEntry, ...]
) -> sync.RawNode:
    return sync.RawNode(
        id=node_id, name="n", type=node_type, pos_x=0, pos_y=0, max_ranks=max_ranks, req_points=req_points,
        entry_node=False, free=False, prev=(), next=(), entries=entries,
    )


def test_find_apex_node_id_picks_highest_req_points_tiered_apextalent_node() -> None:
    nodes = [
        _raw_node(
            1, node_type="tiered", req_points=3, max_ranks=1,
            entries=(_raw_entry(10, 100, "something_else", entry_type="tierrank"),),
        ),
        _raw_node(
            2, node_type="tiered", req_points=20, max_ranks=3,
            entries=(_raw_entry(20, 200, "inv_apextalent_thing", entry_type="tierrank"),),
        ),
        _raw_node(
            3, node_type="choice", req_points=20, max_ranks=1,
            entries=(_raw_entry(30, 300, "inv_apextalent_decoy"),),
        ),
    ]
    assert sync.find_apex_node_id(nodes) == 2


def test_split_hero_subtrees_reads_subtree_nodes_entries() -> None:
    spec_entry = {
        "subTreeNodes": [
            {
                "entries": [
                    {"traitSubTreeId": 24, "name": "Elune's Chosen", "nodes": [1, 2, 3]},
                    {"traitSubTreeId": 23, "name": "Keeper of the Grove", "nodes": [4, 5, 6]},
                ]
            }
        ]
    }
    subtrees = sync.split_hero_subtrees(spec_entry)
    assert subtrees[0].slug == "elunes-chosen"
    assert subtrees[0].sub_tree_id == 24
    assert subtrees[0].node_ids == (1, 2, 3)
    assert subtrees[1].slug == "keeper-of-the-grove"


# --- the Wowhead PTR trap: a regression test for the exact bug class CLAUDE.md warns about --


def test_ptr_branch_uses_the_ptr_tooltip_path_live_does_not() -> None:
    live_url = sync.TOOLTIP_URL_TEMPLATES["live"].format(spell_id=1243435)
    ptr_url = sync.TOOLTIP_URL_TEMPLATES["ptr"].format(spell_id=1243435)
    assert "/ptr/" not in live_url
    assert "/ptr/" in ptr_url
    assert live_url != ptr_url


# --- icon checking (--check-icons) -----------------------------------------------------


def test_check_icon_url_true_on_200_false_on_404(monkeypatch: pytest.MonkeyPatch) -> None:
    def fake_http_get(url: str, *, method: str = "GET", timeout: float = 30.0) -> tuple[int, bytes]:
        return (200, b"jpeg-bytes") if "good_icon" in url else (404, b"")

    monkeypatch.setattr(sync, "_http_get", fake_http_get)
    assert sync.check_icon_url("good_icon") is True
    assert sync.check_icon_url("inv_misc_astralrune") is False  # the known-404 icon, per the doc
    assert sync.check_icon_url("") is False


# --- cache-warm rerun: zero network requests, byte-identical output --------------------


def _feed_entry(entry_id: int, spell_id: int, name: str, icon: str, *, entry_type: str = "active") -> dict[str, Any]:
    return {
        "id": entry_id, "definitionId": entry_id, "maxRanks": 1, "type": entry_type,
        "name": name, "spellId": spell_id, "icon": icon,
    }


def _feed_node(
    node_id: int,
    name: str,
    *,
    node_type: str = "single",
    pos: tuple[int, int] = (0, 0),
    req_points: int | None = None,
    entry_node: bool = False,
    prev: list[int] | None = None,
    next_: list[int] | None = None,
    entries: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    node: dict[str, Any] = {
        "id": node_id, "name": name, "type": node_type, "posX": pos[0], "posY": pos[1],
        "maxRanks": 1, "entryNode": entry_node, "next": next_ or [], "prev": prev or [],
        "entries": entries if entries is not None else [_feed_entry(node_id * 10, node_id * 100, name, "icon")],
    }
    if req_points is not None:
        node["reqPoints"] = req_points
    return node


def _tiny_synthetic_feed() -> list[dict[str, Any]]:
    """A minimal, self-contained stand-in for the real 3.2 MB Raidbots feed -- exercises
    the exact same code path as the real thing, but small enough to embed here and fast
    enough that this test never touches a real network."""
    return [
        {
            "classId": 99,
            "specId": 1,
            "className": "Test",
            "specName": "Spec",
            "traitTreeId": 1,
            "fullNodeOrder": [1, 2, 3, 4, 5, 6, 99],
            "classNodes": [
                _feed_node(1, "Class Entry", entry_node=True, next_=[2]),
                _feed_node(2, "Class Gated", pos=(100, 0), req_points=1, prev=[1]),
            ],
            "specNodes": [
                _feed_node(3, "Spec Entry", entry_node=True, next_=[4]),
                _feed_node(
                    4, "Apex Talent", node_type="tiered", pos=(100, 0), req_points=1, prev=[3],
                    entries=[_feed_entry(40, 400, "Apex Talent", "inv_apextalent_test", entry_type="tierrank")],
                ),
            ],
            "heroNodes": [
                _feed_node(5, "Elunes Pick", pos=(0, 100)),
                _feed_node(6, "Keepers Pick", pos=(100, 100)),
            ],
            "subTreeNodes": [
                {
                    "id": 99, "name": "Pick A / Pick B", "type": "subtree", "posX": 200, "posY": 100,
                    "entryNode": True, "next": [], "prev": [],
                    "entries": [
                        {
                            "id": 991, "type": "subtree", "name": "Elune's Chosen",
                            "traitSubTreeId": 24, "nodes": [5],
                        },
                        {
                            "id": 992, "type": "subtree", "name": "Keeper of the Grove",
                            "traitSubTreeId": 23, "nodes": [6],
                        },
                    ],
                }
            ],
        }
    ]


def test_build_document_cache_warm_rerun_makes_zero_network_requests_and_is_byte_identical(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    feed = _tiny_synthetic_feed()
    feed_bytes = json.dumps(feed).encode("utf-8")
    call_log: list[str] = []

    def fake_http_get(url: str, *, method: str = "GET", timeout: float = 30.0) -> tuple[int, bytes]:
        call_log.append(url)
        if url == sync.FEED_URLS["live"]:
            return 200, feed_bytes
        # every spellId 100..600 gets a trivially-fetchable tooltip
        return 200, json.dumps({"name": "x", "icon": "icon", "tooltip": "Some tooltip text."}).encode("utf-8")

    monkeypatch.setattr(sync, "_http_get", fake_http_get)

    cache_dir = tmp_path / "cache"
    first = sync.build_document(99, 1, "live", patch="12.1", use_cache=True, cache_dir=cache_dir)
    assert call_log, "the cold run should have hit the network"

    def forbidden_http_get(url: str, *, method: str = "GET", timeout: float = 30.0) -> tuple[int, bytes]:
        raise AssertionError(f"unexpected network call on a warm cache: {url}")

    monkeypatch.setattr(sync, "_http_get", forbidden_http_get)
    second = sync.build_document(99, 1, "live", patch="12.1", use_cache=True, cache_dir=cache_dir)

    assert json.dumps(first, sort_keys=True) == json.dumps(second, sort_keys=True)
    assert first == second


def test_build_document_no_cache_flag_always_refetches(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    feed = _tiny_synthetic_feed()
    feed_bytes = json.dumps(feed).encode("utf-8")
    calls = {"n": 0}

    def fake_http_get(url: str, *, method: str = "GET", timeout: float = 30.0) -> tuple[int, bytes]:
        calls["n"] += 1
        if url == sync.FEED_URLS["live"]:
            return 200, feed_bytes
        return 200, json.dumps({"name": "x", "icon": "icon", "tooltip": "Some tooltip text."}).encode("utf-8")

    monkeypatch.setattr(sync, "_http_get", fake_http_get)
    cache_dir = tmp_path / "cache"
    sync.build_document(99, 1, "live", patch="12.1", use_cache=True, cache_dir=cache_dir)
    first_call_count = calls["n"]
    sync.build_document(99, 1, "live", patch="12.1", use_cache=False, cache_dir=cache_dir)
    assert calls["n"] > first_call_count, "--no-cache must force a refetch even with a warm cache present"


def test_build_document_fails_the_run_on_a_tooltip_fetch_failure(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    feed = _tiny_synthetic_feed()
    feed_bytes = json.dumps(feed).encode("utf-8")

    def failing_http_get(url: str, *, method: str = "GET", timeout: float = 30.0) -> tuple[int, bytes]:
        if url == sync.FEED_URLS["live"]:
            return 200, feed_bytes
        return 404, b""

    monkeypatch.setattr(sync, "_http_get", failing_http_get)
    monkeypatch.setattr(sync, "TOOLTIP_FETCH_RETRY_DELAY_SECONDS", 0.0)
    with pytest.raises(sync.TalentTreeSyncError, match="tooltip fetch"):
        sync.build_document(99, 1, "live", patch="12.1", use_cache=True, cache_dir=tmp_path / "cache")


# --- against the real, checked-in output file -------------------------------------------


def _load_real_doc() -> dict[str, Any]:
    if not REAL_OUTPUT_PATH.exists():
        pytest.skip(f"{REAL_OUTPUT_PATH} not generated yet")
    with REAL_OUTPUT_PATH.open(encoding="utf-8") as f:
        return json.load(f)  # type: ignore[no-any-return]


def test_real_file_validates_against_schema(schema: dict[str, Any]) -> None:
    doc = _load_real_doc()
    assert sync.validate_against_schema(doc, schema) == []


def test_real_file_passes_all_validators() -> None:
    doc = _load_real_doc()
    sync.validate_document(doc)  # must not raise


def test_real_file_full_node_order_matches_task20_fixture_order() -> None:
    """Cross-check against task 20's own findings (docs/design/talent-string-format.md):
    a fresh fetch's fullNodeOrder must match, verbatim and in order, what task 20 recorded
    from its own fetch a day earlier -- if this ever diverges, the two tasks' node orders
    have silently drifted and task 20's codec would decode the wrong nodes."""
    doc = _load_real_doc()
    if not TASK20_FIXTURE_PATH.exists():
        pytest.skip(f"{TASK20_FIXTURE_PATH} not present")
    with TASK20_FIXTURE_PATH.open(encoding="utf-8") as f:
        fixture = json.load(f)
    fixture_ids = [n["nodeId"] for n in fixture["tree"]["nodes"]]
    assert doc["full_node_order"] == fixture_ids


def test_real_file_task20_codec_decodes_fixtures_and_every_node_resolves() -> None:
    """The literal acceptance criterion: task 20's codec decodes all three fixture loadout
    strings against *this file's* full_node_order, and the resulting nodes all resolve."""
    doc = _load_real_doc()
    if not TASK20_FIXTURE_PATH.exists():
        pytest.skip(f"{TASK20_FIXTURE_PATH} not present")

    from app.services.talent_codec import TreeNode, decode

    with TASK20_FIXTURE_PATH.open(encoding="utf-8") as f:
        fixture = json.load(f)

    max_ranks_by_id: dict[int, int] = {}
    for tree_name in ("class", "spec", "hero"):
        for node in doc["trees"][tree_name]["nodes"]:
            max_ranks_by_id[node["id"]] = node["max_ranks"]

    # Ids in full_node_order absent from this file's trees belong to other specs sharing
    # the same traitTreeId (see doc fix 2) -- default max_ranks=1, matching task 20's own
    # documented convention (a same-spec loadout string never purchases them).
    node_order = [TreeNode(node_id=nid, max_ranks=max_ranks_by_id.get(nid, 1)) for nid in doc["full_node_order"]]

    known_ids = set(max_ranks_by_id)
    for loadout_fixture in fixture["loadouts"]:
        loadout = decode(loadout_fixture["string"], node_order, expected_spec_id=doc["spec"]["spec_id"])
        for talent_node in loadout.nodes:
            assert talent_node.node_id in known_ids, (
                f"{loadout_fixture['name']}: decoded node {talent_node.node_id} "
                "does not resolve against this file's own trees"
            )


def test_real_file_meta_records_which_branch_was_used() -> None:
    doc = _load_real_doc()
    assert doc["meta"]["branch"] in ("live", "ptr")
