"""Player-impact research gate for NFL Prediction Lab.

Point-in-time rules:
- Historical QB indicators come from plays before this game's kickoff.
- Expected QBs come exclusively from depth-chart snapshots published before
  the prediction cutoff; the current game's actual passer is NEVER a feature.
- Injury alerts come from timestamped pregame practice/injury records, not
  post-game actives or postgame statistics.
- A missing injury report is not evidence that a player was healthy.

The model is a penalised residual/log-odds overlay to the Elo/form baseline.
It is enabled only by sequential held-out-season evidence. Selection years
are research tests, not a prospective independent validation.
"""
from __future__ import annotations
from datetime import datetime, timezone
from statistics import mean
from situational_validation import logit, logistic, clip, _solve

FEATURES = ('qb_epa_edge', 'qb_change_edge', 'qb_sack_edge', 'key_reported_absences_edge')
MIN_QB_DROPBACKS=80
MAX_CHART_AGE_DAYS=21
MIN_TRAIN=160
MIN_SEASON_TEST=80
MIN_VALIDATION_GAMES=350
MIN_BRIER_GAIN=.001
PENALTY=85.0

def _safe_float(v):
    try:
        x=float(v)
        return x if -1e6<x<1e6 else None
    except (ValueError, TypeError): return None

def _clipval(x, bound): return max(-bound,min(bound,x))

def snapshot(game, qb, injury, depth, cutoff, verified_injury_seasons=()):
    """Construct usable features and an audit record from pregame observations.

    The injury feature is null until the relevant season's archive was loaded;
    zero when fully loaded means no matching pregame flags *observed*, not
    proof of full health. Every unavailable feature blocks probability fitting.
    """
    reasons=[]
    detail={}
    valid_qbs={}
    for side in ('home','away'):
        team=game[side]
        q=(qb or {}).get(side) or {}
        chart=(depth or {}).get(team) or {}
        projected=chart.get('qb') or {}
        asof=chart.get('asOf')
        chart_age=None
        if asof:
            try:
                stamp=datetime.fromisoformat(asof.replace('Z','+00:00'))
                if stamp.tzinfo is None:stamp=stamp.replace(tzinfo=timezone.utc)
                chart_age=(cutoff-stamp).total_seconds()/86400
            except (TypeError, ValueError):pass
        # QB must be derived from a timely dated projection AND sufficient
        # completed historical dropbacks. Neither may come from the game itself.
        sample=q.get('sample') or {}
        matched=bool(projected.get('id') and q.get('playerId')==projected.get('id'))
        eligible=(matched and chart_age is not None and 0<=chart_age<=MAX_CHART_AGE_DAYS
                  and (sample.get('dropbacks') or 0)>=MIN_QB_DROPBACKS
                  and _safe_float(sample.get('epaPerDropback')) is not None
                  and _safe_float(sample.get('sackRate')) is not None)
        if not eligible:
            reasons.append(f'{team}: needs a recent pregame depth-chart QB and ≥{MIN_QB_DROPBACKS} prior dropbacks')
        valid_qbs[side]=(q, sample) if eligible else None
        detail[side]={'team':team,'projectedQB':projected.get('name'),
                      'qbSampleDropbacks':sample.get('dropbacks'),
                      'qbChangeFlag':bool(q.get('starterChangeWatch')),
                      'depthAsOf':asof,'depthAgeDays':round(chart_age,1) if chart_age is not None else None,
                      'verifiedQBHistory':eligible}
    inj_verified=game['season'] in set(verified_injury_seasons or ())
    if not inj_verified:reasons.append(f'{game["season"]}: timestamped injury archive not confirmed loaded')
    def reported_absences(side):
        """Weak *reported* availability indicator; NOT verified game inactives."""
        v=0.0;count=0
        if not inj_verified:return None,0
        for p in (injury or {}).get(side,[]):
            if not p.get('starterOnDepthChart'):continue
            status=str(p.get('status') or '').upper().strip()
            if status not in ('OUT','DOUBTFUL'):continue
            count+=1
            role=2.0 if p.get('position')=='QB' else 1.0
            v+=role*(1.0 if status=='OUT' else 0.45)
        return min(4.0,v),count
    h_abs,h_count=reported_absences('home');a_abs,a_count=reported_absences('away')
    detail['home']['flaggedKeyAbsences']=h_count
    detail['away']['flaggedKeyAbsences']=a_count
    features=None
    if not reasons:
        home=valid_qbs['home'][1]; away=valid_qbs['away'][1]
        features=[
            _clipval(home['epaPerDropback']-away['epaPerDropback'],.65),
            int(valid_qbs['away'][0]['starterChangeWatch'])-int(valid_qbs['home'][0]['starterChangeWatch']),
            _clipval(away['sackRate']-home['sackRate'],.35),
            _clipval(a_abs-h_abs,4.0),
        ]
    return {'status':'eligible' if features is not None else 'informational',
            'eligible':features is not None,'features':features,
            'reason':'All pregame player research inputs available.' if features is not None else '; '.join(reasons),
            'home':detail['home'],'away':detail['away'],
            'injuryArchiveLoaded':inj_verified,'probabilityWeight':0,
            'note':'Correlational player indicators, not causal missing-player point estimates. No adjustment without a passed model gate.'}

def fit(rows):
    """Regularised logistic regression on pregame residuals; no future scores."""
    if len(rows)<MIN_TRAIN:return [0.0]*len(FEATURES)
    nonzero=[sum(abs(r['features'][i])>1e-10 for r in rows) for i in range(len(FEATURES))]
    active=[i for i,c in enumerate(nonzero) if c>=20]
    if not active:return [0.0]*len(FEATURES)
    w=[0.0]*len(active)
    for _ in range(25):
        grad=[-PENALTY*x for x in w]
        h=[[PENALTY*(j==k) for k in range(len(w))] for j in range(len(w))]
        for r in rows:
            x=[r['features'][i] for i in active]
            z=logit(r['p'])+sum(a*b for a,b in zip(x,w))
            p=logistic(z); curv=p*(1-p); error=r['y']-p
            for j in range(len(w)):
                grad[j]+=x[j]*error
                for k in range(len(w)):h[j][k]+=curv*x[j]*x[k]
        change=_solve(h,grad)
        w=[_clipval(v+d,.7) for v,d in zip(w,change)]
        if max(abs(d) for d in change)<1e-7:break
    out=[0.0]*len(FEATURES)
    for j,v in zip(active,w):out[j]=round(v,6)
    return out

def predict(p,features,weights):
    if features is None or len(features)!=len(FEATURES):return p
    return clip(logistic(logit(p)+sum(a*b for a,b in zip(features,weights))))

def validate(rows,current_season):
    """Only completed prior seasons train/choose an adjustment for today."""
    historical=[r for r in rows if r.get('season',current_season)<current_season
                and r.get('y') in (0,1) and r.get('features') is not None]
    seasons=sorted({r['season'] for r in historical})
    evaluations=[]
    for season in seasons[1:]:
        train=[r for r in historical if r['season']<season]
        test=[r for r in historical if r['season']==season]
        if len(train)<MIN_TRAIN or len(test)<MIN_SEASON_TEST:continue
        coefs=fit(train)
        baseline=mean((r['p']-r['y'])**2 for r in test)
        adjusted=mean((predict(r['p'],r['features'],coefs)-r['y'])**2 for r in test)
        evaluations.append({'season':season,'games':len(test),'baselineBrier':round(baseline,5),
                            'adjustedBrier':round(adjusted,5),'brierGain':round(baseline-adjusted,5)})
    recent=evaluations[-3:]
    n=sum(e['games'] for e in recent)
    gain=sum(e['games']*e['brierGain'] for e in recent)/n if n else 0
    positives=sum(e['brierGain']>0 for e in recent)
    enabled=(len(recent)>=2 and n>=MIN_VALIDATION_GAMES and positives>=2 and gain>=MIN_BRIER_GAIN)
    learned=fit(historical)
    return {'enabled':enabled,'status':'ACTIVE — research gate passed' if enabled else 'OFF — player impact unproven',
            'sampleSize':len(historical),'historicalSeasons':seasons,'trainedThroughSeason':max(seasons,default=None),
            'evaluationGames':n,'improvingSeasons':positives,'brierGain':round(gain,5) if n else None,
            'seasons':evaluations,'coefficients':dict(zip(FEATURES,learned if enabled else [0.0]*len(FEATURES))),
            'thresholds':{'minTrain':MIN_TRAIN,'minEvaluationGames':MIN_VALIDATION_GAMES,
                          'minPositiveSeasons':2,'minBrierGain':MIN_BRIER_GAIN,'minQBDropbacks':MIN_QB_DROPBACKS},
            'researchOnly':True,
            'notes':['Strictly prior seasons are used in each evaluation; current-season results excluded from activation and coefficients.',
                     'Evaluation seasons decide whether to activate: selection is not an independent prospective blind test.',
                     'QB starter projections are dated depth-chart observations, not confirmed starters.',
                     'OUT/DOUBTFUL is a reported status, not verified gameday inactivity or a causal point deduction.']}
