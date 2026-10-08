# wow-analysis

This project benchmarks and improves a character's performance in World of Warcraft by
comparing **actual play** (WarcraftLogs reports) against **theoretical-optimal play**
(SimulationCraft, via Raidbots) — currently on the PTR. This file is the map for how to
pull data, read it correctly, and reason about it. It's written for future sessions, not
just as a record of what happened in this one. Detail lives in the files it points to;
the "read before" lines are not optional.

## Where things live

| path | holds | read first |
|---|---|---|
| `.claude/skills/` | how to pull data from each source | the skill, before guessing an endpoint |
| `.claude/knowledge/` | durable findings: `game/`, `classes/`, `raid/<patch>/<tier>/`, `dungeons/<patch>/`, `method/` | [its README](.claude/knowledge/README.md) — the index |
| `data/` | long-term datasets: `raid/<patch>/<tier>/<nn>_<boss>/`, `classes/<class>/<spec>/`, `items/<patch>/` | [data/README.md](data/README.md) before regenerating anything |
| `tools/` | analysis tooling, one folder per source: `warcraftlogs/`, `game_knowledge/`, `raidbots/`, `keystoneloot/`, `wowhead/`, `reporting/` | [tools/README.md](tools/README.md) before writing a script |
| `scratch/` | per-report working extracts; not meant to stay current | — |
| `site/`, `docs/design/` | the planning website and its design record | — |

**Read before the task, every time:**
- any new log analysis → [method/analysing-a-pull.md](.claude/knowledge/method/analysing-a-pull.md),
  and run the checks in `tools/warcraftlogs/` before re-deriving anything;
- modelling an encounter in simc → [method/modelling-a-fight-in-simc.md](.claude/knowledge/method/modelling-a-fight-in-simc.md);
- a boss death report → [method/boss-death-timelines.md](.claude/knowledge/method/boss-death-timelines.md);
- a published HTML report → [method/building-reports.md](.claude/knowledge/method/building-reports.md);
- any claim about gear, loot, upgrades or crafting → the itemization set in
  [game/](.claude/knowledge/game/) (gearing systems change on four clocks; honour the
  "valid as of" dates);
- a spec or boss you're about to discuss → its file under `classes/` or `raid/`, if one exists.

## Data sources — use the skills, don't re-derive them

Four skills cover the actual mechanics of pulling data. Load them rather than guessing
endpoints from memory — several have real traps baked in (see below).

- **`warcraftlogs-reports`** — WCL API v2 (GraphQL), OAuth client-credentials flow using
  `.env`. Pulls fight lists, kill/wipe status, damage/cast tables, cast timelines.
- **`raidbots-reports`** — the simc JSON behind a Raidbots report link: DPS distribution,
  a full sample `action_sequence` (cast-by-cast trace with buff/resource state), and a
  per-ability `stats` breakdown with real spellIds.
- **`wow-talent-data`** — the full talent tree (class/spec/hero/apex) for any spec, live or
  PTR, as one JSON feed, plus how to attach real tooltip text to each spellId.
- **`wow-ptr-research`** — where to check *why* something changed on PTR and whether
  SimulationCraft itself has caught up to the current build yet (this matters more than it
  sounds like).

Also: `simc-simulation` and `simc-profile-syntax` for running sims locally,
`wowhead-blueposts` for official commentary, `keystoneloot-favorites` for gear lists.

**Two traps worth internalizing, because they fail silently, not loudly:**
1. Wowhead's tooltip API (`nether.wowhead.com/tooltip/spell/<id>`) serves **live** text by
   default. Without the `/ptr/` path segment, a PTR-redesigned talent will return the old,
   wrong description with no error — verified concretely on Orb Mastery, which reads
   completely differently between the two.
2. `raidbots.com/simbot/report/<id>/data.json` **302-redirects** to a different host
   (`raidbots.com/reports/<id>/data.json`). A client that doesn't follow redirects gets an
   empty 302 response and silently "succeeds" with no data.

The instinct both share: don't trust that a URL returning HTTP 200 means it returned the
*right* data. Spot-check the content against something independently known (a patch note,
a community-stated number) before building on it.

## Reasoning rules

- **Never infer an APL condition's direction from the ability name or from what "seems
  right."** `buff.arcane_soul.down` and `buff.arcane_soul.up` read similarly at a skim and
  mean opposite things; this project shipped a real bug from doing exactly that. The raw
  APL line is ground truth; a community explanation only sanity-checks your reading of it.
  Syntax, structural gates and vocabulary: [method/reading-an-apl.md](.claude/knowledge/method/reading-an-apl.md).
- **Think in resource economy, not "which button is biggest"** — generators, spenders, and
  the spender everything else feeds. Resolve what a talent does from data, never from its
  name; talents get redesigned under the same name. When a character's talents aren't
  exposed, confirm them from empirical evidence and say "confirmed via X" or "unverifiable":
  [method/resource-economy.md](.claude/knowledge/method/resource-economy.md).
- GCD, off-GCD, casts vs channels, and why target count decides which APL branches are
  reachable: [game/combat-system.md](.claude/knowledge/game/combat-system.md).

## Workflow this project follows for a report

1. Pull raw data first — save it under `data/` (durable reference, e.g. talent trees) or
   `scratch/` (per-report working extracts) before writing any prose about it. Prose gets
   written from the saved data, not from memory of having looked at it.
2. Pull exact numbers, not impressions — percentages, spellIds, exact condition text.
   Round only for display, never in the underlying extract.
3. When inferring something the data doesn't state outright (a talent pick, a hero tree),
   say what evidence supports it and what remains unverified, rather than presenting an
   inference as fact.
4. When corrected, re-derive from the saved source text rather than patching the
   conclusion — the bug is usually in how a raw line was read, not just in what was
   written down.
5. Put what you learned where the next session will look: a durable finding in
   `.claude/knowledge/` (and a line in its README), a reusable question about a log as a
   check in `tools/warcraftlogs/`, a dataset under `data/` via a tool and
   `tools/datalayout.py`.
