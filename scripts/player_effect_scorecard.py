"""Forward-only, paired player-effect evaluation for recorded NFL predictions.

Every graded row compares the published probability against the no-player
probability saved at THE SAME pre-kickoff observation. No reconstruction,
backfilling, postgame lineup knowledge, or averaging revision snapshots.
One selected observation per completed game (latest eligible fresh effect).
The scorecard measures correlation with outcomes; it never activates weights.
"""
from __future__ import annotations
from datetime import timedelta

QB_KEYS=("qb-statistical","qb-replacement")
INJURY_KEYS=("other-injuries",)
EFFECT_KEYS=QB_KEYS+INJURY_KEYS

def _selected(hist,kick,dt,valid):
    candidates=[]
    for item in hist:
        at=dt(item.get("recordedAt"))
        saved_kick=dt(item.get("kickoff"))
        if not at or not saved_kick or at>=kick or at>=saved_kick:
            continue
        if item.get("provisionalPlayerApplied") is not True:
            continue
        if item.get("personnelSourceMode")!="fresh":
            continue
        if not valid(item.get("prePersonnelProbability")) or not valid(item.get("homeProbability")):
            continue
        effects=item.get("playerEffectDeltas")
        if not isinstance(effects,dict) or any(
            not isinstance(effects.get(k),(int,float)) or isinstance(effects.get(k),bool)
            or abs(effects[k])>1 for k in EFFECT_KEYS
        ):
            continue
        change=item["homeProbability"]-item["prePersonnelProbability"]
        if abs(change)<.00001 or abs(change-sum(effects[k] for k in EFFECT_KEYS))>.00025:
            continue
        # A source record must be prospective; timestamps from a subsequent
        # game or a later scrape are never substituted.
        observed=dt(item.get("personnelSourceObservedAt"))
        if not observed or observed>at or observed>=kick or at-observed>timedelta(days=7):
            continue
        candidates.append((at,item))
    return max(candidates,key=lambda x:x[0])[1] if candidates else None

def _metrics(rows):
    if not rows:
        return {"games":0,"withoutPlayerBrier":None,"withPlayerBrier":None,
                "brierGain":None,"improved":0,"worsened":0,"unchanged":0}
    n=len(rows)
    baseline=sum(x["withoutPlayerSquaredError"] for x in rows)/n
    adjusted=sum(x["withPlayerSquaredError"] for x in rows)/n
    return {"games":n,"withoutPlayerBrier":round(baseline,6),
            "withPlayerBrier":round(adjusted,6),
            "brierGain":round(baseline-adjusted,6),
            "improved":sum(x["brierGain"]>0.000001 for x in rows),
            "worsened":sum(x["brierGain"]<-.000001 for x in rows),
            "unchanged":sum(abs(x["brierGain"])<=.000001 for x in rows)}

def summarize(scored,groups,dt,valid):
    results=[]
    seen=set()
    for game in scored:
        gid=game.get("gameId")
        if gid in seen:
            raise ValueError("Duplicate completed game in player-effect evaluation: "+str(gid))
        seen.add(gid)
        kick=dt(game.get("kickoff"))
        outcome=game.get("outcomeHome")
        if kick is None or outcome not in (0,1):
            continue
        chosen=_selected(groups.get(gid,[]),kick,dt,valid)
        if not chosen:
            continue
        p=chosen["homeProbability"]
        neutral=chosen["prePersonnelProbability"]
        effects=chosen["playerEffectDeltas"]
        old=(neutral-outcome)**2
        new=(p-outcome)**2
        qb=sum(effects[k] for k in QB_KEYS)
        injury=sum(effects[k] for k in INJURY_KEYS)
        kind="both" if abs(qb)>.00001 and abs(injury)>.00001 else (
            "qb" if abs(qb)>.00001 else "other-injuries")
        results.append({"gameId":gid,"season":game.get("season"),"week":game.get("week"),
            "home":game.get("home"),"away":game.get("away"),
            "kickoff":game.get("kickoff"),"recordedAt":chosen["recordedAt"],
            "verificationLevel":chosen.get("verificationLevel","unavailable"),
            "type":kind,"outcomeHome":outcome,
            "withoutPlayerProbability":neutral,"withPlayerProbability":p,
            "qbHomeDelta":round(qb,5),"otherInjuryHomeDelta":round(injury,5),
            "totalHomeDelta":round(p-neutral,5),
            "withoutPlayerSquaredError":round(old,8),
            "withPlayerSquaredError":round(new,8),
            "brierGain":round(old-new,8)})
    results.sort(key=lambda x:(x["kickoff"],x["gameId"]),reverse=True)
    overall=_metrics(results)
    seasons={r["season"] for r in results if isinstance(r.get("season"),int)}
    # Per-signal summaries can share games when both effects were applied.
    qb=[r for r in results if abs(r["qbHomeDelta"])>.00001]
    injury=[r for r in results if abs(r["otherInjuryHomeDelta"])>.00001]
    return {"schemaVersion":1,"status":"prospective-paired-player-effect-audit",
        **overall,"verifiedSourceGames":sum(r["verificationLevel"]=="checked" for r in results),
        "reviewOrHoldGames":sum(r["verificationLevel"] in ("review","hold") for r in results),
        "evaluatedSeasons":len(seasons),
        "qbEffects":_metrics(qb),"otherInjuries":_metrics(injury),
        "readyForIndependentReview":len(results)>=100 and len(seasons)>=2,
        "calibratedOrApproved":False,
        "recentResults":results[:30],
        "note":"Research only. Each game is graded once using the latest genuinely timestamped, fresh, applied player adjustment BEFORE kickoff and its saved same-time non-player probability. Brier gain = without-player error minus adjusted error, so positive is better. Categories can overlap in combined games. Stale cached effects and old snapshots lacking a saved same-time counterfactual are excluded. Any 100-game/two-season threshold triggers independent review, never automatic approval, confidence or a betting signal."}
