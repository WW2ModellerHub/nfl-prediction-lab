"""Point-in-time, score-only evaluation of historical baseline predictions.

Closing American moneylines are used ONLY AFTER a game is complete to assess a
market benchmark. They are never model inputs, and are not an archive of UK odds.
The historical Elo predictions are sequential reconstructions, NOT originally
published pregame forecasts. Prospective records are graded elsewhere.
"""
from __future__ import annotations
import math
import random
from collections import defaultdict
from statistics import mean


def american_probability(odds):
    """Convert American odds to break-even probability, or None if invalid."""
    if odds is None or not math.isfinite(float(odds)) or odds == 0:
        return None
    odds = float(odds)
    return 100.0/(100.0+odds) if odds > 0 else (-odds)/(100.0-odds)


def no_vig_home_probability(home_american, away_american):
    home = american_probability(home_american)
    away = american_probability(away_american)
    if home is None or away is None or home+away<=0:
        return None
    return home/(home+away)


def _metrics(rows):
    if not rows:
        return {'games':0,'accuracy':None,'brier':None,'logLoss':None}
    return {
        'games':len(rows),
        'accuracy':round(mean(float((p>=.5)==bool(y)) for p,y in rows),4),
        'brier':round(mean((p-y)**2 for p,y in rows),5),
        'logLoss':round(mean(-(y*math.log(max(1e-8,p))+(1-y)*math.log(max(1e-8,1-p))) for p,y in rows),5)
    }


def _week_block_ci(entries, repetitions=400, seed=1640):
    """Resample independent-ish season-week blocks, not individual games."""
    blocks=defaultdict(list)
    for r in entries:
        blocks[(r['season'],r['week'])].append((r['p']-r['y'])**2-(r['market']-r['y'])**2)
    if len(blocks)<6:
        return None
    sets=list(blocks.values()); rng=random.Random(seed)
    estimates=[]
    for _ in range(repetitions):
        sample=[sets[rng.randrange(len(sets))] for __ in range(len(sets))]
        values=[v for group in sample for v in group]
        estimates.append(sum(values)/len(values))
    estimates.sort()
    return [round(estimates[int(.025*(repetitions-1))],5),
            round(estimates[int(.975*(repetitions-1))],5)]


def build_audit(historical_rows, as_of=None):
    """Use baseline probabilities reconstructed before game results were applied.

    historical_rows: completed matchup objects with homeProbability, outcome,
    season, week and optional closingHomeMoneyline/closingAwayMoneyline.
    """
    by_season=defaultdict(list)
    for r in historical_rows:
        try:
            y=r['outcome'];p=float(r['homeProbability'])
            if y not in (0,1,.5) or not 0<=p<=1:continue
            by_season[int(r['season'])].append(r)
        except (TypeError, ValueError, KeyError):continue
    def summary(items):
        valid=[x for x in items if x['outcome'] in (0,1)]
        paired=[]
        for r in valid:
            market=no_vig_home_probability(r.get('closingHomeMoneyline'),r.get('closingAwayMoneyline'))
            if market is not None:
                paired.append({'season':r['season'],'week':r['week'],'p':r['homeProbability'],
                               'market':market,'y':r['outcome']})
        overall=_metrics([(r['homeProbability'],r['outcome']) for r in valid])
        mkt=_metrics([(r['market'],r['y']) for r in paired])
        matched=_metrics([(r['p'],r['y']) for r in paired])
        if paired:
            gap=mean((r['p']-r['y'])**2-(r['market']-r['y'])**2 for r in paired)
        else:gap=None
        return {'completedGames':len(items),'ties':len(items)-len(valid),'baseline':overall,
                'market':mkt,'baselineOnMarketMatchedGames':matched,
                'marketCoverage':len(paired),'modelMinusMarketBrier':round(gap,5) if gap is not None else None,
                'modelMinusMarketBrier95CI':_week_block_ci(paired)}
    seasons=[{'season':s,**summary(by_season[s])} for s in sorted(by_season)]
    overall=summary([r for s in sorted(by_season) for r in by_season[s]])
    return {'status':'historical-score-audit','asOf':as_of,
            'sample':'Completed 2024+ games, excluding tied games from two-way winner metrics',
            'model':'Reconstructed Elo + scoring-form baseline only; advanced overlays not included',
            'marketDefinition':'Retrospective closing two-way American moneyline, converted to no-vig probability',
            'marketIsPregameSnapshot':False,'clvAvailable':False,'ukBookmakersCovered':False,
            'overall':overall,'seasons':seasons,
            'notes':['Lower Brier score is better; a positive model-minus-market gap means the model performed worse.',
                     'Closing lines are retrospective benchmarks, never input features or proof of an actionable edge.',
                     'Season-week block bootstrap intervals account for some within-week correlation; they are approximate.',
                     'Historical reconstructions are not originally timestamped pregame forecasts.',
                     'Only original archived forward picks establish prospective performance.']}
