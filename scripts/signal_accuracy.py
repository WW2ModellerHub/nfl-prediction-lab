"""Season-forward matchup signal ablation and probability reliability audit.

Research-only. Historical games are reconstructed from pregame data, and
evaluation seasons are model-selection evidence rather than untouched blind data.
The accuracy lab must never alter published forecast percentages or gate status.
"""
from __future__ import annotations
import math
import random
from collections import defaultdict
from statistics import mean

from situational_validation import _solve

FEATURES=("pass_matchup", "rush_matchup", "hit_sack_matchup", "explosive_matchup")
CANDIDATES=(
    ("passing", "Passing efficiency", (0,)),
    ("rushing", "Rushing efficiency", (1,)),
    ("pressure", "QB-hit/sack proxy", (2,)),
    ("explosives", "Explosive passes", (3,)),
    ("combined", "All four together", (0,1,2,3)),
)
MIN_TRAIN=350
MIN_SEASON_TEST=80
PENALTY=150.0
BLOCK_DRAWS=400


def _clip(p):
    return max(0.005,min(0.995,float(p)))


def _logit(p):
    p=_clip(p)
    return math.log(p/(1-p))


def _logistic(x):
    if x>=0:
        z=math.exp(-min(700,x))
        return 1/(1+z)
    z=math.exp(max(-700,x))
    return z/(1+z)


def _clean(rows,current_season):
    out=[]
    for r in rows:
        try:
            season=int(r["season"])
            p=float(r["p"])
            y=r["y"]
            if y not in (0,1):
                continue
            features=tuple(float(x) for x in r["features"])
            if season>=current_season or y not in (0,1) or len(features)!=4:
                continue
            if not (math.isfinite(p) and 0<p<1 and all(math.isfinite(x) for x in features)):
                continue
            out.append({"season":season,"week":r.get("week"),
                        "p":p,"y":y,"features":features})
        except (KeyError, TypeError, ValueError, OverflowError):
            continue
    return sorted(out,key=lambda x:(x["season"],str(x["week"])))


def _fit(rows,columns,penalty=PENALTY):
    if len(rows)<MIN_TRAIN:
        return [0.0]*len(columns)
    coefs=[0.0]*len(columns)
    if not any(any(r["features"][k] for k in columns) for r in rows):
        return coefs
    size=len(columns)
    for _ in range(18):
        grad=[-penalty*c for c in coefs]
        h=[[float(penalty) if i==j else 0.0 for j in range(size)]
           for i in range(size)]
        for r in rows:
            x=[r["features"][k] for k in columns]
            if not any(x):
                continue
            pred=_logistic(_logit(r["p"])+sum(c*a for c,a in zip(coefs,x)))
            diff=r["y"]-pred
            curv=pred*(1-pred)
            for j in range(size):
                grad[j]+=x[j]*diff
                for k in range(size):
                    h[j][k]+=curv*x[j]*x[k]
        step=_solve(h,grad)
        coefs=[max(-.65,min(.65,c+s)) for c,s in zip(coefs,step)]
        if max(abs(s) for s in step)<1e-7:
            break
    return coefs


def _predict(r,columns,coefs):
    return _clip(_logistic(_logit(r["p"])+sum(c*r["features"][i] for i,c in zip(columns,coefs))))


def _metrics(games,field):
    if not games:
        return {"games":0,"brier":None,"logLoss":None,"accuracy":None}
    n=len(games)
    return {"games":n,
            "brier":round(mean((g[field]-g["y"])**2 for g in games),6),
            "logLoss":round(mean(-(g["y"]*math.log(_clip(g[field]))+
                                 (1-g["y"])*math.log(1-_clip(g[field]))) for g in games),6),
            "accuracy":round(mean(int((g[field]>=.5)==bool(g["y"])) for g in games),4)}


def _weekly_ci(games,field):
    """Paired season-week bootstrap; exploratory interval, not a selection p-value."""
    if len(games)<80:
        return None
    blocks=defaultdict(list)
    for i,g in enumerate(games):
        # Missing week must not invent a common block shared across all games.
        key=(g["season"],g["week"] if g["week"] is not None else "missing-"+str(i))
        blocks[key].append((g["p"]-g["y"])**2-(g[field]-g["y"])**2)
    keys=list(blocks)
    if len(keys)<10:
        return None
    rr=random.Random(1901)
    samples=[]
    for _ in range(BLOCK_DRAWS):
        draw=[blocks[keys[rr.randrange(len(keys))]] for _ in keys]
        total=sum(sum(b) for b in draw)
        n=sum(len(b) for b in draw)
        samples.append(total/n)
    samples.sort()
    return [round(samples[int(.025*(BLOCK_DRAWS-1))],6),
            round(samples[int(.975*(BLOCK_DRAWS-1))],6)]


def _calibration(games,field):
    result=[]
    for i in range(5):
        group=[g for g in games if min(4,int(g[field]*5))==i]
        result.append({"band":f"{i*20}–{(i+1)*20}%",
                       "games":len(group),
                       "meanForecast":round(mean(g[field] for g in group),4) if group else None,
                       "actualHomeWinRate":round(mean(g["y"] for g in group),4) if group else None})
    return result


def _locked_period_check(evaluated):
    """Simulated chronological selection, never production promotion.

    Select one feature using <=2023 walk-forward evaluations, then inspect the
    same pregame models on >=2024 data without re-selecting the feature.
    Candidate coefficients ARE re-fit at each successive season, from earlier
    games only. The study was not preregistered and is NOT blind.
    """
    selection=[r for r in evaluated if r["season"]<=2023]
    reserved=[r for r in evaluated if r["season"]>=2024]
    old_years=sorted({r["season"] for r in selection})
    later_years=sorted({r["season"] for r in reserved})
    report={"status":"insufficient chronological coverage",
            "selectionThroughSeason":2023,"holdoutFromSeason":2024,
            "featureChoiceFrozen":True,"coefficientsReestimatedAnnually":True,
            "researchOnly":True,"productionWeight":0,
            "selectionGames":len(selection),"selectionSeasons":old_years,
            "holdoutGames":len(reserved),"holdoutSeasons":later_years,
            "selectedKey":None,"selectedName":None,
            "selectionBrierGain":None,"holdout":None,
            "note":"Retrospective date-split check; 2024+ outcomes were already considered in earlier project research, so not an untouched blind experiment."}
    if len(selection)<150 or len(old_years)<2 or len(reserved)<100:
        return report
    gains={key:mean((r["p"]-r["y"])**2-(r[key]-r["y"])**2 for r in selection)
           for key,_,_ in CANDIDATES}
    best=max(gains,key=gains.get)
    selected=best if gains[best]>0 else "p"
    report.update(status="historical simulated feature lock completed",
                  selectedKey=selected,
                  selectedName=next((name for key,name,_ in CANDIDATES if key==selected),
                                    "Baseline (no additional signals)"),
                  selectionBrierGain=round(gains[best] if selected!="p" else 0,6),
                  selectionCandidateGains={key:round(x,6) for key,x in gains.items()})
    base=_metrics(reserved,"p")
    candidate=_metrics(reserved,selected)
    diff=mean((r["p"]-r["y"])**2-(r[selected]-r["y"])**2 for r in reserved)
    per_year=[]
    for year in later_years:
        cohort=[r for r in reserved if r["season"]==year]
        bp=_metrics(cohort,"p");cp=_metrics(cohort,selected)
        per_year.append({"season":year,"games":len(cohort),
                         "baselineBrier":bp["brier"],"selectedBrier":cp["brier"],
                         "brierGain":round(bp["brier"]-cp["brier"],6)})
    report["holdout"]={"games":len(reserved),"baseline":base,"selected":candidate,
                       "brierGain":round(diff,6),"brierGain95CI":_weekly_ci(reserved,selected),
                       "seasons":per_year,
                       "improvingSeasons":sum(s["brierGain"]>0 for s in per_year)}
    return report


def evaluate(rows,current_season):
    """Always compare candidates on exactly the same paired, pregame cohort.

    For an evaluation year s, every coefficient is fit only with seasons <s.
    Current-season outcomes never enter training or evaluation.
    """
    clean=_clean(rows,current_season)
    years=sorted(set(r["season"] for r in clean))
    evaluated=[]
    for year in years:
        train=[r for r in clean if r["season"]<year]
        test=[r for r in clean if r["season"]==year]
        if len(train)<MIN_TRAIN or len(test)<MIN_SEASON_TEST:
            continue
        coefficients={key:_fit(train,columns) for key,_,columns in CANDIDATES}
        for r in test:
            one=dict(r)
            for key,_,columns in CANDIDATES:
                one[key]=_predict(r,columns,coefficients[key])
            evaluated.append(one)
    if not evaluated:
        return {"status":"insufficient historical coverage","researchOnly":True,
                "productionWeight":0,"forecastChanged":False,
                "inputGames":len(clean),"evaluatedGames":0,"evaluatedSeasons":[],
                "baseline":None,"candidates":[],"calibration":{},
                "lockedHoldout":_locked_period_check([]),
                "note":"Needs ≥350 earlier-season eligible games and ≥80 eligible games in a later completed evaluation season. Incomplete play-by-play is never imputed."}
    seasons=sorted({r["season"] for r in evaluated})
    base=_metrics(evaluated,"p")
    candidates=[]
    for key,name,columns in CANDIDATES:
        metric=_metrics(evaluated,key)
        per_year=[]
        for year in seasons:
            games=[r for r in evaluated if r["season"]==year]
            bm=_metrics(games,"p")
            cm=_metrics(games,key)
            per_year.append({"season":year,"games":len(games),"baselineBrier":bm["brier"],
                             "candidateBrier":cm["brier"],
                             "brierGain":round(bm["brier"]-cm["brier"],6)})
        difference=mean((r["p"]-r["y"])**2-(r[key]-r["y"])**2 for r in evaluated)
        ci=_weekly_ci(evaluated,key)
        # This is an invitation to prospectively test, never an activation rule.
        explore=(len(seasons)>=2 and len(evaluated)>=400 and
                 sum(y["brierGain"]>0 for y in per_year)>=2 and
                 difference>=.001 and ci is not None and ci[0]>0)
        candidates.append({"key":key,"name":name,"features":[FEATURES[i] for i in columns],
                           "games":metric["games"],"brier":metric["brier"],
                           "logLoss":metric["logLoss"],"accuracy":metric["accuracy"],
                           "brierGain":round(difference,6),
                           "brierGain95CI":ci,"seasons":per_year,
                           "warrantsForwardResearch":explore,"affectsForecast":False})
    return {"status":"historical season-forward research","researchOnly":True,
            "productionWeight":0,"forecastChanged":False,
            "trainedThroughSeason":max((s for s in years if s<current_season),default=None),
            "inputGames":len(clean),"evaluatedGames":len(evaluated),
            "evaluatedSeasons":seasons,"baseline":base,"candidates":candidates,
            "lockedHoldout":_locked_period_check(evaluated),
            "calibration":{"baseline":_calibration(evaluated,"p"),
                           "combined":_calibration(evaluated,"combined")},
            "notes":["Historical season-forward evaluation uses only preceding seasons to train each held-out season.",
                     "The same games are used for every candidate and baseline, making paired Brier differences comparable.",
                     "The 95% week-block bootstrap intervals are exploratory, unadjusted for five comparisons or model selection.",
                     "The pre-2024 feature-selection check is simulated retrospectively, NOT genuine untouched prospective evidence.",
                     "Historical testing, including the newest seasons, is not untouched blind prospective validation.",
                     "A qualified candidate is research-only; live forecasts, markets and player availability weights are unchanged.",
                     "Coverage requires nflverse play-by-play from completed earlier games; schedules-only refreshes cannot recompute this audit."]}


if __name__=="__main__":
    print("Call evaluate(tactical_rows,current_season) from the NFL model pipeline")
