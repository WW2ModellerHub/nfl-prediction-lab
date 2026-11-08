"""Genuinely archived pregame forecasts for recently kicked-off games.

Never generate an in-play win chance from a pregame probability. Only use
predictions that were actually committed BEFORE that fixture's kickoff.
NFL schedule results are separate; the browser can enrich with an ESPN
scoreboard feed, marked as a different source.
"""
from __future__ import annotations
from datetime import datetime, timezone, timedelta
import math

def _aware(value):
    try:
        d=value if isinstance(value,datetime) else datetime.fromisoformat(str(value).replace("Z","+00:00"))
        return d.astimezone(timezone.utc) if d.tzinfo else None
    except (ValueError, TypeError, OverflowError):return None

def make_recent_kickoffs(schedule,revisions,now,max_hours=30):
    current=_aware(now)
    if current is None:raise ValueError("Timezone-aware update time required")
    eligible={}
    for game in schedule:
        kickoff=_aware(game.get("kickoff"))
        if not kickoff or not current>=kickoff or current-kickoff>timedelta(hours=max_hours):continue
        if not game.get("id") or not game.get("home") or not game.get("away"):continue
        eligible[str(game["id"])]=(game,kickoff)
    saved={}
    for row in revisions:
        if not isinstance(row,dict):continue
        gid=str(row.get("gameId"))
        hit=eligible.get(gid)
        if not hit:continue
        game,kick=hit
        published=_aware(row.get("recordedAt"))
        saved_kick=_aware(row.get("kickoff"))
        prob=row.get("homeProbability")
        if (not published or published>current or published>=kick or
            not saved_kick or saved_kick!=kick or
            not isinstance(prob,(int,float)) or isinstance(prob,bool) or
            not math.isfinite(prob) or not 0<prob<1):continue
        # Only same-fixture snapshots. Team-name mismatch is not accepted.
        if row.get("home")!=game["home"] or row.get("away")!=game["away"]:continue
        saved.setdefault(gid,[]).append((published,row))
    result=[]
    for gid,(game,kick) in eligible.items():
        observations=sorted(saved.get(gid,[]),key=lambda entry:entry[0])
        if not observations:continue
        first=next((row for _,row in observations if row.get("kind")=="first"),observations[0][1])
        latest=observations[-1][1]
        p=round(float(latest["homeProbability"]),5)
        result.append({
            "id":gid,"season":game.get("season"),"week":game.get("week"),
            "home":game["home"],"away":game["away"],
            "kickoff":kick.isoformat(),"archivedPregame":True,
            "homeProbability":p,"awayProbability":round(1-p,5),
            "originalHomeProbability":round(float(first["homeProbability"]),5),
            "originalRecordedAt":first["recordedAt"],
            "lastPregameRecordedAt":latest["recordedAt"],
            "model":latest.get("model"),
            "predMargin":latest.get("predMargin"),"predTotal":latest.get("predTotal"),
            "verificationLevel":latest.get("verificationLevel"),
            "personnelStatus":latest.get("personnelStatus"),
            "revisions":max(0,len(observations)-1),
            "finalScoreFromSchedule":({
                "home":game.get("home_score"),"away":game.get("away_score"),
                "source":"nflverse schedules — not a live score feed"}
                if game.get("home_score") is not None and game.get("away_score") is not None else None)
        })
    result.sort(key=lambda g:(g["kickoff"],g["id"]),reverse=True)
    return result[:24]
