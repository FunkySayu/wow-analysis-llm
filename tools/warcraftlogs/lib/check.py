"""The Check base class and the Report context every check runs against.

Why this exists
---------------
Checks started as `check_<name>(code, aid, fights)` functions that computed and
printed in one pass. That is fine for reading in a terminal and useless for
anything else: the numbers only ever existed as formatted text, so a report had
to be re-derived by hand from what the terminal happened to say.

The split here keeps both surfaces from one computation:

    json()   -> the findings as data. The only thing that touches the log.
    print()  -> the same findings as the terminal text we already had.

`print()` MUST read `self.json()` and nothing else. That is not a style rule -
it is what makes `Check.from_json(payload)` work, which is how a saved extract
under `scratch/` can be re-rendered (or re-read by a later session) without the
WCL API, and what lets `tools/reporting` render a check it has never run. The test
suite enforces it by constructing checks with `report=None`.

`id` is the pairing key: the CLI name, the key in the JSON envelope, and the key
the React component registers under (tools/reporting/src/registry.ts) are all the same
string. One identifier, so the two sides cannot drift.
"""

from __future__ import annotations

import abc
import collections
import functools
import inspect

from lib import wclapi as W

SCHEMA = 1

#: Sentinel for `Report.events(source_id=...)`: default to this report's actor.
#: `None` has to stay available as "no source filter at all" (CombatantInfo is
#: fetched report-wide, not per actor), so the default cannot itself be None.
ACTOR = object()


class Report:
    """One WarcraftLogs report, narrowed to one actor and a fight selection.

    This is the "content of the log" a check is constructed with. It owns the
    fetch plumbing (report code, actor id, caching) so a check body never
    repeats `W.events(code, f["id"], ..., aid)` and never has to be told which
    actor it is looking at.

    It is also the seam that makes checks testable: everything a check reads
    goes through these few methods, so a fake with synthetic events substitutes
    for the live API with no network and no credentials.
    """

    def __init__(self, code, actor_id, fights, actor_name=None, selector=None,
                 refresh=False):
        self.code = code
        self.actor_id = actor_id
        self.actor_name = actor_name
        self.fights = list(fights)
        self.selector = selector
        self.refresh = refresh

    @classmethod
    def load(cls, code, actor, selector="encounters", refresh=False):
        """Resolve an actor name and a fight selector against the live report."""
        aid = W.actor_id(code, actor)
        fights = W.fights(code, selector)
        if not fights:
            raise SystemExit(f"no fights matched selector {selector!r}")
        return cls(code, aid, fights, actor_name=actor, selector=selector,
                   refresh=refresh)

    # --- log access ----------------------------------------------------------

    def events(self, fight, data_type, source_id=ACTOR, **kw):
        """Events for one fight. `fight` is a fight dict or a fight id.

        `source_id` defaults to this report's actor; pass `None` explicitly for
        a report-wide fetch (CombatantInfo), or another actor's id to look at a
        peer.
        """
        fid = fight["id"] if isinstance(fight, dict) else fight
        src = self.actor_id if source_id is ACTOR else source_id
        return W.events(self.code, fid, data_type, source_id=src,
                        refresh=self.refresh, **kw)

    def table(self, data_type, fight_ids=None, source_id=ACTOR):
        ids = fight_ids if fight_ids is not None else [f["id"] for f in self.fights]
        src = self.actor_id if source_id is ACTOR else source_id
        return W.table(self.code, ids, data_type, source_id=src, refresh=self.refresh)

    def ability_names(self):
        return W.ability_names(self.code)

    def actor_names(self):
        return W.actor_names(self.code)

    @property
    def meta(self):
        return W.report_meta(self.code, refresh=self.refresh)

    # --- serialisation -------------------------------------------------------

    def context(self):
        """The part of the envelope that says what was analysed.

        Every field is derivable from the fight dicts alone, so a saved envelope
        stays readable after the WCL cache is gone.
        """
        return {
            "report": self.code,
            "actor": self.actor_name,
            "actorId": self.actor_id,
            "selector": self.selector,
            "fights": [fight_ref(f) for f in self.fights],
        }


def fight_ref(f):
    """A fight reduced to what a presentation layer needs to label it.

    `seconds` is exact, not rounded. Rounding here once cost a real diff: a 1.45s
    fight became 1.5 in the payload and then printed as "2" where the same
    format string over the raw value printed "1". Round in the renderer.
    """
    return {
        "id": f["id"],
        "name": f.get("name"),
        "encounterId": f.get("encounterID"),
        "keystoneLevel": f.get("keystoneLevel"),
        "kill": f.get("kill"),
        "seconds": (f["endTime"] - f["startTime"]) / 1000.0,
        "startTime": f["startTime"],
    }


class Check(abc.ABC):
    """Base class for every log check.

    **The unit of analysis is one pull.** A check computes `fight_json(fight)`
    for a single fight and the base class maps that over the selection, so the
    payload is per-fight by construction:

        {"scope": "fight",
         "params":  {...},                      # check constants, not measurements
         "fights":  [{"fight": {...}, "data": {...}}, ...],
         "overall": {...}}                      # combine(), or None

    This is not tidiness. Pooling several pulls into one number hides sequencing
    (.claude/knowledge/method/analysing-a-pull.md: "an aggregate hides sequencing
    completely"), and - worse - it invites a check to establish context once and
    apply it everywhere. `barrage` did exactly that: it read the hero tree and
    `aoe_count` from `fights[0]` and graded every fight against them, where that
    pair takes four different values across a 54-fight selection. Per-fight
    computation makes that class of mistake unavailable rather than merely
    discouraged, and `consensus()` below makes the disagreement reportable.

    A check that genuinely cannot decompose - one that reads the raid roster, or
    compares actors across a whole night - sets `scope = "run"` and implements
    `json()` directly instead.

    Either way `json()` is memoised, so calling it repeatedly (which `print()`
    and `envelope()` both do) reads the log once.
    """

    #: Unique across the whole suite. Doubles as the CLI name and the React
    #: component key. Enforced unique by `registry()`.
    id: str = ""
    #: Human title for a report heading.
    title: str = ""
    #: Which suite this belongs to ("common", "mage", "druid", ...).
    group: str = ""
    #: "fight" - implement `fight_json()` (+ optionally `combine()`), and the
    #: base class assembles. "run" - implement `json()` yourself, for a check
    #: whose finding is not per-pull at all.
    scope: str = "fight"
    #: Distinguishes a real check from the legacy adapter below, which raises
    #: on `json()`. `run.py --json` reads this to say what is not ported yet.
    ported = True

    def __init__(self, report=None):
        self.report = report
        self._data = None

    def __init_subclass__(cls, **kw):
        """Memoise a `scope = "run"` subclass's own `json()` in `self._data`.

        Fight-scope checks never define `json()` and go through the base one,
        which memoises directly; this covers the run-scope checks that do.
        Done here rather than by asking subclasses to call a helper because the
        alternative - `json()` recomputing whenever `print()` also calls it -
        fails silently and only shows up as a check that takes twice as long.
        Wrapping also gives `from_json()` its meaning: a pre-seeded `_data`
        short-circuits the real body, so a hydrated check never touches a
        Report that isn't there.
        """
        super().__init_subclass__(**kw)
        raw = cls.__dict__.get("json")
        if raw is None or getattr(raw, "_memoised", False):
            return

        @functools.wraps(raw)
        def json(self):
            if self._data is None:
                self._data = raw(self)
            return self._data

        json._memoised = True
        cls.json = json

    # --- the two surfaces ----------------------------------------------------

    def json(self):
        """The findings as a JSON-serialisable dict. Memoised.

        For `scope = "fight"` (the default) this is assembled from
        `fight_json()` / `combine()` / `params()` and should not be overridden.
        A `scope = "run"` check overrides it and does its own thing; the
        override is memoised too, by `__init_subclass__`.
        """
        if self._data is None:
            self._data = self._assemble()
        return self._data

    def _assemble(self):
        if self.scope != "fight":
            raise NotImplementedError(
                f"{type(self).__name__} sets scope={self.scope!r} and must "
                f"implement json() itself")
        parts = [(f, self.fight_json(f)) for f in self.report.fights]
        return {
            "scope": "fight",
            "params": self.params(),
            "fights": [{"fight": fight_ref(f), "data": d} for f, d in parts],
            "overall": self.combine(parts),
        }

    def fight_json(self, fight):
        """The findings for ONE fight, as a JSON-serialisable dict.

        Domain-shaped, not presentation-shaped: exact numbers, spell IDs, real
        timestamps. Round only in `print()` and in the React component. Read the
        log through `self.report.events(fight, ...)`.

        Anything this check infers about context - which talents are on, how
        many targets the APL should assume - belongs in here, derived from
        *this* fight, not established once outside the loop.
        """
        raise NotImplementedError(
            f"{type(self).__name__} must implement fight_json() "
            f"(or set scope='run' and implement json())")

    def combine(self, parts):
        """Roll `[(fight, fight_json), ...]` up into the whole-selection view.

        Return None when a roll-up would be meaningless. Sum what is additive,
        take extremes where an extreme is the point, and say so explicitly when
        the fights disagree about something - never quietly pick the first.
        """
        return None

    def params(self):
        """Check constants that are not measurements (thresholds, the APL text).

        Separate from `overall` because they are configuration, not a finding,
        and a reader should be able to tell which is which.
        """
        return {}

    @abc.abstractmethod
    def print(self):
        """Render `self.json()` as the terminal text. Must not read the log."""

    # --- packaging -----------------------------------------------------------

    @classmethod
    def summary(cls):
        """First paragraph of the docstring - the one-line description."""
        doc = inspect.getdoc(cls) or ""
        return doc.split("\n\n")[0].replace("\n", " ").strip()

    def envelope(self):
        """`{schema, id, title, group, summary, context, data}`.

        The unit the visualization layer consumes: enough context to caption
        itself, plus the check's own payload under `data`.
        """
        return {
            "schema": SCHEMA,
            "id": self.id,
            "title": self.title or self.id,
            "group": self.group,
            "summary": self.summary(),
            "context": self.report.context() if self.report else None,
            "data": self.json(),
        }

    @classmethod
    def from_json(cls, data, report=None):
        """Rehydrate a check from a saved `data` payload, with no log access.

        `print()` then re-renders the original text from the saved numbers -
        which is also how the test suite proves `print()` reads nothing else.
        """
        inst = cls(report)
        inst._data = data
        return inst

    @classmethod
    def from_envelope(cls, env):
        if env.get("id") != cls.id:
            raise ValueError(f"envelope id {env.get('id')!r} is not {cls.id!r}")
        return cls.from_json(env["data"])


class PoolCheck(Check):
    """Base for checks that compare one pull against its encounter's ranking pool.

    Fight-scoped, because a comparison is always against ONE encounter's pool -
    but capped at `POOL_FIGHTS` pulls. Each pull costs roughly ten to twenty-five
    peer profiles at several cached queries each, so letting `-f raid` fan out
    over fourteen pulls would fire hundreds of ranking queries from one command.

    The cap keeps the payload shape uniform with every other check while
    preserving the protection the old "narrow with -f <id>" guard gave; the
    difference is that `-f raid` now analyses the first ranked pull instead of
    refusing to do anything.
    """

    POOL_FIGHTS = 1

    def _rendered_ids(self):
        return [x["id"] for x in self.report.fights[:self.POOL_FIGHTS]
                if x.get("encounterID")]

    def _skip(self, f):
        """None if this fight should be analysed, else why it was not."""
        if not f.get("encounterID"):
            return "not a ranked encounter"
        if f["id"] not in self._rendered_ids():
            return (f"beyond the first {self.POOL_FIGHTS} ranked pull(s) - "
                    f"narrow with -f {f['id']} to compare this one")
        return None

    def _skipped_note(self, data):
        skipped = [row for row in data["fights"] if row["data"].get("skipped")]
        if skipped:
            ids = ", ".join(str(row["fight"]["id"]) for row in skipped)
            print(f"\n({len(skipped)} further pull(s) not compared - one pool per run. "
                  f"Use -f <id> for any of: {ids})")


def consensus(parts, key):
    """Roll a per-fight inference up without quietly picking the first answer.

    `parts` is `combine()`'s argument and `key` names a `{"value", "evidence"}`
    entry in each fight's payload. Returns that shape plus `varies` and a
    per-value fight count, so a selection where the fights disagree reports the
    disagreement instead of hiding it. This exists because the alternative was
    already shipped once and was wrong: reading `aoe_count` from `fights[0]` and
    grading 54 fights against it.
    """
    counts = collections.Counter()
    evidence = {}
    for _, data in parts:
        entry = data.get(key) or {}
        v = entry.get("value")
        counts[v] += 1
        evidence.setdefault(v, entry.get("evidence"))
    if not counts:
        return {"value": None, "evidence": "no fights", "varies": False, "byValue": {}}
    top, _ = counts.most_common(1)[0]
    return {
        "value": top,
        "evidence": evidence.get(top),
        "varies": len(counts) > 1,
        "byValue": {str(v): n for v, n in counts.most_common()},
    }


def registry(*checks):
    """`{id: class}` for a module's checks, rejecting duplicate or missing ids.

    A duplicate id would silently shadow a check in `run.py`'s merged CHECKS
    dict and, worse, would pair the wrong React component with it.
    """
    out = {}
    for c in checks:
        if not c.id:
            raise ValueError(f"{c.__name__} has no id")
        if c.id in out:
            raise ValueError(f"duplicate check id {c.id!r}")
        out[c.id] = c
    return out


def is_check(entry):
    return isinstance(entry, type) and issubclass(entry, Check)


def instantiate(entry, report):
    """Build a runnable object from a registry entry.

    Legacy `check_<name>(code, aid, fights)` functions are still registered
    alongside ported classes; this adapts them to the class interface so
    `run.py` has one code path. A legacy check has no `json()`, which is
    exactly the signal `--json` uses to report what is not ported yet.
    """
    if is_check(entry):
        return entry(report)
    return _LegacyCheck(entry, report)


class _LegacyCheck:
    """Adapter for a not-yet-ported `check_<name>(code, aid, fights)` function."""

    ported = False

    def __init__(self, fn, report):
        self.fn = fn
        self.report = report
        self.id = fn.__name__.replace("check_", "").replace("_", "-")
        self.title = self.id
        self.group = ""

    def summary(self):
        doc = inspect.getdoc(self.fn) or ""
        return doc.split("\n\n")[0].replace("\n", " ").strip()

    def json(self):
        raise NotImplementedError(
            f"check {self.id!r} still prints directly - port it to a Check "
            f"subclass (see tools/warcraftlogs/lib/check.py) to give it a JSON payload")

    def print(self):
        r = self.report
        self.fn(r.code, r.actor_id, r.fights)
