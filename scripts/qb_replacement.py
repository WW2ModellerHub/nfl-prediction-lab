"""2026 QB replacement-discontinuity estimates, prospective and auditable.

A starting-QB injury may have a larger impact than a generic 2.5-point
penalty. This module estimates a pregame *conditional* replacement impact
using the outgoing QB's prior completed plays, the dated projected backup,
and an as-of population of earlier actual first starts.

It NEVER infers the current game's actual QB from postgame scores or
nflverse game starter fields. Published impact requires a recent media
OUT/DOUBTFUL designation for the *outgoing* QB and a recent, different
depth-chart projection. Projection-only scenarios are research, not picks.

The margin-to-win and EPA-to-points mappings remain declared assumptions
until independent prospectively logged games establish calibration.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
import math

MAX_HORIZON_DAYS=7
MAX_CHART_DAYS=14
MAX_PREVIOUS_STARTER_DAYS=35
MAX_REPORT_AGE_DAYS=7
MIN_PRIOR_STARTER_DROPBACKS=80
MIN_NEW_STARTER_DROPBACKS=80
MIN_FIRST_START_OBSERVATIONS=20
MAX_POINTS=13.0
MIN_DROPBACK_VOLUME=24.
MAX_DROPBACK_VOLUME=42.
ODDS_PER_POINT=.11
OUT={"OUT","INJURED RESERVE","IR","INACTIVE","OUT FOR SEASON"}
DOUBTFUL={"DOUBTFUL"}
OTHER_UNCERTAIN={"QUESTIONABLE","GAME TIME DECISION"}

def _time(value):
    try:
        d=value if isinstance(value,datetime) else datetime.fromisoformat(str(value).replace("Z","+00:00"))
        return d.astimezone(timezone.utc) if d.tzinfo else None
    except (ValueError,TypeError,OverflowError):return None

def _finite(value):
    return isinstance(value,(int,float)) and not isinstance(value,bool) and math.isfinite(value)

def _name(value):
    return str(value or "").strip().casefold().replace(".","").replace("'","")

def _sigmoid(x):
    if x>=0:return 1/(1+math.exp(-x))
    z=math.exp(x)
    return z/(1+z)

def _logit(p):
    p=max(.005,min(.995,p))
    return math.log(p/(1-p))

def _prob(p,points):
    return round(_sigmoid(_logit(p)+ODDS_PER_POINT*points),5)

def _effective_epa(sample,empirical_prior):
    """Shrink small NFL samples; never treat zero observed dropbacks as league average."""
    if not sample or not _finite(sample.get("epaPerDropback")):return None
    n=sample.get("dropbacks",0)
    if not isinstance(n,(int,float)) or n<MIN_NEW_STARTER_DROPBACKS:return None
    observed=max(-.55,min(.55,float(sample["epaPerDropback"])))
    w=n/(n+150.)
    return round(w*observed+(1-w)*empirical_prior,4)

def _report_status(items,former,now,kickoff):
    status=None; latest=None
    for r in items:
        if (not isinstance(r,dict) or _name(r.get("name"))!=_name(former) or
            str(r.get("position") or "").upper()!="QB"):
            continue
        at=_time(r.get("reportDate"))
        if not at or at>now or at>=kickoff or now-at>timedelta(days=MAX_REPORT_AGE_DAYS):continue
        if latest is None or at>latest:
            latest=at
            status=str(r.get("status") or "").upper().strip()
    return status,latest

def evaluate(game,now,include_projection_scenario=True):
    """Return evidence, risk ranges, and a conditional estimate for each side.

    The actual probability only changes for a fresh, specifically matched
    previous-starter OUT/DOUBTFUL media report. Other projected QB changes
    can be described, but never assumed to be an official scratch.
    """
    now=_time(now)
    kick=_time(game.get("kickoff"))
    p=game.get("homeProbability")
    empty={"status":"unavailable","eligible":False,"affectsPrediction":False,
           "homeProbability":p,"homeDelta":0.,"marginDelta":0.,
           "factors":[],"scenarios":[],"warnings":[],
           "researchOnly":True,"validated":False,
           "model":"QB replacement EPA model v1 · research",
           "source":"Dated nflverse depth chart, prior completed quarterback EPA and dated ESPN media observation",
           "pointMapping":{"maxPoints":MAX_POINTS,"oddsPerPoint":ODDS_PER_POINT,
                           "method":"Projected dropbacks × shrunken prior EPA gap; unvalidated",
                           "unknownReplacement":"Historical first-start EPA before this kickoff"}}
    if not now or not kick or not _finite(p) or p<=0 or p>=1 or now>=kick:
        return {**empty,"reason":"Kickoff began or forecast timestamp invalid"}
    if kick-now>timedelta(days=MAX_HORIZON_DAYS):
        return {**empty,"status":"future-week-monitor",
                "reason":"Long-horizon depth projections are not reliable enough for replacement scenarios"}
    qb=game.get("qbIntelligence") or {}
    media=game.get("supplementalInjuryWatch") or {}
    charts=game.get("personnelDepthChart") or {}
    first=qb.get("firstStartPrior") or {}
    first_epa=first.get("epaPerDropback")
    if (first.get("status")!="observed" or not _finite(first_epa) or
        first.get("starts",0)<MIN_FIRST_START_OBSERVATIONS):
        return {**empty,"status":"insufficient-empirical-first-starts",
                "reason":"Need at least 20 already completed first starts to estimate a rookie/unknown QB prior",
                "observations":first.get("starts",0)}
    scenarios=[];factors=[];warnings=[];team_pts={"home":0.,"away":0.}
    for side in ("home","away"):
        team=game.get(side)
        q=qb.get(side) or {}
        old=q.get("lastGameLeader") or {}
        prev_name=old.get("name")
        projected=q.get("qb") if q.get("basis")=="depth_chart_projection" else None
        chart_at=_time((charts.get(side) or {}).get("asOf"))
        old_at=_time(old.get("date"))
        if not (prev_name and projected and _name(prev_name)!=_name(projected) and
            chart_at and timedelta(0)<=now-chart_at<=timedelta(days=MAX_CHART_DAYS) and
            old_at and timedelta(0)<=now-old_at<=timedelta(days=MAX_PREVIOUS_STARTER_DAYS) and
            old.get("season")==game.get("season")):
            continue
        before=q.get("previousQBsample") or {}
        previous=_effective_epa(before,0.0)
        if previous is None:
            warnings.append(str(team)+": outgoing QB has fewer than 80 previously recorded dropbacks; direction unknown")
            continue
        after=q.get("sample") or {}
        replacement=_effective_epa(after,0.0)
        is_first_start=replacement is None
        if is_first_start:replacement=float(first_epa)
        dbs=float(before.get("dropbacks",0))/max(1,float(before.get("games",1)))
        dbs=max(MIN_DROPBACK_VOLUME,min(MAX_DROPBACK_VOLUME,dbs))
        gap=max(-.45,min(.45,previous-replacement))
        points=max(-MAX_POINTS,min(MAX_POINTS,gap*dbs))
        if abs(points)<.05:continue
        if media.get("status")=="loaded":
            status,reported_at=_report_status(media.get(side) or [],prev_name,now,kick)
        else:
            status,reported_at=None,None
        used=status in OUT or status in DOUBTFUL
        certainty=1. if status in OUT else .5 if status in DOUBTFUL else 0.
        if status in OTHER_UNCERTAIN:
            warnings.append(str(team)+": QB questionable; no replacement adjustment without out/doubtful designation")
        if not used:
            warnings.append(str(team)+": projected QB change lacks a matching fresh outgoing-QB OUT/DOUBTFUL report")
        change=round(points*certainty,3)
        scenario={"team":team,"side":side,"outgoingQB":prev_name,
                  "replacementQB":projected,"reportStatus":status or "unverified projected switch",
                  "reportAsOf":reported_at.isoformat() if reported_at else None,
                  "projectedDepthAsOf":chart_at.isoformat(),
                  "oldQBdropbacks":before.get("dropbacks"),
                  "replacementQBdropbacks":after.get("dropbacks",0),
                  "firstStartPriorEPA":first_epa if is_first_start else None,
                  "firstStartObservations":first["starts"] if is_first_start else None,
                  "outgoingExpectedEPA":previous,"replacementExpectedEPA":replacement,
                  "epaGap":round(gap,4),"projectedDropbacks":round(dbs,1),
                  "fullAbsencePoints":round(points,3),
                  "appliedPoints":change,
                  "mode":"reported-absence" if used else "scenario-only",
                  "uncertainty":"Projected starter is unconfirmed; each QB EPA estimate is noisy",
                  "evidence":"Previous game starter and dated projected QB; replacement distribution contains only completed earlier games"}
        scenarios.append(scenario)
        if used:
            team_pts[side]+=change
            factors.append({"team":team,"side":side,"kind":"qb-replacement",
                "player":prev_name,"replacement":projected,
                "status":status,"pointsAgainstTeam":change,
                "evidence":str(before.get("dropbacks"))+" previous QB dropbacks; "+
                    (str(first['starts'])+" historical first starts" if is_first_start else
                     str(after.get("dropbacks"))+" previous replacement QB dropbacks"),
                "assumption":"Empirical pregame EPA gap × expected dropbacks; log-odds conversion unvalidated"})
    if not scenarios:
        return {**empty,"status":"no-documented-replacement",
                "reason":"No eligible previous established QB versus fresh different projected replacement",
                "firstStartPopulation":first}
    points=max(-MAX_POINTS,min(MAX_POINTS,team_pts["away"]-team_pts["home"]))
    applied=any(x.get("mode")=="reported-absence" for x in scenarios) and abs(points)>.001
    conditional=[]
    for x in scenarios:
        # Conditional 100% absence applies to a single side, independent of
        # all other injury news; it is NOT the default live probability.
        signed=x["fullAbsencePoints"]*(1 if x["side"]=="away" else -1)
        est=_prob(float(p),signed)
        range_pts=max(3.0,min(7.0,x["projectedDropbacks"]*.12))
        conditional.append({**x,"conditionalHomeProbability":est,
            "illustrativeLow":_prob(float(p),signed-range_pts),
            "illustrativeHigh":_prob(float(p),signed+range_pts),
            "intervalType":"sensitivity (not calibrated 95% confidence interval)"})
    updated=_prob(float(p),points) if applied else p
    return {**empty,"status":"reported-absence-provisional" if applied else "projection-scenarios-only",
            "eligible":True,"affectsPrediction":applied,
            "homeProbability":updated,"homeDelta":round(updated-p,5),
            "marginDelta":round(points,3) if applied else 0.,
            "scenarios":conditional,"factors":factors,
            "warnings":warnings[:12],
            "firstStartPopulation":first,
            "reason":"Empirical QB replacement difference applied only to a fresh outgoing-starter absence report" if applied else
                     "Only depth-chart projection; scenario shown without moving the published forecast",
            "sourceObservedAt":media.get("retrievedAt") if media.get("status")=="loaded" else None}


def historical_screen(rows,current_season):
    """Research-only pregame projected-change evaluation on earlier seasons.

    Actual historical starter is never used in the pregame feature snapshot.
    An observed projected switch is NOT a historically confirmed absence.
    """
    cohort=[r for r in rows if r.get('season',current_season)<current_season
            and r.get('y') in (0,1) and _finite(r.get('baseline'))
            and _finite(r.get('conditional')) and r.get('eligible')]
    cohort.sort(key=lambda x:(x['season'],x.get('week',0)))
    by_year={}
    for r in cohort:by_year.setdefault(r['season'],[]).append(r)
    def brier(items,key):
        return round(sum((r[key]-r['y'])**2 for r in items)/len(items),6) if items else None
    seasons=[{'season':y,'games':len(a),'baselineBrier':brier(a,'baseline'),
              'projectedScenarioBrier':brier(a,'conditional'),
              'brierGain':round(brier(a,'baseline')-brier(a,'conditional'),6)}
             for y,a in sorted(by_year.items())]
    baseline=brier(cohort,'baseline')
    candidate=brier(cohort,'conditional')
    return {'status':'research-only; independent QB injury validation unavailable',
            'researchOnly':True,'productionApproved':False,
            'eligibleProjectedChangeGames':len(cohort),
            'baselineBrier':baseline,'conditionalScenarioBrier':candidate,
            'brierGain':round(baseline-candidate,6) if cohort else None,
            'seasons':seasons,'notes':[
                'Historical timestamped depth charts are only sourced from 2025 onward.',
                'Pregame projected QB change is not a verified starter injury or actual replacement.',
                'Historical projection-change screen uses pregame evidence only, never the current-game actual starter.',
                'Current-season results do not enter this historical comparison.',
                'Projected dropbacks × shrunken prior EPA and log-odds mapping are unvalidated assumptions.']}
