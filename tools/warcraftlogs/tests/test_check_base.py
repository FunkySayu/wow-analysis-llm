"""Contract tests for the Check base class and the two ported common checks.

No network and no credentials: `FakeReport` supplies synthetic events through the
same few methods a real `Report` exposes, which is the whole point of routing log
access through that object.

The test that matters most is `test_print_reads_only_json`. `print()` reading the
log directly would work fine in a terminal and silently break `from_json()`,
`--json` and the React renderer all at once, so it is asserted rather than
documented: the check is constructed with `report=None`, and any log access at
all raises AttributeError.
"""

from __future__ import annotations

import json as jsonlib

import pytest

from checks.common import AbcCheck, ManaCheck
from lib import check as C
from lib import format as F


def fight(fid=1, name="Test Boss", start=0, end=10_000, **kw):
    return dict({"id": fid, "name": name, "startTime": start, "endTime": end,
                 "encounterID": 100, "kill": True, "keystoneLevel": None}, **kw)


def cast(ts, ability=123, mana=None, mana_max=100):
    e = {"timestamp": ts, "type": "cast", "abilityGameID": ability}
    if mana is not None:
        e["classResources"] = [{"type": 0, "amount": mana, "max": mana_max}]
    return e


class FakeReport:
    """Stands in for `Report`: same surface, canned events, counts its fetches."""

    def __init__(self, fights, events_by_type, names=None):
        self.code = "FAKE"
        self.actor_id = 1
        self.actor_name = "Tester"
        self.selector = "test"
        self.fights = fights
        self._events = events_by_type      # {(fight_id, data_type): [event, ...]}
        self._names = names or {}
        self.fetches = 0

    def events(self, f, data_type, **kw):
        self.fetches += 1
        fid = f["id"] if isinstance(f, dict) else f
        return list(self._events.get((fid, data_type), []))

    def ability_names(self):
        self.fetches += 1
        return dict(self._names)

    def context(self):
        return {"report": self.code, "actor": self.actor_name, "actorId": self.actor_id,
                "selector": self.selector, "fights": [C.fight_ref(f) for f in self.fights]}


# --------------------------------------------------------------- abc / GCD uptime

@pytest.fixture
def abc_report():
    # One fight with a 7s hole at the end, one fight the player never cast in.
    f1, f2 = fight(1), fight(2, name="Quiet Boss", end=5_000)
    return FakeReport([f1, f2], {(1, "Casts"): [cast(1_000), cast(2_000), cast(3_000)]})


def test_abc_json_numbers(abc_report):
    d = AbcCheck(abc_report).json()
    assert d["scope"] == "fight"
    assert d["params"] == {"gcd": 1.5}
    assert [row["fight"]["id"] for row in d["fights"]] == [1, 2]
    a, b = (row["data"] for row in d["fights"])
    assert a["casts"] == 3
    # gaps are 1s, 1s, 1s and 7s; only the 7s one exceeds the 1.5s GCD.
    assert a["downtimeSeconds"] == pytest.approx(5.5)
    assert a["uptimePct"] == pytest.approx(45.0)
    assert a["longestGapSeconds"] == pytest.approx(7.0)
    # A fight with no casts carries no derived fields at all rather than zeroes,
    # so "silent in this fight" cannot be misread as "100% downtime".
    assert b["casts"] == 0 and "downtimeSeconds" not in b
    # ... and it is excluded from the measurement, but still counted in the
    # selection, matching what the text says.
    assert d["overall"]["seconds"] == pytest.approx(10.0)
    assert d["overall"]["uptimePct"] == pytest.approx(45.0)
    assert d["overall"]["fights"] == 2 and d["overall"]["measuredFights"] == 1


def test_abc_seconds_are_exact_not_rounded():
    """Regression: rounding `seconds` in the payload changed the printed column.

    A 1.45s fight rounded to 1.5 prints as "2" under `{:.0f}` where the raw value
    prints "1". Payload keeps full precision; the renderer rounds.
    """
    r = FakeReport([fight(1, start=0, end=1_450)], {})
    ref = AbcCheck(r).json()["fights"][0]["fight"]
    assert ref["seconds"] == pytest.approx(1.45)


def test_print_reads_only_json(abc_report, capsys):
    """`print()` must render from the payload alone - no Report, no log."""
    payload = AbcCheck(abc_report).json()
    detached = AbcCheck.from_json(payload)          # report is None
    detached.print()
    out = capsys.readouterr().out
    assert "45.0" in out                            # the uptime it computed
    assert "no casts recorded" in out               # the silent fight
    assert "2 fights, 10s total" in out


def test_print_matches_between_live_and_rehydrated(abc_report, capsys):
    AbcCheck(abc_report).print()
    live = capsys.readouterr().out
    AbcCheck.from_json(jsonlib.loads(jsonlib.dumps(AbcCheck(abc_report).json()))).print()
    assert capsys.readouterr().out == live


# --------------------------------------------------------------- mana curve

def test_mana_json_and_dry_casts():
    f = fight(1)
    casts = [cast(0, mana=100), cast(4_000, ability=456, mana=10)]
    r = FakeReport([f], {(1, "Casts"): casts}, names={456: "Desperate Filler"})
    d = ManaCheck(r).json()["overall"]
    assert d["totalSeconds"] == pytest.approx(10.0)
    bands = {b["label"]: b["seconds"] for b in d["bands"]}
    assert bands["80-100%"] == pytest.approx(4.0)   # cast-to-cast attribution
    assert bands["0-20%"] == pytest.approx(6.0)     # last cast holds to fight end
    assert d["dryPct"] == pytest.approx(60.0)
    assert d["lowest"]["pct"] == pytest.approx(10.0)
    assert d["lowest"]["at"] == "0:04.0"
    # Spell names are resolved in json(), not print() - print() cannot reach the log.
    assert d["castsWhileDry"] == [{"spellId": 456, "name": "Desperate Filler", "count": 1}]


def test_mana_print_uses_only_the_payload(capsys):
    f = fight(1)
    r = FakeReport([f], {(1, "Casts"): [cast(0, mana=100), cast(4_000, mana=5)]})
    ManaCheck.from_json(ManaCheck(r).json()).print()
    out = capsys.readouterr().out
    assert "time on the mana curve" in out
    assert "lowest reading: 5.0%" in out


def test_mana_with_no_readings_says_so(capsys):
    r = FakeReport([fight(1)], {(1, "Casts"): [cast(0)]})   # no classResources
    ManaCheck.from_json(ManaCheck(r).json()).print()
    assert "no mana readings" in capsys.readouterr().out


# --------------------------------------------------------------- base class

def test_json_is_memoised(abc_report):
    c = AbcCheck(abc_report)
    c.json()
    after_first = abc_report.fetches
    c.json()
    c.print()
    c.envelope()
    assert abc_report.fetches == after_first, "json() re-read the log"


def test_envelope_shape(abc_report):
    env = AbcCheck(abc_report).envelope()
    assert env["schema"] == C.SCHEMA
    assert env["id"] == "abc"
    assert env["title"] and env["group"] == "common"
    assert env["summary"].startswith("Always Be Casting")
    assert env["context"]["actor"] == "Tester"
    assert env["data"]["fights"]
    jsonlib.dumps(env)      # must be serialisable as-is


def test_from_envelope_rejects_a_mismatched_id(abc_report):
    env = AbcCheck(abc_report).envelope()
    with pytest.raises(ValueError):
        ManaCheck.from_envelope(env)


def test_registry_rejects_duplicate_and_missing_ids():
    class A(C.Check):
        id = "dup"

        def json(self):
            return {}

        def print(self):
            pass

    class B(A):
        pass                      # inherits id="dup"

    class Anon(A):
        id = ""

    with pytest.raises(ValueError, match="duplicate"):
        C.registry(A, B)
    with pytest.raises(ValueError, match="no id"):
        C.registry(Anon)


def test_legacy_function_is_adapted_but_has_no_payload():
    def check_legacy(code, aid, fights):
        """Old-style check."""
        print("legacy ran")

    entry = C.instantiate(check_legacy, FakeReport([fight(1)], {}))
    assert not entry.ported
    with pytest.raises(NotImplementedError, match="port it to a Check subclass"):
        entry.json()


# --------------------------------------------------------------- ledger plumbing

def test_ledger_accepts_instance_dicts(capsys):
    rows = [F.instance("0:10.0", F.PERFECT, "on plan", salvo=25),
            F.instance("0:20.0", F.FAIL, "spent early", salvo=3)]
    assert F.tally(rows) == {F.PERFECT: 1, F.GOOD: 0, F.OK: 0, F.FAIL: 1}
    F.ledger("Test", rows)
    out = capsys.readouterr().out
    assert "2 instances" in out and "1 PERFECT" in out
    assert "0:20.0" in out and "0:10.0" not in out   # only faults are listed


# --------------------------------------------------- per-fight scope contract

def test_fight_json_only_ever_sees_its_own_fight():
    """The point of the scope: a check cannot reach a fight it was not given.

    The old shape let a check establish context from `fights[0]` and apply it to
    the whole selection, which is exactly how `barrage` came to grade 54 fights
    against one fight's talent evidence.
    """
    seen = []

    class Spy(C.Check):
        id, title, group = "spy", "Spy", "test"

        def fight_json(self, fight):
            seen.append(fight["id"])
            # Only the fight handed in is reachable from here.
            assert self.report.events(fight, "Casts") is not None
            return {"id": fight["id"]}

        def combine(self, parts):
            return {"ids": [d["id"] for _, d in parts]}

        def print(self):
            pass

    r = FakeReport([fight(1), fight(2), fight(3)], {})
    d = Spy(r).json()
    assert seen == [1, 2, 3]
    assert [row["fight"]["id"] for row in d["fights"]] == [1, 2, 3]
    assert d["overall"] == {"ids": [1, 2, 3]}


def test_combine_defaults_to_none_rather_than_a_fake_rollup():
    class NoRollup(C.Check):
        id, title, group = "noroll", "No rollup", "test"

        def fight_json(self, fight):
            return {"n": 1}

        def print(self):
            pass

    assert NoRollup(FakeReport([fight(1)], {})).json()["overall"] is None


def test_run_scope_check_must_implement_json():
    class Bad(C.Check):
        id, title, group, scope = "bad", "Bad", "test", "run"

        def print(self):
            pass

    with pytest.raises(NotImplementedError, match="must implement json"):
        Bad(FakeReport([fight(1)], {})).json()


def test_fight_scope_check_must_implement_fight_json():
    class Bad2(C.Check):
        id, title, group = "bad2", "Bad", "test"

        def print(self):
            pass

    with pytest.raises(NotImplementedError, match="fight_json"):
        Bad2(FakeReport([fight(1)], {})).json()


def test_run_scope_json_is_still_memoised():
    calls = []

    class RunScope(C.Check):
        id, title, group, scope = "runscope", "Run", "test", "run"

        def json(self):
            calls.append(1)
            return {"ok": True}

        def print(self):
            pass

    c = RunScope(FakeReport([fight(1)], {}))
    c.json()
    c.json()
    c.envelope()
    assert len(calls) == 1


def test_consensus_reports_disagreement_instead_of_taking_the_first():
    parts = [
        (fight(1), {"aoe": {"value": 5, "evidence": "spheres seen"}}),
        (fight(2), {"aoe": {"value": 5, "evidence": "spheres seen"}}),
        (fight(3), {"aoe": {"value": 2, "evidence": "no spheres seen"}}),
    ]
    out = C.consensus(parts, "aoe")
    assert out["value"] == 5                     # the majority reading
    assert out["varies"] is True                 # ... but the split is stated
    assert out["byValue"] == {"5": 2, "2": 1}

    agreed = C.consensus(parts[:2], "aoe")
    assert agreed["varies"] is False and agreed["evidence"] == "spheres seen"


def test_mana_is_per_fight_not_pooled():
    """Two pulls with different curves must stay distinguishable in the payload.

    Pooled, these two average to something neither pull ever looked like.
    """
    f1, f2 = fight(1, name="Full"), fight(2, name="Dry", start=0, end=10_000)
    r = FakeReport(
        [f1, f2],
        {
            (1, "Casts"): [cast(0, mana=100), cast(4_000, mana=90)],
            (2, "Casts"): [cast(0, mana=10), cast(4_000, mana=5)],
        },
    )
    d = ManaCheck(r).json()
    per = {row["fight"]["name"]: row["data"] for row in d["fights"]}
    assert per["Full"]["dryPct"] == pytest.approx(0.0)
    assert per["Dry"]["dryPct"] == pytest.approx(100.0)
    assert per["Full"]["lowest"]["pct"] == pytest.approx(90.0)
    assert per["Dry"]["lowest"]["pct"] == pytest.approx(5.0)
    # The roll-up takes the extreme, not a mean of the two.
    assert d["overall"]["lowest"]["pct"] == pytest.approx(5.0)
    assert d["overall"]["dryPct"] == pytest.approx(50.0)
