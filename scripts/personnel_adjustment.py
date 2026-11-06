"""Provisional, auditable QB/injury-aware forecast.

This is deliberately NOT a statistically validated player-value model.
Only recent, dated ESPN *media observations* and a pregame depth-chart
change may move the provisional forecast. Official starter/inactive status
is NOT inferred. The original Elo forecast is retained separately and
the point values below are explicitly declared assumptions to test forward.
"""
from __future__ import annotations
from datetime import datetime, timezone, timedelta
import math

QB_OUT_POINTS=2.5
QB_DOUBTFUL_POINTS=1.5
QB_CHANGE_POINTS=1.5
KEY_OUT_POINTS=0.35
KEY_DOUBTFUL_POINTS=0.16
MAX_QB_POINTS=3.5
MAX_OTHER_POINTS=1.4
MAX_GAME_POINTS=5.0
LOG_ODDS_PER_POINT=0.11
MAX_REPORT_AGE_DAYS=7
QB_MAX_CHART_AGE_DAYS=14
MAX_FORECAST_HORIZON_DAYS=7
MIN_QB_DROPBACKS=80

OUT={"OUT","INJURED RESERVE","IR","OUT FOR SEASON","INACTIVE"}
DOUBTFUL={"DOUBTFUL","DOUBTFUL FOR GAME"}
USAGE_POS={"WR","RB","HB","FB","TE","T","LT","RT","G","LG","RG","C","OT","OL","DL","DE","DT","EDGE","LB","CB","S","SS","FS","DB"}

def as_utc(v):
    if isinstance(v,datetime):
        d=v
    else:
        try:d=datetime.fromisoformat(str(v).replace("Z","+00:00"))
        except (ValueError,TypeError):return None
    if d.tzinfo is None:return None
    return d.astimezone(timezone.utc)

def valid_report(item,now,kickoff):
    d=as_utc(item.get("reportDate"))
    return bool(d and d<=now and d<kickoff and timedelta(0)<=now-d<=timedelta(days=MAX_REPORT_AGE_DAYS))

def player_key(item):
    return str(item.get("name") or "").strip().casefold()

def _logit(x):
    p=max(.01,min(.99,float(x)))
    return math.log(p/(1-p))

def _sigmoid(x):
    if x>=0:return 1/(1+math.exp(-x))
    z=math.exp(x)
    return z/(1+z)

def qb_efficiency_preview(game,validation):
    """Experimental QB efficiency overlay from PREVIOUS completed seasons.

    The original strict validation gate remains OFF. This is a separate,
    clearly labelled provisional forecast with capped 0.20 log-odds effect.
    """
    p=game.get("homeProbability")
    x=game.get("qbResearch") or {}
    v=validation or {}
    result={"status":"unavailable","affectsPrediction":False,"homeProbability":p,
            "homeDelta":0.0,"marginDelta":0.0,"factors":[],
            "researchOnly":True,"validated":False,
            "trainedThroughSeason":v.get("trainedThroughSeason"),
            "historicalBrierGain":v.get("brierGain")}
    if not isinstance(p,(float,int)) or not 0<p<1 or not x.get("eligible"):return result
    try:year=int(game["season"]);train=int(v.get("trainedThroughSeason") or 9999)
    except (KeyError,ValueError,TypeError):return result
    if (train>=year or v.get("sampleSize",0)<500 or
        v.get("improvingSeasons",0)<2 or (v.get("brierGain") or 0)<.0003):
        return {**result,"status":"exploratory-gate-not-met"}
    features=x.get("features")
    names=("qb_epa_edge","qb_sack_edge","qb_change_watch")
    coeff=v.get("candidateCoefficients") or {}
    if not isinstance(features,(list,tuple)) or len(features)!=3:return result
    if not all(isinstance(z,(float,int)) and math.isfinite(z) for z in features):return result
    if not all(isinstance(coeff.get(k),(float,int)) and math.isfinite(coeff[k]) for k in names):return result
    z=max(-.2,min(.2,sum(coeff[k]*z for k,z in zip(names,features))))
    if abs(z)<.001:return {**result,"status":"negligible-historical-qb-effect"}
    estimated=round(_sigmoid(_logit(p)+z),5)
    margin=round(z/LOG_ODDS_PER_POINT,3)
    return {**result,"status":"historical-qb-efficiency-provisional",
            "affectsPrediction":True,"homeProbability":estimated,
            "homeDelta":round(estimated-p,5),"marginDelta":margin,
            "featureNames":names,"features":list(features),
            "coefficients":{k:coeff[k] for k in names},
            "factors":[{"team":str(game.get("home"))+" vs "+str(game.get("away")),
                        "side":"both","kind":"qb-efficiency",
                        "player":"Historical QB matchup",
                        "status":"Pregame EPA / sack / starter-change features",
                        "pointsAgainstTeam":round(-margin,3),
                        "evidence":"Earlier completed-season statistical QB calibration only",
                        "assumption":"Provisional research effect (not certified starter or prospectively validated)"}]}


def assess(game,now,exclude_qb=False):
    """Return an alternative probability, evidence trail and point assumptions.

    No new forecast is generated from a feed that did not actually refresh.
    Never processes already-started games. Unknown or questionable statuses
    are surfaced as uncertainty, NOT silently counted as confirmed OUT.
    """
    kickoff=as_utc(game.get("kickoff"))
    now=as_utc(now)
    original=game.get("homeProbability")
    base=game.get("baselineHomeProbability",original)
    empty={"status":"not-available","provisional":True,"validated":False,
           "affectsPrediction":False,"baseHomeProbability":base,
           "homeProbability":original,"homeDelta":0.0,"marginDelta":0.0,
           "factors":[],"warnings":[],"source":"ESPN media injury watch and dated nflverse depth charts",
           "method":"Assumed points mapped to log-odds; requires forward validation"}
    if now is None or kickoff is None or not now<kickoff or not isinstance(original,(int,float)) or not 0<original<1:
        return {**empty,"reason":"Fixture started or missing pregame probability; no retrospective edits"}
    if kickoff-now>timedelta(days=MAX_FORECAST_HORIZON_DAYS):
        return {**empty,"status":"future-week-monitor-only",
                "reason":"Future-week projected roster has insufficient certainty"}
    media=game.get("supplementalInjuryWatch") or {}
    if media.get("status")!="loaded":
        return {**empty,"status":"source-unavailable",
                "reason":"No fresh dated ESPN media observation; cannot apply assumed player impact"}
    qb=game.get("qbIntelligence") or {}
    factors=[];warnings=[];scores={"home":0.0,"away":0.0}
    observed={}
    for side in ("home","away"):
        team=game[side]
        qb_info=qb.get(side) or {}
        leader=qb_info.get("lastGameLeader") or {}
        leader_name=str(leader.get("name") or "").strip()
        projected_name=str(qb_info.get("qb") or "").strip() if qb_info.get("basis")=="depth_chart_projection" else ""
        # Drop stale depth charts. The per-team projection was determined using
        # a pre-kickoff snapshot, but we also require recent source material.
        chart=game.get("personnelDepthChart") or {}
        projected_date=as_utc((chart.get(side) or {}).get("asOf"))
        chart_fresh=bool(projected_date and projected_date<=now and now-projected_date<=timedelta(days=QB_MAX_CHART_AGE_DAYS))
        qb_switch=bool(chart_fresh and leader_name and projected_name and
                       leader_name.casefold()!=projected_name.casefold())
        observations=[item for item in media.get(side,[]) if
                      isinstance(item,dict) and valid_report(item,now,kickoff)]
        by_name={}
        for item in observations:
            key=player_key(item)
            if key and (key not in by_name or
              str(item.get("reportDate",""))>str(by_name[key].get("reportDate",""))):
                by_name[key]=item
        if not observations:
            warnings.append(team+": no fresh eligible media status; no availability assumptions")
        prior_qb_status=next((str(item.get("status") or "").upper().strip()
            for item in by_name.values() if str(item.get("position") or "").upper()=="QB"
            and leader_name and player_key(item)==leader_name.casefold()),None)
        qb_pts=0.0
        reason=""
        if prior_qb_status in OUT|DOUBTFUL:
            qb_pts=QB_OUT_POINTS if prior_qb_status in OUT else QB_DOUBTFUL_POINTS
            if qb_switch:qb_pts+=QB_CHANGE_POINTS
            reason="Recent dated ESPN QB absence report"+("; dated QB projection changed" if qb_switch else "")
        elif qb_switch:
            # A healthy starter returning from a backup can be an UPGRADE.
            prior=qb_info.get("previousQBsample") or {}
            new=qb_info.get("sample") or {}
            if (prior.get("dropbacks",0)>=MIN_QB_DROPBACKS and
                new.get("dropbacks",0)>=MIN_QB_DROPBACKS and
                isinstance(prior.get("epaPerDropback"),(int,float)) and
                isinstance(new.get("epaPerDropback"),(int,float)) and
                math.isfinite(prior["epaPerDropback"]) and
                math.isfinite(new["epaPerDropback"])):
                qb_pts=max(-2.5,min(2.5,10.0*(prior["epaPerDropback"]-new["epaPerDropback"])))
                reason="Dated QB projection; relative prior QB EPA with >=80 previous dropbacks each"
            else:
                warnings.append(team+": changed QB projection, but direction unverified — no automatic penalty")
        # The production pipeline uses the separate evidence-aware
        # replacement-value module for QB OUT/DOUBTFUL. Never add the old
        # fixed QB heuristic on top of it, even when the new feed is missing.
        if exclude_qb:qb_pts=0.0
        qb_pts=max(-MAX_QB_POINTS,min(MAX_QB_POINTS,qb_pts))
        if abs(qb_pts)>0.001:
            scores[side]+=qb_pts
            factors.append({"team":team,"side":side,"kind":"qb",
              "player":leader_name,"status":prior_qb_status or "Observed QB projection change",
              "projectedQB":projected_name or None,"pointsAgainstTeam":round(qb_pts,3),
              "evidence":reason,
              "assumption":"Provisional signed QB assessment; a negative value is an upgrade, not validated player value"})
        for item in by_name.values():
            status=str(item.get("status") or "").upper().strip()
            pos=str(item.get("position") or "").upper()
            if pos=="QB":
                # Projected starters for current game aren't official: no double QB count.
                if status=="QUESTIONABLE":warnings.append(team+": reported QB questionable: "+str(item.get("name")))
                continue
            if pos not in USAGE_POS or status not in OUT|DOUBTFUL:continue
            usage=item.get("recentUsage") or {}
            off=usage.get("offensePct")
            defense=usage.get("defensePct")
            try:heavy=max(float(x) for x in (off,defense) if x is not None)>=.70
            except (TypeError,ValueError):heavy=False
            if not heavy:continue
            points=KEY_OUT_POINTS if status in OUT else KEY_DOUBTFUL_POINTS
            current=sum(x["pointsAgainstTeam"] for x in factors if x["side"]==side and x["kind"]=="other")
            points=max(0,min(points,MAX_OTHER_POINTS-current))
            if points:
                scores[side]+=points
                factors.append({"team":team,"side":side,"kind":"other",
                  "player":str(item.get("name") or "Unknown"),"status":status,
                  "pointsAgainstTeam":round(points,3),
                  "evidence":"Dated ESPN media status and >=70% historical snap participation",
                  "assumption":"Provisional role-based availability adjustment, not measured replacement value"})
        for item in by_name.values():
            if str(item.get("status") or "").upper().strip()=="QUESTIONABLE" and str(item.get("position") or "").upper()!="QB":
                warnings.append(team+": "+str(item.get("name"))+" questionable — NOT included as OUT")
        observed[side]=len(by_name)
    # Positive margin delta means favourable for home: away has more estimated absence risk.
    margin=max(-MAX_GAME_POINTS,min(MAX_GAME_POINTS,scores["away"]-scores["home"]))
    changed=bool(abs(margin)>1e-8)
    result=round(_sigmoid(_logit(original)+LOG_ODDS_PER_POINT*margin),5) if changed else original
    return {**empty,"status":"provisional-assessment" if changed else "no-qualifying-evidence",
            "affectsPrediction":changed,"homeProbability":result,
            "homeDelta":round(result-original,5),"marginDelta":round(margin,3),
            "homeMissingPoints":round(scores["home"],3),
            "awayMissingPoints":round(scores["away"],3),
            "factors":factors,"warnings":warnings[:12],
            "sourceObservedAt":media.get("retrievedAt"),
            "teamObservations":observed,
            "reason":("Fresh media reports and projected QB changes triggered declared assumptions" if changed
                      else "No qualifying dated QB-out/change or high-usage absences observed"),
            "uncertainty":"Only an experimental scenario, not a validated win probability. Depth charts are projected; ESPN media statuses are not certified NFL gameday inactives."}
