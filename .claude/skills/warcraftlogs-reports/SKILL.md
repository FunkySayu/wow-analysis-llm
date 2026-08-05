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
`expires_in` is ~360 days for a client-credentials app token — cache it (e.g. write
to a scratch file) instead of re-requesting per query.

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

## Rate limits

```json
{"query": "query { rateLimitData { limitPerHour pointsSpentThisHour } }"}
```

Each requested field/nesting level costs points against an hourly budget — keep
queries scoped to the fields and fight IDs you actually need.
