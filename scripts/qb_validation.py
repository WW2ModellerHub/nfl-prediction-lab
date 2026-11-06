"""QB-only sequential historical validation using earlier observed starters, not actual current-game QB.
Unvalidated results never alter published win percentages. No injury statuses used.
"""
from datetime import datetime,timezone
from statistics import mean
from situational_validation import logit,logistic,clip,_solve
FEATURES=('qb_epa_edge','qb_sack_edge','qb_change_watch')
MIN_DROPBACKS=80
MIN_TRAIN=140
PENALTY=90.

def _date(v):
    try:
        d=datetime.fromisoformat(str(v).replace('Z','+00:00'))
        return d if d.tzinfo else d.replace(tzinfo=timezone.utc)
    except (ValueError,TypeError):return None

def snapshot(game,qb,chart,cutoff):
    observations={};reasons=[]
    for side in ('home','away'):
        info=(qb or {}).get(side) or {}
        sample=info.get('sample') or {}
        recorded=info.get('lastGameLeader') or {}
        team_chart=(chart or {}).get(game[side],{})
        projected=team_chart.get('qb') or {}
        dated=_date(team_chart.get('asOf'))
        if projected:
            source_ok=(dated is not None and 0<=(cutoff-dated).total_seconds()/86400<=21
                       and bool(projected.get('id')) and projected.get('id')==info.get('playerId'))
        else:
            prior=_date(recorded.get('date'))
            source_ok=(prior is not None and 0<=(cutoff-prior).total_seconds()/86400<=35
                       and recorded.get('season')==game['season'] and
                       bool(recorded.get('id')) and recorded.get('id')==info.get('playerId'))
        ok=(source_ok and sample.get('dropbacks',0)>=MIN_DROPBACKS and
            isinstance(sample.get('epaPerDropback'),(int,float)) and
            isinstance(sample.get('sackRate'),(int,float)))
        if not ok:reasons.append(game[side]+': recent pregame QB and sufficient prior dropbacks unavailable')
        observations[side]=sample if ok else None
    vector=None
    if not reasons:
        h,a=observations['home'],observations['away']
        vector=[max(-.8,min(.8,h['epaPerDropback']-a['epaPerDropback'])),
                max(-.35,min(.35,a['sackRate']-h['sackRate'])),
                int(bool(qb['away'].get('starterChangeWatch')))-int(bool(qb['home'].get('starterChangeWatch')))]
    return {'eligible':vector is not None,'features':vector,
            'status':'eligible' if vector is not None else 'missing-observations',
            'reason':'; '.join(reasons) if reasons else 'Prior-game QB observations available',
            'source':'Recorded prior starter or dated pregame depth chart, not game-day confirmation'}

def fit(rows):
    if len(rows)<MIN_TRAIN:return [0.]*len(FEATURES)
    indices=[i for i in range(len(FEATURES)) if sum(abs(r['features'][i])>1e-9 for r in rows)>=15]
    if not indices:return [0.]*len(FEATURES)
    weights=[0.]*len(indices)
    for _ in range(20):
        grad=[-PENALTY*w for w in weights]
        mat=[[PENALTY*(i==j) for j in range(len(weights))] for i in range(len(weights))]
        for r in rows:
            x=[r['features'][i] for i in indices]
            p=logistic(logit(r['p'])+sum(a*b for a,b in zip(weights,x)))
            for j in range(len(weights)):
                grad[j]+=x[j]*(r['y']-p)
                for k in range(len(weights)):mat[j][k]+=p*(1-p)*x[j]*x[k]
        change=_solve(mat,grad)
        weights=[max(-.8,min(.8,w+d)) for w,d in zip(weights,change)]
        if max(abs(v) for v in change)<1e-7:break
    out=[0.]*len(FEATURES)
    for i,w in zip(indices,weights):out[i]=round(w,6)
    return out

def predict(prob,features,weights):
    if features is None:return prob
    return clip(logistic(logit(prob)+sum(a*b for a,b in zip(features,weights))))

def validate(rows,current_season):
    old=[r for r in rows if r.get('season',current_season)<current_season and
         r.get('features') is not None and r.get('y') in (0,1)]
    seasons=sorted({r['season'] for r in old})
    tests=[]
    for season in seasons[1:]:
        train=[r for r in old if r['season']<season]
        holdout=[r for r in old if r['season']==season]
        if len(train)<MIN_TRAIN or len(holdout)<80:continue
        coefs=fit(train)
        b=mean((r['p']-r['y'])**2 for r in holdout)
        a=mean((predict(r['p'],r['features'],coefs)-r['y'])**2 for r in holdout)
        tests.append({'season':season,'games':len(holdout),'baselineBrier':round(b,5),
                      'adjustedBrier':round(a,5),'brierGain':round(b-a,5)})
    recent=tests[-3:]
    n=sum(r['games'] for r in recent)
    gain=sum(r['games']*r['brierGain'] for r in recent)/n if n else 0
    positives=sum(x['brierGain']>0 for x in recent)
    enabled=(len(recent)>=2 and n>=350 and positives>=2 and gain>=.001)
    candidate_coeff=fit(old)
    coeff=candidate_coeff if enabled else [0.]*len(FEATURES)
    return {'enabled':enabled,'status':'ACTIVE — passed QB evidence gate' if enabled else 'OFF — QB adjustment unproven',
            'sampleSize':len(old),'trainedThroughSeason':max(seasons,default=None),
            'evaluationGames':n,'improvingSeasons':positives,'brierGain':round(gain,5) if n else None,
            'seasons':tests,'coefficients':dict(zip(FEATURES,coeff)),
            'candidateCoefficients':dict(zip(FEATURES,candidate_coeff)),
            'candidateResearchOnly':True,
            'researchOnly':True,'note':'Pre-kickoff QB observations, completed-season model selection, never postgame QB starters. Gate requires >=2 improving years, 350 test games, >=.001 Brier improvement.'}
