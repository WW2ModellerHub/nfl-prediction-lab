"""XGBoost multi-factor challenger. Research only: NEVER modifies live picks.

Training uses completed past seasons and only pre-kickoff team/QB/tactical
observations. No current-season labels, closing odds or injury statuses.
"""
from statistics import mean
import math

FEATURES=('elo_gap','form_gap','defense_gap','home_field','rest_gap',
          'qb_epa_edge','qb_sack_edge','qb_available','pass_matchup',
          'rush_matchup','hit_sack_matchup','explosive_matchup','tactical_available')

def vector(game,p):
    s=p.get('situation') or {}
    h=(s.get('home') or {}).get('fullRestDays')
    a=(s.get('away') or {}).get('fullRestDays')
    q=p.get('qb_research') or {}
    qb=q.get('features') if q.get('eligible') else None
    t=p.get('tactical') or {}
    tac=t.get('features') if t.get('status')=='ready' else None
    x=[(p.get('elo_home',1500)-p.get('elo_away',1500))/400,
       (p.get('home_form',22)-p.get('away_form',22))/16,
       (p.get('away_allowed',22)-p.get('home_allowed',22))/16,
       0 if game.get('neutral') else 1,
       max(-10,min(10,h-a))/7 if isinstance(h,(float,int)) and isinstance(a,(float,int)) else 0,
       qb[0] if qb else 0,qb[1] if qb else 0,1 if qb else 0,
       *([max(-3,min(3,float(z))) for z in tac[:4]] if tac else [0,0,0,0]),
       1 if tac else 0]
    if len(x)!=len(FEATURES):raise ValueError('Challenger schema mismatch')
    return x

def _logit(x):
    p=max(.005,min(.995,float(x)))
    return math.log(p/(1-p))

def _fit(rows):
    import numpy as np
    from xgboost import XGBClassifier
    X=np.array([r['features'] for r in rows],dtype=np.float32)
    y=np.array([r['y'] for r in rows],dtype=np.int8)
    base=np.array([_logit(r['p']) for r in rows],dtype=np.float32)
    model=XGBClassifier(objective='binary:logistic',n_estimators=85,
        max_depth=2,learning_rate=.025,subsample=.85,colsample_bytree=.85,
        min_child_weight=15,reg_alpha=2,reg_lambda=40,
        n_jobs=2,random_state=47,tree_method='hist',eval_metric='logloss')
    model.fit(X,y,base_margin=base)
    return model

def _predict(model,rows):
    import numpy as np
    X=np.array([r['features'] for r in rows],dtype=np.float32)
    base=np.array([_logit(r['p']) for r in rows],dtype=np.float32)
    return [float(v) for v in model.predict_proba(X,base_margin=base)[:,1]]

def run(history,upcoming,current_season):
    result={'status':'unavailable','researchOnly':True,'productionWeight':0,
        'source':'XGBoost (Apache-2.0), pregame nflverse signals',
        'features':list(FEATURES),'seasons':[],
        'note':'Shadow forecasts never change published percentages or picks. Evaluated years are model-selection data, not an independent blind prospective test.'}
    try:import xgboost
    except ImportError:
        result['reason']='Optional xgboost package not installed'
        return result,{}
    rows=[r for r in history if r.get('y') in (0,1) and r['season']<current_season]
    years=sorted(set(r['season'] for r in rows if r['season']>=2024))
    try:
        seasons=[]
        for year in years:
            train=[r for r in rows if r['season']<year]
            test=[r for r in rows if r['season']==year]
            if len(train)<900 or len(test)<180:continue
            forecasts=_predict(_fit(train),test)
            baseline=mean((r['p']-r['y'])**2 for r in test)
            challenger=mean((f-r['y'])**2 for f,r in zip(forecasts,test))
            seasons.append({'season':year,'games':len(test),
                'baselineBrier':round(baseline,5),
                'challengerBrier':round(challenger,5),
                'brierGain':round(baseline-challenger,5),
                'baselineAccuracy':round(mean((r['p']>=.5)==bool(r['y']) for r in test),4),
                'challengerAccuracy':round(mean((f>=.5)==bool(r['y']) for f,r in zip(forecasts,test)),4)})
        n=sum(r['games'] for r in seasons)
        result['seasons']=seasons
        result['evaluationGames']=n
        result['improvingSeasons']=sum(r['brierGain']>0 for r in seasons)
        result['baselineBrier']=round(sum(r['baselineBrier']*r['games'] for r in seasons)/n,5) if n else None
        result['challengerBrier']=round(sum(r['challengerBrier']*r['games'] for r in seasons)/n,5) if n else None
        result['candidateQualifiedForFurtherResearch']=(len(seasons)>=2 and n>=400 and
            result['improvingSeasons']>=2 and result['baselineBrier']-result['challengerBrier']>=.001)
        if len(rows)>=900:
            predictions=_predict(_fit(rows),upcoming) if upcoming else []
            result['trainSeasons']=[min(r['season'] for r in rows),max(r['season'] for r in rows)]
            result['status']='validated-research' if result['candidateQualifiedForFurtherResearch'] else 'research-only'
            return result,{r['id']:round(p,4) for r,p in zip(upcoming,predictions)}
        result['reason']='Too few completed prior-season games for model training'
    except (TypeError,ValueError,RuntimeError) as exc:
        result.update(status='unavailable',reason=type(exc).__name__+': '+str(exc)[:180])
    return result,{}
