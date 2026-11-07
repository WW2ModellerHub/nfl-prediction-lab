"""One record per NFL game, backed by immutable timestamped pregame picks.

Never count revision snapshots as additional predictions, mark a game settled
before a verified final exists, or grade a forecast recorded at/after kickoff.
This summary is a read model of the immutable forecast-revisions ledger.
"""
from __future__ import annotations
import math

def metric(rows, correct_key, probability_key):
    n=len(rows)
    if not n:return {"games":0,"wins":0,"losses":0,"accuracy":None,
                      "brier":None,"logLoss":None}
    wins=sum(int(bool(x[correct_key])) for x in rows)
    brier=sum((x[probability_key]-x["outcomeHome"])**2 for x in rows)/n
    logloss=sum(-x["outcomeHome"]*math.log(max(.005,min(.995,x[probability_key])))-
                (1-x["outcomeHome"])*math.log(max(.005,min(.995,1-x[probability_key])))
                for x in rows)/n
    return {"games":n,"wins":wins,"losses":n-wins,
            "accuracy":round(wins/n,4),"brier":round(brier,6),
            "logLoss":round(logloss,6)}

def summarize(scored, groups, now, dt, valid, max_details=250):
    """Produce forward-only hit rate and transparent original-versus-latest log.

    scored: confirmed final-game comparisons from forecast_revisions.
    groups: all archived snapshots, keyed by gameId.
    dt/valid: same strict timestamp/probability validators as ledger.
    """
    results=[]
    used=set()
    for item in sorted(scored,key=lambda x:(x["kickoff"],x["gameId"]),reverse=True):
        gid=item["gameId"]
        if gid in used:raise ValueError("Duplicate graded prediction gameId: "+str(gid))
        used.add(gid)
        outcome=item["outcomeHome"]
        if outcome not in (0,1):continue
        original_pick=item["home"] if item["firstProbability"]>=.5 else item["away"]
        latest_pick=item["home"] if item["lastProbability"]>=.5 else item["away"]
        results.append({
            "gameId":gid,"season":item.get("season"),"week":item.get("week"),
            "kickoff":item["kickoff"],"home":item["home"],"away":item["away"],
            "homeScore":item["homeScore"],"awayScore":item["awayScore"],
            "winner":item["winner"],"outcomeHome":outcome,
            "originalPick":original_pick,"originalWinProbability":round(max(item["firstProbability"],1-item["firstProbability"]),5),
            "originalHomeProbability":item["firstProbability"],
            "originalCorrect":bool(item["firstCorrect"]),
            "originalRecordedAt":item["firstRecordedAt"],
            "latestPick":latest_pick,"latestWinProbability":round(max(item["lastProbability"],1-item["lastProbability"]),5),
            "latestHomeProbability":item["lastProbability"],
            "latestCorrect":bool(item["lastCorrect"]),
            "latestRecordedAt":item["lastRecordedAt"],
            "latestHoursBeforeKickoff":item["lastAgeHours"],
            "changed":bool(item["changed"]),
            "revisionCount":item["revisionsAfterFirst"],
            "hadQBReport":bool(item["lastQBEvidence"]),
            "latestPersonnelStatus":item["lastPersonnelStatus"],
            "improvementBrier":item["brierGain"]
        })
    def summary(rows):
        return {"games":len(rows),
                "original":metric(rows,"originalCorrect","originalHomeProbability"),
                "latest":metric(rows,"latestCorrect","latestHomeProbability")}
    completed=summary(results)
    seasons=sorted({x["season"] for x in results if x.get("season") is not None},reverse=True)
    by_season=[{"season":s,**summary([x for x in results if x["season"]==s])} for s in seasons]
    keys=sorted({(x.get("season"),x.get("week")) for x in results
                 if isinstance(x.get("season"),int) and isinstance(x.get("week"),int)},reverse=True)
    by_week=[{"season":season,"week":week,**summary([x for x in results if x.get("season")==season and x.get("week")==week])}
             for season,week in keys]
    most_recent=summary(results[:10])
    pending=[]
    awaiting=[]
    for gid,items in groups.items():
        if gid in used:continue
        choices=[x for x in items if valid(x.get("homeProbability"))
                 and dt(x.get("recordedAt")) and dt(x.get("kickoff"))
                 and dt(x["recordedAt"])<dt(x["kickoff"])]
        if not choices:continue
        choices.sort(key=lambda x:dt(x["recordedAt"]))
        first=next((x for x in choices if x.get("kind")=="first"),choices[0])
        latest=choices[-1]
        kickoff=dt(first.get("kickoff"))
        if not kickoff:continue
        row={"gameId":gid,"kickoff":kickoff.isoformat(),
             "home":first.get("home"),"away":first.get("away"),
             "originalPick":first.get("home") if first["homeProbability"]>=.5 else first.get("away"),
             "originalProbability":round(max(first["homeProbability"],1-first["homeProbability"]),5),
             "originalRecordedAt":first["recordedAt"],
             "latestPick":latest.get("home") if latest["homeProbability"]>=.5 else latest.get("away"),
             "latestProbability":round(max(latest["homeProbability"],1-latest["homeProbability"]),5),
             "latestRecordedAt":latest["recordedAt"],
             "revisions":max(0,len(choices)-1)}
        if kickoff>now:pending.append(row)
        else:awaiting.append(row)
    pending.sort(key=lambda x:(x["kickoff"],x["gameId"]))
    awaiting.sort(key=lambda x:(x["kickoff"],x["gameId"]),reverse=True)
    return {
        "schemaVersion":1,"generatedAt":now.isoformat(),
        "status":"timestamped-forward-grading",
        "trackedGames":len({gid for gid,items in groups.items()
                            if any(valid(x.get("homeProbability")) and
                                   dt(x.get("recordedAt")) and dt(x.get("kickoff")) and
                                   dt(x["recordedAt"])<dt(x["kickoff"]) for x in items)}),
        "completed":completed,"recent10":most_recent,
        "bySeason":by_season,"byWeek":by_week,
        "latestResults":results[:max_details],
        "allResults":results,
        "upcoming":pending[:80],"upcomingCount":len(pending),
        "awaitingFinal":awaiting[:30],"awaitingFinalCount":len(awaiting),
        "smallSample":completed["games"]<30,
        "note":"These are real timestamped forward predictions, NOT historical backtests. Every game counts once, irrespective of saved revisions. Original picks never change. Latest means the last actually recorded pre-kickoff pick, not necessarily a game-day estimate. Only official final scores available in nflverse schedules are graded; tied, unplayed, and unverified matches are excluded. Accuracy is favourite-pick win rate. Brier and log loss measure probability quality, and lower is better. Sample sizes below 30 are preliminary."
    }
