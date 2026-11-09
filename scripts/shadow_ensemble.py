"""Joint NFL pregame challenger with reconciled feature attribution.

Research only until prospective results independently corroborate historical
selection. All features are as-of kickoff; only earlier completed seasons train
each historical prediction. Team/injury/venue market data are NOT imputed as
"healthy"/"no wind" when no timestamped historical source exists.

XGBoost TreeSHAP effects are statistical allocation of the candidate model's
prediction, not causal effects. Interactions are shared across their features.
"""
from __future__ import annotations
from statistics import mean
import math

from situational_validation import feature_vector

VERSION="joint-xgb-v2-2026-11-09"
BASE_FEATURES=('elo_gap','form_gap','defense_gap','home_field','rest_gap',
 'qb_epa_edge','qb_sack_edge','qb_available',
 'pass_matchup','rush_matchup','hit_sack_matchup','explosive_matchup',
 'tactical_available')
SITUATIONAL=('empty_tank','thursday_road_ot','blowout_bounce',
 'nuclear_bounce','rest_edge','repeat_road')
EXTRA=('qb_change_watch','reported_absence_edge','injury_archive_available')
FEATURES=BASE_FEATURES+SITUATIONAL+EXTRA
GROUPS=(
 ('team','Team strength & scoring',('elo_gap','form_gap','defense_gap','home_field')),
 ('rest','Rest, travel & overtime',('rest_gap',)+SITUATIONAL),
 ('qb','Quarterback efficiency',('qb_epa_edge','qb_sack_edge','qb_available','qb_change_watch')),
 ('tactical','Passing, rushing & pressure',
    ('pass_matchup','rush_matchup','hit_sack_matchup','explosive_matchup','tactical_available')),
 ('injury','Reported absences',('reported_absence_edge','injury_archive_available')),
)
# Weather needs an archived, *pre-kickoff* venue forecast, currently unavailable.
UNTRAINED=('Weather & venue conditions',)

def _safe(x,limit=3.0):
    if isinstance(x,bool):return 0.0
    try:
        v=float(x)
        return max(-limit,min(limit,v)) if math.isfinite(v) else 0.0
    except (TypeError,ValueError,OverflowError):
        return 0.0

def vector(game,p):
    s=p.get('situation') or {}
    h=(s.get('home') or {}).get('fullRestDays')
    a=(s.get('away') or {}).get('fullRestDays')
    q=p.get('qb_research') or {}
    qb=q.get('features') if q.get('eligible') else None
    t=p.get('tactical') or {}
    tac=t.get('features') if t.get('status')=='ready' else None
    player=p.get('player_impact') or {}
    # An undated injury snapshot is not evidence of no injuries.
    injury=player.get('features') if player.get('eligible') and player.get('injuryArchiveLoaded') else None
    signals=feature_vector(s)
    vals=[
        _safe((p.get('elo_home',1500)-p.get('elo_away',1500))/400),
        _safe((p.get('home_form',22)-p.get('away_form',22))/16),
        _safe((p.get('away_allowed',22)-p.get('home_allowed',22))/16),
        0 if game.get('neutral') else 1,
        _safe((h-a)/7,10/7) if isinstance(h,(float,int)) and isinstance(a,(float,int)) else 0,
        _safe(qb[0],1) if qb else 0,
        _safe(qb[1],1) if qb else 0,
        1 if qb else 0,
        *([_safe(z) for z in tac[:4]] if tac and len(tac)>=4 else [0]*4),
        1 if tac and len(tac)>=4 else 0,
        *[int(z) for z in signals],
        int(qb[2]) if qb and len(qb)>=3 else 0,
        _safe(injury[3],4) if injury and len(injury)>=4 else 0,
        1 if injury and len(injury)>=4 else 0,
    ]
    if len(vals)!=len(FEATURES):
        raise ValueError('Joint challenger schema mismatch')
    return vals

def _logit(x):
    p=max(.005,min(.995,float(x)))
    return math.log(p/(1-p))

def _sigmoid(z):
    if z>=0:
        return 1/(1+math.exp(-min(z,100)))
    v=math.exp(max(z,-100))
    return v/(1+v)

def _fit(rows):
    import numpy as np
    from xgboost import XGBClassifier
    X=np.array([r['features'] for r in rows],dtype=np.float32)
    y=np.array([r['y'] for r in rows],dtype=np.int8)
    offset=np.array([_logit(r['p']) for r in rows],dtype=np.float32)
    model=XGBClassifier(objective='binary:logistic',n_estimators=85,
        max_depth=2,learning_rate=.025,subsample=.85,colsample_bytree=.85,
        min_child_weight=15,reg_alpha=2,reg_lambda=40,
        n_jobs=2,random_state=47,tree_method='hist',eval_metric='logloss')
    model.fit(X,y,base_margin=offset)
    return model

def _predict(model,rows):
    if not rows:return []
    import numpy as np
    from xgboost import DMatrix
    X=np.array([r['features'] for r in rows],dtype=np.float32)
    offset=np.array([_logit(r['p']) for r in rows],dtype=np.float32)
    dm=DMatrix(X,base_margin=offset,feature_names=list(FEATURES))
    booster=model.get_booster()
    return [float(v) for v in booster.predict(dm)]

def _explain(model,rows):
    """TreeSHAP groups in raw log-odds; reconcile EXACTLY to the forecast.

    The offset and booster bias belong to "model calibration"; per-feature
    contributions are allocated by TreeSHAP, including shared interactions.
    """
    if not rows:return []
    import numpy as np
    from xgboost import DMatrix
    matrix=np.array([r['features'] for r in rows],dtype=np.float32)
    bases=np.array([_logit(r['p']) for r in rows],dtype=np.float32)
    d=DMatrix(matrix,base_margin=bases,feature_names=list(FEATURES))
    booster=model.get_booster()
    margins=booster.predict(d,output_margin=True)
    shap=booster.predict(d,pred_contribs=True)
    if shap.shape!=(len(rows),len(FEATURES)+1):
        raise ValueError('TreeSHAP dimensional mismatch')
    predictions=[]
    for row,features,base,contrib,margin in zip(rows,matrix,bases,shap,margins):
        if not np.isfinite(contrib).all() or not math.isfinite(float(margin)):
            raise ValueError('Non-finite joint prediction')
        if abs(float(contrib.sum())-float(margin))>.0005:
            raise ValueError('TreeSHAP does not reconcile to XGBoost margin')
        p=float(row['p'])
        cursor=float(base)
        pieces=[{'key':'calibration','label':'Model calibration',
                 'logOddsContribution':float(contrib[-1])-cursor,'observed':True}]
        groups=[]
        for key,label,fields in GROUPS:
            score=sum(float(contrib[FEATURES.index(f)]) for f in fields)
            available=(bool(features[FEATURES.index('qb_available')]) if key=='qb' else
                       bool(features[FEATURES.index('tactical_available')]) if key=='tactical' else
                       bool(features[FEATURES.index('injury_archive_available')]) if key=='injury' else True)
            groups.append({'key':key,'label':label,'logOddsContribution':score,
                           'observed':available})
        pieces+=groups
        combined=sum(part['logOddsContribution'] for part in pieces)
        residual=float(margin)-float(base)-combined
        if abs(residual)>.0005:raise ValueError('Attribution missing an input feature')
        pieces[0]['logOddsContribution']+=residual
        trail=[]
        for piece in pieces:
            before=_sigmoid(cursor)
            cursor+=piece['logOddsContribution']
            after=_sigmoid(cursor)
            trail.append({'key':piece['key'],'label':piece['label'],
                 'deltaHomePP':round((after-before)*100,4),
                 'afterHomeProbability':round(after,7),
                 'observed':piece['observed']})
        final=_sigmoid(float(margin))
        if abs(cursor-float(margin))>.0005 or abs(final-_sigmoid(cursor))>1e-6:
            raise ValueError('Joint prediction does not reconcile')
        predictions.append({
            'homeProbability':round(final,6),
            'baselineHomeProbability':round(p,6),
            'impactPP':round((final-p)*100,3),
            'reconciles':True,'layers':trail,
            'source':'TreeSHAP log-odds attribution; ordered percentage-point display',
            'missingEvidence':[
                'Timestamped historical injury archive' if not features[FEATURES.index('injury_archive_available')] else None,
                'As-of projected QB with prior statistics' if not features[FEATURES.index('qb_available')] else None,
                'Historical play-by-play tactical observations' if not features[FEATURES.index('tactical_available')] else None,
                'Archived pregame weather (no trained coefficient)',
            ]})
        predictions[-1]['missingEvidence']=[v for v in predictions[-1]['missingEvidence'] if v]
    return predictions

def run(history,upcoming,current_season):
    """Historical screen, then current-season shadow prediction.

    Selection seasons are *not* independent validation. Versioned future
    forecasts must be recorded before kickoff and graded separately before
    anyone promotes this model into production.
    """
    result={'status':'unavailable','version':VERSION,'researchOnly':True,'productionWeight':0,
        'source':'XGBoost (Apache-2.0), as-of nflverse pregame data',
        'features':list(FEATURES),'factorGroups':[{'key':k,'label':name} for k,name,_ in GROUPS],
        'unsupportedFactors':list(UNTRAINED),'seasons':[],
        'note':'Historical walk-forward evaluation is model selection, not an untouched prospective proof. TreeSHAP assigns associations, not causal effects.'}
    try:
        import xgboost
    except ImportError:
        result['reason']='Optional xgboost package not installed'
        return result,{}
    rows=[r for r in history if r.get('y') in (0,1) and
          r.get('season',current_season)<current_season and
          len(r.get('features',[]))==len(FEATURES) and
          0<float(r.get('p',0))<1]
    years=sorted(set(r['season'] for r in rows if r['season']>=2024))
    try:
        seasons=[]
        for year in years:
            train=[r for r in rows if r['season']<year]
            test=[r for r in rows if r['season']==year]
            if len(train)<900 or len(test)<180:continue
            forecasts=_predict(_fit(train),test)
            base=mean((r['p']-r['y'])**2 for r in test)
            candidate=mean((f-r['y'])**2 for f,r in zip(forecasts,test))
            seasons.append({'season':year,'games':len(test),
                'baselineBrier':round(base,6),
                'challengerBrier':round(candidate,6),
                'brierGain':round(base-candidate,6),
                'baselineAccuracy':round(mean((r['p']>=.5)==bool(r['y']) for r in test),4),
                'challengerAccuracy':round(mean((f>=.5)==bool(r['y']) for f,r in zip(forecasts,test)),4)})
        n=sum(r['games'] for r in seasons)
        result['seasons']=seasons
        result['evaluationGames']=n
        result['improvingSeasons']=sum(r['brierGain']>0 for r in seasons)
        result['baselineBrier']=round(sum(r['baselineBrier']*r['games'] for r in seasons)/n,6) if n else None
        result['challengerBrier']=round(sum(r['challengerBrier']*r['games'] for r in seasons)/n,6) if n else None
        result['candidateQualifiedForFurtherResearch']=(len(seasons)>=2 and n>=400 and
            result['improvingSeasons']>=2 and
            (result['baselineBrier']-result['challengerBrier'])>=.001)
        result['historicalInjuryTrainingGames']=sum(
             bool(r['features'][FEATURES.index('injury_archive_available')]) for r in rows)
        result['historicalQBTrainingGames']=sum(
             bool(r['features'][FEATURES.index('qb_available')]) for r in rows)
        result['historicalTacticalTrainingGames']=sum(
             bool(r['features'][FEATURES.index('tactical_available')]) for r in rows)
        result['activationGate']={
             'status':'LOCKED — independent forward validation required',
             'minProspectiveGradedGames':100,
             'minProspectiveBrierGain':.001,
             'requireVersionMatch':VERSION,
             'autoPromote':False}
        if len(rows)>=900:
            model=_fit(rows)
            forecasts=_explain(model,upcoming)
            result['trainSeasons']=[min(r['season'] for r in rows),max(r['season'] for r in rows)]
            result['status']='historical-research-candidate' if result['candidateQualifiedForFurtherResearch'] else 'research-only'
            return result,{r['id']:{**v,'version':VERSION,'researchOnly':True,
                'productionWeight':0,'bettingEligible':False} for r,v in zip(upcoming,forecasts)}
        result['reason']='Too few completed prior-season games'
    except (ImportError,TypeError,ValueError,RuntimeError,OverflowError) as exc:
        result.update(status='unavailable',reason=type(exc).__name__+': '+str(exc)[:180])
    return result,{}
