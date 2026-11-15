"""Sleeper depth charts as a second, separately maintained QB1 source.

The existing QB cross-check compares nflverse against ESPN, but nflverse depth
charts are derived from ESPN, so agreement between them is not independent.
Sleeper maintains its own player database (depth-chart order and injury
status), so a Sleeper QB1 that matches the projected starter is treated as
independent corroboration by the pregame verification gate.

Nothing here changes a win probability or names an official starter. Sleeper
is unofficial; its depth order is a projection like the others. A Sleeper
disagreement is surfaced for review rather than silently resolved.

Sleeper asks clients to fetch /players/nfl at most about once a day per
caller; the refresh workflow runs four times a day, which is one request
per run.
"""
from __future__ import annotations
import json
import urllib.request
from datetime import datetime, timezone, timedelta

URL = "https://api.sleeper.app/v1/players/nfl"
SOURCE = "Sleeper player database (unofficial depth charts)"
# Sleeper team codes → nflverse codes used throughout the model.
TEAM_ALIASES = {"LAR": "LA", "JAC": "JAX", "WSH": "WAS", "OAK": "LV", "SD": "LAC", "STL": "LA"}
UNAVAILABLE = {"OUT", "IR", "PUP", "SUS", "NA", "DNR", "COV", "INJURED RESERVE", "SUSPENDED"}
SUFFIXES = {"jr", "sr", "ii", "iii", "iv", "v"}
MAX_AGE = timedelta(hours=72)


def clean_name(value):
    words = [w for w in "".join(c if c.isalnum() or c.isspace() else " " for c in str(value or "").casefold()).split()
             if w not in SUFFIXES]
    return "".join(words)


def _aware(value):
    try:
        d = value if isinstance(value, datetime) else datetime.fromisoformat(str(value).replace("Z", "+00:00"))
        return d.astimezone(timezone.utc) if d.tzinfo else None
    except (ValueError, TypeError, OverflowError):
        return None


def _order(value):
    try:
        n = int(value)
        return n if n > 0 else None
    except (TypeError, ValueError):
        return None


def team_qbs(players):
    """Group Sleeper QBs by nflverse team code, ordered by depth chart."""
    teams = {}
    items = players.values() if isinstance(players, dict) else players or []
    for p in items:
        if not isinstance(p, dict):
            continue
        pos = str(p.get("depth_chart_position") or p.get("position") or "").upper()
        fantasy = [str(x).upper() for x in (p.get("fantasy_positions") or [])]
        if pos != "QB" and not (str(p.get("position") or "").upper() == "QB" or "QB" in fantasy):
            continue
        team = str(p.get("team") or "").upper()
        if not team or p.get("active") is False:
            continue
        team = TEAM_ALIASES.get(team, team)
        name = p.get("full_name") or " ".join(x for x in (p.get("first_name"), p.get("last_name")) if x)
        if not name:
            continue
        teams.setdefault(team, []).append({
            "name": name, "order": _order(p.get("depth_chart_order")),
            "injuryStatus": (str(p.get("injury_status")).strip() or None) if p.get("injury_status") else None,
            "gsisId": str(p.get("gsis_id") or "").strip() or None,
            "sleeperId": str(p.get("player_id") or "") or None})
    for team, rows in teams.items():
        rows.sort(key=lambda r: (r["order"] is None, r["order"] or 99, r["name"]))
    return teams


def qb1(rows):
    """Sleeper's QB1, skipping players Sleeper itself lists as unavailable.

    Returns (starter, listed_first). ``listed_first`` is the depth-chart #1
    even if unavailable, so a stale chart can be shown. Ties at the top rank
    give no starter: an ambiguous chart is not evidence.
    """
    ranked = [r for r in rows or [] if r["order"] is not None]
    if not ranked:
        return None, None
    listed_first = ranked[0]
    available = [r for r in ranked if str(r.get("injuryStatus") or "").upper() not in UNAVAILABLE]
    if not available:
        return None, listed_first
    top = available[0]
    if sum(1 for r in available if r["order"] == top["order"]) > 1:
        return None, listed_first
    return top, listed_first


def fetch(now=None, opener=None, timeout=60):
    """Download Sleeper players once; return (teams, metadata). Never raises."""
    now = now or datetime.now(timezone.utc)
    meta = {"status": "unavailable", "source": SOURCE, "url": URL, "observedAt": None, "teams": 0, "errors": []}
    try:
        req = urllib.request.Request(URL, headers={"User-Agent": "NFLPredictionLab/3.2 (personal research)",
                                                   "Accept": "application/json"})
        with (opener or urllib.request.urlopen)(req, timeout=timeout) as response:
            payload = json.loads(response.read().decode("utf-8"))
        teams = team_qbs(payload)
    except Exception as exc:  # network, JSON, shape: the gate simply stays at review
        meta["errors"].append(f"{type(exc).__name__}: {str(exc)[:160]}")
        return {}, meta
    meta.update(status="loaded" if teams else "empty", observedAt=now.isoformat(), teams=len(teams))
    return teams, meta


def attach(game, teams, meta, now):
    """Add Sleeper QB1 evidence to ``game['qbSourceEvidence'][side]``."""
    now = _aware(now)
    evidence = game.setdefault("qbSourceEvidence", {"status": "unavailable"})
    observed = _aware(meta.get("observedAt"))
    current = bool(meta.get("status") == "loaded" and observed and now and timedelta(0) <= now - observed <= MAX_AGE)
    qbs = game.get("qbIntelligence") or {}
    for side in ("home", "away"):
        src = evidence.setdefault(side, {})
        rows = teams.get(game.get(side)) or []
        starter, listed = qb1(rows)
        q = qbs.get(side) or {}
        projected = q.get("qb") if q.get("basis") == "depth_chart_projection" else None
        pid = str(q.get("playerId") or "").strip()
        def same(r):
            return bool(r and projected and (clean_name(r["name"]) == clean_name(projected) or
                                             (pid and r.get("gsisId") and r["gsisId"] == pid)))
        projected_row = next((r for r in rows if same(r)), None)
        agrees = bool(current and starter and same(starter))
        src.update({
            "sleeperStatus": meta.get("status", "unavailable"),
            "sleeperObservedAt": observed.isoformat() if observed else None,
            "sleeperProjectedQB": starter["name"] if starter else None,
            "sleeperListedFirst": listed["name"] if listed else None,
            "sleeperListedFirstStatus": listed.get("injuryStatus") if listed else None,
            "sleeperDepth": [{"name": r["name"], "order": r["order"], "injuryStatus": r["injuryStatus"]}
                             for r in rows[:4]],
            "sleeperProjectedQBInjury": projected_row.get("injuryStatus") if projected_row else None,
            "sleeperAgrees": agrees,
            "sleeperConflict": bool(current and starter and projected and not same(starter)),
            "independentConfirmation": agrees,
            "corroborationBasis": ("Sleeper depth chart (separately maintained) matches the projected QB" if agrees else
                                   "ESPN-derived mirror comparison only; Sleeper did not corroborate")})
    if current:
        evidence["independentSource"] = SOURCE
    return game
