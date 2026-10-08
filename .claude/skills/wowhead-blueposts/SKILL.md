---
name: wowhead-blueposts
description: Retrieve recent "blue posts" — official posts by Blizzard Entertainment developers/community managers on the WoW forums, mirrored by Wowhead's Blue Tracker. Dumps each post's full text to a .txt file (posts can be long) and lists a title -> file mapping. Use whenever the user wants recent official Blizzard commentary — class tuning notes, hotfixes, developer notes — rather than community theorycrafting.
---

# Wowhead Blue Tracker

A "blue post" is a forum post made by a Blizzard Entertainment employee (historically
rendered in blue text on the official forums) — patch notes, class tuning changes,
developer commentary. Wowhead's **Blue Tracker** mirrors these from the official forums in
near-real-time. This skill covers pulling the most recent ones and dumping their full text
locally, since a single tuning post can run to hundreds of lines and isn't worth re-fetching
every time it's referenced.

No API key needed — everything here is a plain `curl` against public pages.

## Step 1 — list recent posts via RSS

```bash
curl -s -A "Mozilla/5.0" "https://www.wowhead.com/blue-tracker?rss" -o /tmp/bluetracker.rss
grep -o '<title>[^<]*</title>\|<link>[^<]*</link>\|<pubDate>[^<]*</pubDate>' /tmp/bluetracker.rss
```

The feed mixes two link shapes — **filter to the one you want**:

- `https://www.wowhead.com/blue-tracker/topic/<region>/<id>` — an actual forum **thread**
  containing one or more verbatim Blizzard posts. This is almost always what "a blue post"
  means, and what this skill targets by default.
- `https://www.wowhead.com/blue-tracker/news/<region>/<id>` — Wowhead's own news-article
  writeups (patch notes reposts, marketing announcements). Related, but not a verbatim
  developer post — skip these unless specifically asked for site news.

The feed also duplicates every item once per region (`us` and `eu` post the same content
minutes apart). Filter to one region — `us` is the natural default:

```bash
grep -o '<link>https://www\.wowhead\.com/blue-tracker/topic/us/[0-9]*</link>' /tmp/bluetracker.rss \
  | sed -E 's#</?link>##g'
```

This list is already newest-first. Take the top N links for "the last few" posts. Titles
for each link are the preceding `<title>` in the same feed — read them together rather than
re-grepping separately, e.g.:

```bash
grep -o '<title>[^<]*</title>\|<link>https://www\.wowhead\.com/blue-tracker/topic/us/[0-9]*</link>' \
  /tmp/bluetracker.rss
```
(titles and links interleave in document order; a title line is immediately followed by its
matching link line, `news`-category titles simply won't have a matching `topic/us` link
line next to them and can be visually skipped).

## Step 2 — fetch full text and dump to .txt

Each topic page **server-renders the full raw HTML of every blue post in that thread**
into a `<script type="application/json" id="data.blueTracker.topic">` tag
(`entries[].body`, `entries[].author`, `entries[].date`) — this is what the page's own JS
reads to paint the DOM, so reading the tag directly is more reliable than scraping rendered
markup (which requires a JS-executing fetch WebFetch can't do reliably here — the bare page
shell is nearly empty without it).

```bash
curl -sL -A "Mozilla/5.0" "https://www.wowhead.com/blue-tracker/topic/us/<id>" -o /tmp/post.html
perl tools/wowhead/extract_bluepost.pl /tmp/post.html > scratch/blueposts/<slug>.txt
```

`-L` is required — the bare numeric URL 301s to the slugged canonical URL. `extract_bluepost.pl`
pulls the JSON, strips/decodes the HTML into readable plain text (headers, list bullets,
and `<hr>` section breaks preserved as line breaks), and prints one `author — date` banner
per post in the thread (a thread like a running hotfix log can contain several dated
entries under one topic ID).

Pick a filename slug from the post title (lowercase, hyphenated) so the mapping in step 3
stays legible, e.g. `class-tuning-incoming-august-18.txt`.

## Step 3 — report the title → file mapping

After dumping N posts, list what was captured, e.g.:

| Title | File |
|---|---|
| Class Tuning Incoming – August 18 | `scratch/blueposts/class-tuning-incoming-august-18.txt` |
| World of Warcraft: Midnight Hotfixes - August 14, 2026 | `scratch/blueposts/midnight-hotfixes-aug-14.txt` |

Save dumps under `scratch/blueposts/` per this project's convention of `scratch/` for
per-task working extracts (see root `CLAUDE.md`) — they're a point-in-time capture, not a
durable reference.

## Linking back to the original forum thread

The numeric ID in a Wowhead `topic/<region>/<id>` URL **is the same ID as the official
Discourse forum thread** (verified: Wowhead topic `2336820` ↔
`us.forums.blizzard.com/en/wow/t/class-tuning-incoming-.../2336820`, and topic `2335871` ↔
the matching `.../season-2-class-tuning-plans/2335871`). To hand the user a canonical link
rather than the Wowhead mirror:

```
https://us.forums.blizzard.com/en/wow/t/<id>          # region=us
https://eu.forums.blizzard.com/en/wow/t/<id>           # region=eu
```

Discourse resolves the bare ID without needing the exact slug. This isn't guaranteed by any
documented API contract — it's an observed pattern — so if precision matters, confirm with
a quick web search for the post title rather than assuming it always holds.

## Caveats

- This scrapes Wowhead's server-rendered markup, not a documented API — if a fetch returns
  no `data.blueTracker.topic` script tag, the page structure likely changed; re-inspect a
  known-good URL's raw HTML (`curl -sL ... | grep -o 'data.blueTracker.topic'`) before
  assuming the post itself is missing.
- `extract_bluepost.pl` requires Perl's `JSON::PP` and `HTML::Entities` — both are core
  modules bundled with any standard Perl (including Git for Windows' bundled Perl used
  throughout this project's tooling), so no separate install should be needed.
- The RSS feed is capped at recent history (roughly the last ~50 items across both
  categories and regions) — it's a "recent activity" stream, not a searchable archive. For
  anything older, search the official forums or `bluetracker.gg` directly instead.
