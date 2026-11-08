"""Pregame NFL availability evidence from the dated NFL injury-report mirror.

The public nflverse injury release mirrors official NFL weekly report fields
(report_status, practice_status, date_modified, season/week). It is NOT the
NFL's own endpoint, a confirmed starting-lineup feed or the inactive list.

Only as-of dated, same-week *game status* is usable for an availability
decision. A practice DNP is never equivalent to game OUT. Missing rows are
never converted to healthy. Every feed failure remains explicit.
"""
from __future__ import annotations

from datetime import datetime, timezone, timedelta
import csv
import io
import urllib.request
from qb_injuries import normalized_team, dt_value

URL="https://github.com/nflverse/nflverse-data/releases/download/injuries/injuries_{season}.csv"
OFFICIAL_PAGE="https://www.nfl.com/injuries/"
GAME_STATUSES={"OUT","DOUBTFUL","QUESTIONABLE","INJURED RESERVE","IR","INACTIVE",
               "OUT FOR SEASON"}
NO_GAME_STATUS={"","NA","N/A","NONE","NULL","NAN","--"}
MAX_BYTES=32_000_000

def stamp(v):
    d=dt_value(v)
    return d.astimezone(timezone.utc) if d and d.tzinfo else None

def norm(name):
    return "".join(c for c in str(name or "").casefold() if c.isalnum())

def status(v):
    s=str(v or "").strip().upper()
    if s in NO_GAME_STATUS:return None
    if s in ("D","DOUT","DID NOT PRACTICE"):return None
    if s in ("DOUBTFUL FOR GAME",):return "DOUBTFUL"
    if s in ("INJURED RESERVE","IR"):return "INJURED RESERVE"
    return s if s in GAME_STATUSES else None

def parse(text,season,now):
    now=stamp(now)
    if now is None:raise ValueError("Timestamp must be timezone-aware")
    rows=[]
    data=csv.DictReader(io.StringIO(text))
    must={"season","week","team","full_name","position","report_status","practice_status","date_modified"}
    if not data.fieldnames or not must.issubset(data.fieldnames):
        raise ValueError("nflverse injury CSV does not provide required weekly report fields")
    for r in data:
        try:ys=int(r.get("season") or 0);week=int(r.get("week") or 0)
        except (ValueError,TypeError):continue
        if ys!=season or week not in range(1,24):continue
        team=normalized_team(r.get("team"))
        name=str(r.get("full_name") or "").strip()
        at=stamp(r.get("date_modified"))
        game_status=status(r.get("report_status"))
        if not team or not name:continue
        if at and at>now:continue # future-dated data cannot be inserted before kickoff
        rows.append({
            "season":ys,"week":week,"team":team,"name":name,"nameKey":norm(name),
            "gsisId":str(r.get("gsis_id") or "").strip(),
            "position":str(r.get("position") or "").strip().upper(),
            "gameStatus":game_status,
            "practiceStatus":str(r.get("practice_status") or "").strip() or None,
            "injury":str(r.get("report_primary_injury") or r.get("practice_primary_injury") or "").strip(),
            "reportDate":(at or now).isoformat(),
            "sourceUpdatedAt":at.isoformat() if at else None,
            "observedAt":now.isoformat(),
            "timestampBasis":"row-updated" if at else "download-observation",
            "source":"NFL weekly report mirrored by nflverse",
            "sourceType":"official-report-derived-mirror",
            "officialNFLDomain":False,
            "sourceURL":URL.format(season=ys),
            "officialReferenceURL":OFFICIAL_PAGE,
            "starterConfirmed":False,
            "inactiveConfirmed":False
        })
    # One entry per player per game-week, prefer newest dated observation.
    most_recent={}
    for r in rows:
        k=(r["season"],r["week"],r["team"],r["gsisId"] or r["nameKey"])
        prior=most_recent.get(k)
        if prior is None or (r["reportDate"] or "")>(prior["reportDate"] or ""):
            most_recent[k]=r
    return list(most_recent.values())

def fetch(season,now,opener=None):
    now=stamp(now)
    if now is None:raise ValueError("Timestamp must be timezone-aware")
    url=URL.format(season=season)
    meta={"status":"unavailable","source":url,"sourceType":"official-report-derived-mirror",
          "officialReference":OFFICIAL_PAGE,"observedAt":now.isoformat(),
          "records":0,"dated":0,"gameStatuses":0,"teamsCovered":0,
          "note":"Source copies NFL weekly game-status and practice fields. Not a direct NFL.com feed, coach starter confirmation or game-day inactive feed."}
    try:
        request=urllib.request.Request(url,headers={"User-Agent":"NFLPredictionLab/3.0 (personal research)",
                                                   "Accept":"text/csv"})
        with (opener or urllib.request.urlopen)(request,timeout=25) as response:
            raw=response.read(MAX_BYTES+1)
        if len(raw)>MAX_BYTES:raise ValueError("Injury source exceeds size cap")
        records=parse(raw.decode("utf-8-sig"),season,now)
        meta.update(status=("loaded" if any(r["timestampBasis"]=="row-updated" for r in records)
                            else "snapshot-only" if records else "empty"),records=len(records),
                    dated=sum(r["timestampBasis"]=="row-updated" for r in records),
                    snapshotObserved=sum(r["timestampBasis"]=="download-observation" for r in records),
                    gameStatuses=sum(bool(r["gameStatus"] and r["reportDate"]) for r in records),
                    teamsCovered=len({r["team"] for r in records}))
        return records,meta
    except (OSError,TimeoutError,UnicodeError,ValueError,TypeError) as exc:
        meta["error"]=f"{type(exc).__name__}: {str(exc)[:210]}"
        return [],meta

def from_existing(rows,season,now):
    """Reuse already downloaded FULL-mode injury CSV instead of fetching twice."""
    now=stamp(now)
    result=[]
    for r in rows:
        at=r.get("asOf")
        if r.get("season")!=season or not at or at>now:continue
        s=status(r.get("reportStatus"))
        result.append({"season":season,"week":r.get("week"),"team":r.get("team"),
            "name":r.get("name"),"nameKey":norm(r.get("name")),
            "gsisId":r.get("id"),"position":r.get("position"),
            "gameStatus":s,"practiceStatus":r.get("practiceStatus") or None,
            "injury":r.get("injury"),"reportDate":at.isoformat(),
            "sourceUpdatedAt":at.isoformat() if r.get("timestampBasis")=="row-updated" else None,
            "observedAt":now.isoformat(),
            "timestampBasis":r.get("timestampBasis"),
            "source":"NFL weekly report mirrored by nflverse",
            "sourceType":"official-report-derived-mirror",
            "officialNFLDomain":False,
            "sourceURL":URL.format(season=season),
            "officialReferenceURL":OFFICIAL_PAGE,
            "starterConfirmed":False,"inactiveConfirmed":False})
    meta={"status":("loaded" if any(x["timestampBasis"]=="row-updated" for x in result)
                         else "snapshot-only" if result else "unavailable"),
          "source":URL.format(season=season),
          "sourceType":"official-report-derived-mirror",
          "officialReference":OFFICIAL_PAGE,"observedAt":now.isoformat(),
          "records":len(result),"dated":sum(x["timestampBasis"]=="row-updated" for x in result),
          "snapshotObserved":sum(x["timestampBasis"]=="download-observation" for x in result),
          "gameStatuses":sum(bool(x["gameStatus"] and x["timestampBasis"]=="row-updated") for x in result),
          "teamsCovered":len({x["team"] for x in result}),
          "note":"Historical full-refresh injury report rows reused; undated snapshot rows remain non-authoritative."}
    return result,meta

def attach(game,records,meta,now):
    """Attach only the same-week, strictly prior-to-kickoff availability."""
    now=stamp(now);kick=stamp(game.get("kickoff"))
    if not now or not kick:raise ValueError("Missing valid current time or kickoff")
    cutoff=min(now,kick-timedelta(microseconds=1))
    groups={}
    for side in ("home","away"):
        team=game.get(side)
        rows=[]
        for r in records:
            if r.get("team")!=team or r.get("season")!=game.get("season") or r.get("week")!=game.get("week"):continue
            at=stamp(r.get("reportDate"))
            if not at or at>cutoff or r.get("timestampBasis") not in ("row-updated","download-observation"):continue
            # An undated report can be observed prospectively *now*, but
            # cannot be asserted to have existed before that download.
            if r.get("timestampBasis")=="download-observation" and at>now:continue
            # Old record from a different game-week should not qualify even
            # if upstream incorrectly assigned it to the current week.
            if cutoff-at>timedelta(days=11):continue
            rows.append({k:v for k,v in r.items() if k not in ("nameKey",)})
        rows.sort(key=lambda r:(r["position"]!="QB",r["name"]))
        qb=[r for r in rows if r.get("position")=="QB"]
        groups[side]={"team":team,"rows":rows[:50],"qbs":qb[:10],
                      "reportCount":len(rows),
                      "qualifiedQBOut":[{"name":r["name"],"status":r["gameStatus"],"reportDate":r["reportDate"]}
                           for r in qb if r["gameStatus"] in ("OUT","DOUBTFUL","INJURED RESERVE","INACTIVE","OUT FOR SEASON")],
                      "isWeeklyReportAvailable":bool(rows)}
    game["officialInjuryEvidence"]={
        "status":meta.get("status","unavailable"),
        "source":meta.get("source"),"sourceType":"official-report-derived-mirror",
        "observedAt":meta.get("observedAt"),"week":game.get("week"),"season":game.get("season"),
        "home":groups["home"],"away":groups["away"],
        "notes":"NFL weekly report fields mirrored by nflverse. If original date_modified is absent, rows are prospective observations at DOWNLOAD time only, never retrospectively backdated. An unlisted player is UNKNOWN; practice DNP is not an OUT designation. Not a confirmed starter or inactive list."}
    return game
