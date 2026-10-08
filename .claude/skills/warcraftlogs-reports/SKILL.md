---
name: warcraftlogs-reports
description: Query WarcraftLogs reports (fight lists, kill/wipe status, damage and cast breakdowns) via the WCL API v2 GraphQL endpoint, using the OAuth client-credentials app configured in .env. Use whenever the user wants to inspect a specific warcraftlogs.com/reports/<code> link.
---

# WarcraftLogs Report Analysis

WarcraftLogs' public API is GraphQL-based ("API v2"). This project has an OAuth
client-credentials app already registered — credentials live in `.env` at the repo
root as `WARCRAFTLOGS_CLIENT_ID` / `WARCRAFTLOGS_CLIENT_SECRET`. This app can only
read data that's already public on the site (no private/unlisted reports, no
user identity) — that's sufficient for pulling any report the user links.

## Step 1 — get an access token

`POST https://www.warcraftlogs.com/oauth/token`, HTTP Basic auth
(`client_id:client_secret`), body `grant_type=client_credentials`.

```bash
set -a && source .env && set +a
curl -s -X POST https://www.warcraftlogs.com/oauth/token \
  -u "$WARCRAFTLOGS_CLIENT_ID:$WARCRAFTLOGS_CLIENT_SECRET" \
  -d "grant_type=client_credentials"
```

Returns `{"token_type":"Bearer","expires_in":31104000,"access_token":"..."}`.
`expires_in` is ~360 days for a client-credentials app token — cache it instead of
re-requesting per query (`tools/warcraftlogs/lib/wclapi.py` already caches the token and
every response in `.wclcache/`).

**Before hand-writing a query, check `tools/warcraftlogs/`.** It has ~35 reusable checks
(`run.py <check|group> -r <report> -a <actor> -f raid|dungeon|<ids>`) covering rotation,
cooldowns, consumables, peers and fight structure. Its README lists them and the API traps
they already work around. Add a new question there as a check rather than as a one-off
script.

## Step 2 — query the GraphQL API

Endpoint: `POST https://www.warcraftlogs.com/api/v2/client`, JSON body
`{"query": "..."}`, header `Authorization: Bearer <access_token>`.

Full schema / interactive explorer: https://www.warcraftlogs.com/api/docs

The report **code** is the last path segment of a report URL, e.g. for
`https://www.warcraftlogs.com/reports/vAtQGNpDqJHyw9mn` the code is
`vAtQGNpDqJHyw9mn`.

### List fights (kill/wipe status)

```json
{"query": "query { reportData { report(code: \"vAtQGNpDqJHyw9mn\") { title fights { id name kill difficulty encounterID startTime endTime } } } }"}
```

```bash
curl -s -X POST https://www.warcraftlogs.com/api/v2/client \
  -H "Authorization: Bearer $TOKEN" -H "Content-Type: application/json" \
  --data-binary @query.json
```

**Gotcha — filter out non-encounter pulls.** Fights with `encounterID: 0` (and
`kill: null`, `difficulty: null`) aren't real boss/target pulls — they're things
like a stray target-dummy segment. Count only fights with `encounterID != 0` as
"total fights", and among those, `kill: true` as completed/killed.

Verified against report `vAtQGNpDqJHyw9mn`: 11 raw fight entries, one of which
(`"Rat"`, `encounterID: 0`) is a non-encounter pull → **10 real fights**, of which
**6 have `kill: true`** — matches the "6 completed / 10 total" the user expects
before trusting any further analysis of this report.

### Damage/cast breakdown for rotation analysis

- `table(dataType: DamageDone, fightIDs: [1,3,5,7,8,9])` — damage-by-ability
  summary table, good for "what did I actually spend my damage on".
- `events(dataType: Casts, sourceID: <playerActorID>, fightIDs: [...])` — full
  cast timeline. This is what you diff against a Raidbots `action_sequence` to
  see where your rotation deviated from optimal play.
- `reportData.report(code: "...").playerDetails(fightIDs: [...])` to resolve
  actor names/IDs to `sourceID` for the queries above.

### Comparing against other players

`worldData.encounter(id:).characterRankings(className:, specName:, difficulty:, metric: dps,
page:, includeCombatantInfo: true)` returns ranked parses with each player's gear and talents —
no per-report calls needed. `filter: "date.<startMs>.<endMs>"` (undocumented, verified)
restricts to a time window. Three things it does not do:

- **It paginates to page 20 at most** (2,000 parses). On a popular spec that floor sits around
  the 84th percentile, so "compare against average players" is not possible; a rare spec's list
  can end early (page 13 on Mythic Twin Fangs Balance) and then covers the whole field.
- **It carries no percentile.** Read `rankPercent` from each sampled report's own
  `reportData.report.rankings` (one extra query per log).
- **`bracketData` is not equipped item level.** Compute ilvl from `CombatantInfo` gear.

How to sample a comparison pool (stratify, report `n`, check the metric tracks rank) is in
`.claude/knowledge/method/analysing-a-pull.md`.

`events(dataType: CombatantInfo)` gives a player's gear (with `permanentEnchant` and `gems`
per slot), auras at pull, and a `talentTree` of `{nodeID, id, rank}` that maps 1:1 onto the
entry ids in `data/classes/<class>/<spec>/<patch>_talents.json` — the loadout string never
needs decoding.

## Silent traps

Each of these returns wrong or empty data with no error. The evidence for each is in the
file named; `tools/warcraftlogs/README.md` ("Traps these checks had to work around") has
more.

| trap | where it is documented |
|---|---|
| `sourceID` + `hostilityType: Enemies` in one events query returns zero rows | tools README |
| `targetID` (or `filterExpression: "target.id = N"`) on `DamageTaken` drops enemy-sourced hits or returns nothing — query the window unfiltered, filter client-side | `method/boss-death-timelines.md` trap 1 |
| debuff apply/refresh/remove events are keyed on the aura on the target, not the caster — rebuild one player's DoT uptime from damage ticks | `classes/druid/balance-druid-12.1.md` |
| the Casts *table* keeps only the top 5 abilities per player — utility never appears; use `events` | `dungeons/12_1/midnight-s2-dungeons.md` |
| `table(dataType: Dispels)` rows are at `data.entries[0].entries` | `dungeons/12_1/midnight-s2-dungeons.md` |
| one ability is several spell ids, and the journal / tooltip id is often not the logged one — resolve by name from `masterData.abilities` | `raid/12_1/venomous_abyss/sszorak-mythic.md` |
| a buff check on the cast misses lust that landed from someone else (eight lust ids, not four) — check the buff received | `classes/druid/balance-druid-12.1.md` |
| the Deaths table's `events` are capped at three and its window is adaptive; `overkill` appears only on the killing blow | `method/boss-death-timelines.md` traps 3–4 |
| `includeResources: true` is what attaches `hitPoints`, `x`/`y` and the source's buffs to events | tools README |
| the `graph` endpoint smooths to ~40s buckets; target-view `activeTime` saturates whenever a DoT ticks | `classes/dps-specs-boss-profile-12.1.md` |

(Knowledge paths are under `.claude/knowledge/`.)

## Rate limits

```json
{"query": "query { rateLimitData { limitPerHour pointsSpentThisHour } }"}
```

Each requested field/nesting level costs points against an hourly budget — keep
queries scoped to the fields and fight IDs you actually need.
