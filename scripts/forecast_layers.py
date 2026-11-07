"""Reconciled, source-labelled win-probability contribution ledger.

The forecast is one published number. Supporting layers are distinct:
- Elo strength + home advantage: 60% of the model's unbounded Elo vote;
- historical scoring form: 40% of the normal-margin probability vote;
- at most one historically approved statistical overlay;
- independently identified provisional QB/injury estimates.

For every game, applied deltas are in HOME-win probability units and sum
back to the actual published homeProbability. Never assign numerical
influence to data that the prediction did not use.
"""
from __future__ import annotations
import math

LAYERS=(
    ('situational','Rest, travel & overtime','Historical selection required; observations otherwise context-only'),
    ('tactical','Passing, rushing & pressure','Historical selection required; descriptive EPA is not a probability adjustment'),
    ('player','Player availability model','Historically selected model only; injury flags alone have no validated weight'),
    ('qb','Validated QB model','Historical selection required; not the separately labelled research QB preview'),
)
EXPERIMENTAL=(
    ('qbStatisticalHomeDelta','qb-statistical','QB efficiency research','Provisional: historical QB EPA/sack signal, not prospectively calibrated'),
    ('qbReplacementHomeDelta','qb-replacement','QB replacement','Provisional: confirmed-news-gated replacement scenario with unvalidated point mapping'),
    ('injuryHomeDelta','other-injuries','Other reported absences','Provisional: dated reports, not official game-day inactives'),
)

def _p(x):
    try:
        if isinstance(x,bool):return None
        v=float(x)
        return v if math.isfinite(v) and 0 <= v <= 1 else None
    except (TypeError,ValueError,OverflowError):return None

def _delta(x):
    try:
        if isinstance(x,bool) or x is None:return None
        v=float(x)
        return v if math.isfinite(v) and -1 <= v <= 1 else None
    except (TypeError,ValueError,OverflowError):return None

def explain(game):
    final=_p(game.get('homeProbability'))
    if final is None:
        return {'status':'unavailable','reason':'No valid published game probability',
                'layers':[],'reconciles':False}
    baseline=_p(game.get('baselineHomeProbability'))
    if baseline is None:baseline=final
    pre=_p(game.get('prePersonnelProbability'))
    if pre is None:pre=final
    # The trained model publishes a convex 60% Elo / 40% scoring vote,
    # followed by explicit clipping to [5%,95%].
    elo=_p(game.get('eloModelProbability'))
    form=_p(game.get('formModelProbability'))
    selected=game.get('overlayType','none')
    selected=selected if game.get('adjustmentActive') and selected in dict((k,True) for k,_,_ in LAYERS) else 'none'
    current=0.5
    rows=[]
    def add(key,label,change,kind,reason):
        nonlocal current
        current+=change
        rows.append({'key':key,'label':label,'applied':True,'deltaHome':round(change,7),
                     'afterHome':round(current,7),'kind':kind,'explanation':reason})
    def context(key,label,reason):
        rows.append({'key':key,'label':label,'applied':False,'deltaHome':None,
                     'afterHome':round(current,7),'kind':'not-weighted','explanation':reason})
    if elo is not None and form is not None:
        e=.6*(elo-.5)
        f=.4*(form-.5)
        add('elo','Elo strength & home field',e,'core',
            '60% of historical Elo strength and venue context relative to a neutral 50/50 reference')
        add('form','Scoring form & projected margin',f,'core',
            '40% of the normal-score-margin forecast, based on prior team scoring results')
        gap=baseline-current
        if abs(gap)>0.00015:
            add('bounds','Probability model limit',gap,'core',
                'Elo/form mix bounded to 5–95%, with published baseline precision')
        else:
            # The baseline is rounded for transport. This tiny remainder is
            # explicitly included in scoring form, rather than displayed as an
            # unexplained 0.0 pp contribution.
            rows[-1]['deltaHome']=round(f+gap,7)
            current=baseline
            rows[-1]['afterHome']=round(current,7)
    else:
        add('core','Elo & scoring form combined',baseline-.5,'core',
            'Underlying Elo and normal-margin components were not published separately; this is the observed combined baseline')
    for key,label,reason in LAYERS:
        if key==selected:
            add(key,label,pre-baseline,'validated',
                'Applied as the single historically selected overlay before provisional player assessments')
        else:context(key,label,reason+'; no forecast percentage-point contribution')
    s=game.get('personnelScenario') or {}
    have_components=all(_delta(s.get(field)) is not None for field,_,_ in EXPERIMENTAL)
    if have_components:
        for field,key,label,reason in EXPERIMENTAL:
            effect=_delta(s[field])
            if abs(effect)>0.0000001:
                add(key,label,effect,'provisional',reason)
            else:
                reason=('Qualified effect not applied; not proof of a healthy or unchanged roster' if key=='other-injuries' else
                        'No separate qualifying adjustment activated in this forecast')
                context(key,label,reason)
    else:
        for _,key,label,reason in EXPERIMENTAL:
            context(key,label,'Separate percentage-point attribution not available in this snapshot; no value inferred')
    diff=final-current
    if abs(diff)>0.00015:
        add('unattributed','Other or cached forecast change',diff,'unverified',
            'The current forecast differs from the sum of the individually reported model components; treat this as unverified rather than attributing it to a player')
    else:
        # Transport precision difference only; do not invent extra factors.
        current=final
    context('weather','Weather & venue conditions',
            'Displayed as context; weather has no independently validated probability weight')
    experimental=any(x['applied'] and x['kind']=='provisional' for x in rows)
    warnings=[]
    if experimental:warnings.append('Provisional QB/injury assumptions have not passed prospective validation')
    if any(x['key']=='unattributed' for x in rows):warnings.append('Some published change could not be attributed to a named model layer')
    if elo is None or form is None:warnings.append('Elo/form votes unavailable separately; combined baseline only')
    return {'status':'provisional' if experimental else 'partially-unverified' if warnings else 'model-derived',
            'homeTeam':game.get('home'),'awayTeam':game.get('away'),
            'homeProbability':round(final,7),
            'awayProbability':round(1-final,7),
            'winner':game.get('home') if final>=.5 else game.get('away'),
            'winnerProbability':round(max(final,1-final),7),
            'referenceHomeProbability':.5,
            'eloFormBaseline':round(baseline,7),
            'beforePersonnelHomeProbability':round(pre,7),
            'selectedOverlay':selected,
            'layers':rows,
            'warnings':warnings,
            'reconciles':abs(current-final)<.00015,
            'actualVsBaselinePP':round((final-baseline)*100,3),
            'note':'Deltas are percentage points of HOME win probability; reverse the sign for the away team. Muted layers do not change the probability. The 50/50 start is an attribution reference, not a separate model prediction. Rounding can change displayed totals by 0.1 pp.'}
