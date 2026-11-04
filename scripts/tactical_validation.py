"""Ridge logistic-offset ablation of team-level tactical indicators.

Selection years are evaluated sequentially, but selecting on these years is
still model selection — prospective predictions are the untouched test.
"""
from situational_validation import logit,logistic,clip,_solve
from statistics import mean
FEATURES=('pass_matchup','rush_matchup','hit_sack_matchup','explosive_matchup')
PENALTY=150.0

def fit(rows):
    if len(rows)<350:return [0.0]*len(FEATURES)
    weights=[0.0]*len(FEATURES)
    for _ in range(20):
        grad=[-PENALTY*w for w in weights]
        h=[[PENALTY*(i==j) for j in range(4)] for i in range(4)]
        for r in rows:
            x=r['features'];prob=logistic(logit(r['p'])+sum(w*a for w,a in zip(weights,x)))
            err=r['y']-prob;curv=prob*(1-prob)
            for j in range(4):
                grad[j]+=x[j]*err
                for k in range(4):h[j][k]+=curv*x[j]*x[k]
        change=_solve(h,grad)
        weights=[max(-.6,min(.6,w+d)) for w,d in zip(weights,change)]
        if max(abs(d) for d in change)<1e-7:break
    return weights

def predict(p,features,coefs):
    return clip(logistic(logit(p)+sum(c*f for c,f in zip(coefs,features))))

def validate(rows,current_season):
    rows=[r for r in rows if r['season']<current_season and r['y'] in (0,1)
          and r.get('features') is not None]
    seasons=sorted(set(r['season'] for r in rows))
    evals=[]
    for season in seasons[2:]:
        train=[r for r in rows if r['season']<season]
        tests=[r for r in rows if r['season']==season]
        if len(train)<350 or len(tests)<150:continue
        w=fit(train)
        baseline=mean((r['p']-r['y'])**2 for r in tests)
        adjusted=mean((predict(r['p'],r['features'],w)-r['y'])**2 for r in tests)
        evals.append({'season':season,'games':len(tests),'baselineBrier':round(baseline,5),
                      'adjustedBrier':round(adjusted,5),'brierGain':round(baseline-adjusted,5)})
    recent=evals[-3:];n=sum(r['games'] for r in recent)
    gain=sum(x['brierGain']*x['games'] for x in recent)/n if n else 0
    positives=sum(x['brierGain']>0 for x in recent)
    enabled=(len(recent)>=2 and n>=350 and positives>=2 and gain>=.001)
    learned=fit(rows)
    return {'status':'ACTIVE — gated' if enabled else 'OFF — incremental accuracy unproven',
            'enabled':enabled,'trainedThroughSeason':max((r['season'] for r in rows),default=None),
            'seasons':evals,'evaluationGames':n,'brierGain':round(gain,5),
            'improvingSeasons':positives,'coefficients':dict(zip(FEATURES,learned if enabled else [0]*4)),
            'researchOnly':True,'sampleSize':len(rows),
            'notes':'Ablation uses prior-season data only. Evaluation years were used for selection, not an independent blind test.'}
