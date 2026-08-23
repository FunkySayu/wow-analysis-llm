"""WarcraftLogs API v2 client with on-disk caching.

Credentials come from `.env` at the repo root (WARCRAFTLOGS_CLIENT_ID /
WARCRAFTLOGS_CLIENT_SECRET). The OAuth token is cached in `.wclcache/token.json`
(~360 day lifetime) and every event/table fetch is cached under `.wclcache/<code>/`
so re-running a check costs nothing.

Run under WSL python from the repo root:
    wsl.exe -d Ubuntu -e python3 tools/wcl/run.py <check> ...
"""

import base64
import hashlib
import json
import os
import sys
import time
import urllib.parse
import urllib.request

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
CACHE = os.path.join(ROOT, ".wclcache")
ENDPOINT = "https://www.warcraftlogs.com/api/v2/client"
TOKEN_URL = "https://www.warcraftlogs.com/oauth/token"


def _env():
    path = os.path.join(ROOT, ".env")
    out = {}
    if os.path.exists(path):
        for line in open(path, encoding="utf-8"):
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            k, v = line.split("=", 1)
            out[k.strip()] = v.strip().strip('"').strip("'")
    return out


def token(refresh=False):
    os.makedirs(CACHE, exist_ok=True)
    tp = os.path.join(CACHE, "token.json")
    if not refresh and os.path.exists(tp):
        try:
            t = json.load(open(tp))
            if t.get("obtained", 0) + t.get("expires_in", 0) - 86400 > time.time():
                return t["access_token"]
        except Exception:
            pass
    e = _env()
    cid, sec = e.get("WARCRAFTLOGS_CLIENT_ID"), e.get("WARCRAFTLOGS_CLIENT_SECRET")
    if not cid or not sec:
        sys.exit("Missing WARCRAFTLOGS_CLIENT_ID / _SECRET in .env")
    body = urllib.parse.urlencode({"grant_type": "client_credentials"}).encode()
    auth = base64.b64encode(f"{cid}:{sec}".encode()).decode()
    req = urllib.request.Request(
        TOKEN_URL, data=body,
        headers={"Authorization": "Basic " + auth,
                 "Content-Type": "application/x-www-form-urlencoded"})
    with urllib.request.urlopen(req, timeout=60) as r:
        t = json.loads(r.read().decode())
    t["obtained"] = time.time()
    json.dump(t, open(tp, "w"))
    return t["access_token"]


def query(gql, variables=None, retries=3):
    """Raw GraphQL POST. Raises on transport failure; prints GraphQL errors."""
    payload = {"query": gql}
    if variables:
        payload["variables"] = variables
    data = json.dumps(payload).encode()
    last = None
    for attempt in range(retries):
        try:
            req = urllib.request.Request(
                ENDPOINT, data=data,
                headers={"Authorization": "Bearer " + token(),
                         "Content-Type": "application/json"})
            with urllib.request.urlopen(req, timeout=180) as r:
                out = json.loads(r.read().decode())
            if "errors" in out:
                print("GraphQL errors:", json.dumps(out["errors"])[:800], file=sys.stderr)
            return out
        except Exception as exc:                      # noqa: BLE001
            last = exc
            if attempt == retries - 1:
                break
            time.sleep(2 + 3 * attempt)
    raise RuntimeError(f"WCL query failed after {retries} attempts: {last}")


def _cache_path(code, key):
    d = os.path.join(CACHE, code)
    os.makedirs(d, exist_ok=True)
    return os.path.join(d, hashlib.sha1(key.encode()).hexdigest()[:20] + ".json")


def cached(code, key, producer, refresh=False):
    """Memoise `producer()` to disk under this report's cache directory."""
    p = _cache_path(code, key)
    if not refresh and os.path.exists(p):
        try:
            return json.load(open(p))
        except Exception:
            pass
    val = producer()
    json.dump(val, open(p, "w"))
    return val


# ----------------------------------------------------------------- report data

def report_meta(code, refresh=False):
    """Fights + player/NPC actor tables for a report."""
    def go():
        r = query('''query { reportData { report(code: "%s") {
              title startTime endTime zone { id name }
              fights { id name kill difficulty encounterID startTime endTime
                       keystoneLevel gameZone { id name } }
              masterData { actors { id name type subType } }
            } } }''' % code)
        return r["data"]["reportData"]["report"]
    return cached(code, "meta", go, refresh)


def actor_id(code, name):
    for a in report_meta(code)["masterData"]["actors"]:
        if a["name"].lower() == name.lower() and a["type"] == "Player":
            return a["id"]
    raise SystemExit(f'Player "{name}" not found in report {code}')


def actor_names(code):
    return {a["id"]: a["name"] for a in report_meta(code)["masterData"]["actors"]}


def fights(code, which="all"):
    """which: all | encounters | kills | raid | dungeon | comma-separated ids"""
    fs = report_meta(code)["fights"]
    if which and which[0].isdigit():
        want = {int(x) for x in which.split(",")}
        return [f for f in fs if f["id"] in want]
    if which == "all":
        return fs
    if which == "encounters":
        return [f for f in fs if f["encounterID"]]
    if which == "kills":
        return [f for f in fs if f.get("kill")]
    if which == "raid":
        return [f for f in fs if f["encounterID"] and not f.get("keystoneLevel")]
    if which == "dungeon":
        return [f for f in fs if f.get("keystoneLevel")]
    raise SystemExit(f"unknown fight selector: {which}")


def events(code, fight_id, data_type, source_id=None, ability_id=None,
           hostility=None, resources=False, target_id=None, refresh=False):
    """Paged event fetch, cached. Returns a flat list of event dicts."""
    key = f"ev|{fight_id}|{data_type}|{source_id}|{ability_id}|{hostility}|{resources}|{target_id}"

    def go():
        out, ts, page = [], None, 0
        while True:
            f = [f"fightIDs: [{fight_id}]", f"dataType: {data_type}", "limit: 10000"]
            if source_id is not None:
                f.append(f"sourceID: {source_id}")
            if target_id is not None:
                f.append(f"targetID: {target_id}")
            if ability_id is not None:
                f.append(f"abilityID: {ability_id}")
            if hostility:
                f.append(f"hostilityType: {hostility}")
            if resources:
                f.append("includeResources: true")
            if ts is not None:
                f.append(f"startTime: {ts}")
            r = query('query { reportData { report(code: "%s") { events(%s) '
                      '{ data nextPageTimestamp } } } }' % (code, ", ".join(f)))
            ev = r["data"]["reportData"]["report"]["events"]
            out.extend(ev["data"])
            ts = ev.get("nextPageTimestamp")
            page += 1
            if not ts or page > 80:
                break
        return out
    return cached(code, key, go, refresh)


def table(code, fight_ids, data_type, source_id=None, refresh=False):
    ids = ",".join(str(i) for i in fight_ids)
    key = f"tbl|{ids}|{data_type}|{source_id}"

    def go():
        src = f", sourceID: {source_id}" if source_id is not None else ""
        r = query('query { reportData { report(code: "%s") { table(dataType: %s, '
                  'fightIDs: [%s]%s) } } }' % (code, data_type, ids, src))
        return r["data"]["reportData"]["report"]["table"]["data"]
    return cached(code, key, go, refresh)
