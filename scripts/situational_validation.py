"""Leakage-aware evaluation of incremental situational NFL matchup signals.

Fits a penalised logistic *offset* model against the existing pregame baseline:
  logit(P(home win)) = logit(P_baseline) + sum(beta_j * signed_signal_j).

It fits on past completed seasons only and evaluates later years sequentially.
The evaluation years are used to choose whether to ENABLE the adjustment,
so these numbers are *research/selection-validation*, not a final blind test.
The first genuinely untouched test is prospective predictions recorded afterward.
No bookmaker closing odds are inputs to the model.
No third-party packages are required (works on GitHub Actions).
"""
import math

FEATURES=('empty_tank','thursday_road_ot','blowout_bounce','nuclear_bounce','rest_edge','repeat_road')
PENALTY=45.0
MIN_TRAIN_GAMES=500
MIN_FEATURE_OBSERVATIONS=30
MIN_VALIDATION_GAMES=350
MIN_BRIER_IMPROVEMENT=0.001  # modest preregistered minimum improvement

def clip(v,low=0.02,high=0.98):return max(low,min(high,v))
def logit(p):
    p=clip(p);return math.log(p/(1-p))
def logistic(x):
    if x>=0:
        t=math.exp(-min(100,x));return 1/(1+t)
    t=math.exp(max(-100,x));return t/(1+t)

def feature_vector(context):
    values={k:0 for k in FEATURES}
    for s in context.get('signals',[]):
        key=s.get('id')
        if key not in values: continue
        sign=1 if s.get('direction')=='back' else -1
        if s.get('side')=='away': sign=-sign
        values[key]+=sign
    return tuple(max(-1,min(1,values[k])) for k in FEATURES)

def _solve(matrix,vector):
    n=len(vector)
    a=[list(matrix[i])+[vector[i]] for i in range(n)]
    for i in range(n):
        pivot=max(range(i,n),key=lambda j:abs(a[j][i]))
        a[i],a[pivot]=a[pivot],a[i]
        if abs(a[i][i])<1e-10:return [0.0]*n
        v=a[i][i]
        for k in range(i,n+1):a[i][k]/=v
        for j in range(n):
            if j==i:continue
            factor=a[j][i]
            if factor:
                for k in range(i,n+1):a[j][k]-=factor*a[i][k]
    return [a[i][n] for i in range(n)]

def fit(rows,penalty=PENALTY):
    """Penalised maximum likelihood, no intercept (baseline probability offset)."""
    if len(rows)<MIN_TRAIN_GAMES:return [0.0]*len(FEATURES)
    counts=[sum(bool(r['features'][i]) for r in rows) for i in range(len(FEATURES))]
    active=[i for i,c in enumerate(counts) if c>=MIN_FEATURE_OBSERVATIONS]
    if not active:return [0.0]*len(FEATURES)
    weights=[0.0]*len(active)
    for _ in range(25):
        grad=[-penalty*w for w in weights]
        h=[[penalty*(i==j) for j in range(len(active))] for i in range(len(active))]
        for r in rows:
            x=[r['features'][i] for i in active]
            if not any(x):continue
            z=logit(r['p'])+sum(w*a for w,a in zip(weights,x))
            pred=logistic(z)
            error=r['y']-pred
            curvature=pred*(1-pred)
            for j in range(len(active)):
                grad[j]+=x[j]*error
                for k in range(len(active)):
                    h[j][k]+=curvature*x[j]*x[k]
        change=_solve(h,grad)
        weights=[max(-0.8,min(0.8,w+d)) for w,d in zip(weights,change)]
        if max(abs(x) for x in change)<1e-6:break
    out=[0.0]*len(FEATURES)
    for i,w in zip(active,weights):out[i]=round(w,6)
    return out

def predict(p,features,coefs):
    return clip(logistic(logit(p)+sum(c*x for c,x in zip(coefs,features))))

def brier(rows,key='p'):
    return sum((r[key]-r['y'])**2 for r in rows)/len(rows) if rows else None

def validate(rows,current_season):
    """Walk seasons strictly forward, using completed seasons before current one.

    Current season results never influence the activation gate. To distinguish
    selection from verification, returned status explicitly says research-only.
    """
    finished=[r for r in rows if r.get('season',0)<current_season and r.get('y') in (0,1)]
    completed_seasons=sorted({r['season'] for r in finished})
    # Give the baseline 2016-2022 for an initial model, if those seasons exist.
    start=max(2023,completed_seasons[0]+5) if completed_seasons else 2023
    evaluations=[]
    for season in [s for s in completed_seasons if s>=start]:
        train=[r for r in finished if r['season']<season]
        test=[r for r in finished if r['season']==season]
        coefs=fit(train)
        evaluated=[{**r,'adjusted':predict(r['p'],r['features'],coefs)} for r in test]
        base=brier(evaluated)
        adj=brier(evaluated,'adjusted')
        evaluations.append({'season':season,'games':len(test),'baselineBrier':round(base,5),
                            'adjustedBrier':round(adj,5),'brierGain':round(base-adj,5),
                            'coefficients':dict(zip(FEATURES,coefs))})
    # Only the *last three* complete seasons decide activation. Never use 2026
    # results to decide 2026 predictions, even if the season is already underway.
    recent=evaluations[-3:]
    n=sum(r['games'] for r in recent)
    gain=(sum(r['brierGain']*r['games'] for r in recent)/n) if n else 0
    positive=sum(r['brierGain']>0 for r in recent)
    enabled=(len(recent)>=2 and n>=MIN_VALIDATION_GAMES
             and gain>=MIN_BRIER_IMPROVEMENT and positive>=2)
    training=[r for r in finished if r['season']<current_season]
    learned=fit(training)
    if not enabled:learned_active=[0.0]*len(FEATURES)
    else:learned_active=learned
    effects=[]
    for i,key in enumerate(FEATURES):
        observations=sum(bool(r['features'][i]) for r in training)
        effects.append({'id':key,'observations':observations,
                        'logOddsEffect':round(learned[i],4),
                        'approxPpAtEven':round((logistic(learned[i])-0.5)*100,2),
                        'applied':bool(enabled and learned[i] and observations>=MIN_FEATURE_OBSERVATIONS)})
    return {'status':'ACTIVE — research-gated adjustment' if enabled else 'OFF — incremental value not established',
            'enabled':enabled,'trainedThroughSeason':max((r['season'] for r in training),default=None),
            'evaluationYears':[e['season'] for e in evaluations],
            'selectionSample':n,'selectionBrierGain':round(gain,5) if n else None,
            'selectionYearsPositive':positive,'selectionYearsTested':len(recent),
            'thresholds':{'minGames':MIN_VALIDATION_GAMES,'minBrierGain':MIN_BRIER_IMPROVEMENT,
                          'minPositiveSeasons':2},'seasons':evaluations,
            'effects':effects,'coefficients':dict(zip(FEATURES,learned_active)),
            'notes':['Evaluation seasons are used to select the method; they are not an untouched final test.',
                     'Coefficients use only completed previous seasons; current-season final scores are excluded from adjustment training.',
                     'Signals are correlated and effects are penalised; coefficients are conditional associations, not causal effects.',
                     'Closing spread and odds are never used for model training.',
                     'A disabled gate means zero probability adjustment; situational flags remain visible.']}
