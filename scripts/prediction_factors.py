"""Compact pregame factor snapshots for every published prediction.

Upcoming fixtures already carry their full evidence on the dashboard row. Once a
fixture kicks off it drops out of ``nextGames`` and only the archived pregame
probability survives in ``recentKickoffs``. This module copies the matchup
factors that were on the *last pregame* dashboard row (venue / home-away, Elo,
scoring form, QBs, injuries, rest, tactical EPA, weather and which forecast
layers were applied) onto that archived row, so started and final games still
show every metric behind their frozen pick.

Nothing here recomputes or changes a probability. A snapshot is only taken from
a dashboard generated strictly before kickoff; otherwise an earlier carried
snapshot is reused, or none is attached.
"""
from __future__ import annotations
from datetime import datetime, timezone

INJURY_LIMIT = 14
TOP_LEVEL = ('homeName', 'awayName', 'stadium', 'stadiumId', 'roof', 'neutral', 'homeAdvantageElo',
             'eloHome', 'eloAway', 'formHome', 'formAway', 'allowedHome', 'allowedAway',
             'predHome', 'predAway')
QB_KEYS = ('team', 'qb', 'basis', 'confirmedStarter', 'starterChangeWatch')
SAMPLE_KEYS = ('games', 'dropbacks', 'epaPerDropback', 'sackRate', 'completionPct')
TACTICAL_KEYS = ('team', 'games', 'passEPA', 'rushEPA', 'allowedPassEPA', 'allowedRushEPA')


def _aware(value):
    try:
        d = value if isinstance(value, datetime) else datetime.fromisoformat(str(value).replace('Z', '+00:00'))
        return d.astimezone(timezone.utc) if d.tzinfo else None
    except (ValueError, TypeError, OverflowError):
        return None


def _pick(source, keys):
    source = source if isinstance(source, dict) else {}
    return {k: source[k] for k in keys if k in source}


def _players(rows, keys):
    rows = rows if isinstance(rows, list) else []
    return [_pick(r, keys) for r in rows if isinstance(r, dict)][:INJURY_LIMIT]


def factor_snapshot(row):
    """Return the subset of a dashboard ``nextGames`` row the factor panel needs."""
    snap = _pick(row, TOP_LEVEL)
    qb = row.get('qbIntelligence') or {}
    snap['qbIntelligence'] = {'status': qb.get('status')}
    for side in ('home', 'away'):
        entry = qb.get(side)
        if isinstance(entry, dict):
            item = _pick(entry, QB_KEYS)
            if isinstance(entry.get('sample'), dict):
                item['sample'] = _pick(entry['sample'], SAMPLE_KEYS)
            snap['qbIntelligence'][side] = item
    rep = row.get('qbReplacement') or {}
    snap['qbReplacement'] = _pick(rep, ('status', 'affectsPrediction'))
    inj = row.get('injuryIntelligence') or {}
    snap['injuryIntelligence'] = {'status': inj.get('status'),
        **{side: _players(inj.get(side), ('name', 'position', 'status', 'starterOnDepthChart'))
           for side in ('home', 'away')}}
    watch = row.get('supplementalInjuryWatch') or {}
    snap['supplementalInjuryWatch'] = {'status': watch.get('status'),
        **{side: [{**_pick(p, ('name', 'position', 'status')),
                   'recentUsage': _pick(p.get('recentUsage'), ('offensePct', 'defensePct'))}
                  for p in (watch.get(side) or []) if isinstance(p, dict)][:INJURY_LIMIT]
           for side in ('home', 'away')}}
    if isinstance(row.get('situation'), dict):
        snap['situation'] = row['situation']
    tac = row.get('tactical') or {}
    snap['tactical'] = {'status': tac.get('status'), 'advantages': tac.get('advantages') or [],
                        **{side: _pick(tac.get(side), TACTICAL_KEYS) for side in ('home', 'away')}}
    if isinstance(row.get('weather'), dict):
        snap['weather'] = row['weather']
    layers = (row.get('forecastExplanation') or {}).get('layers') or []
    snap['forecastExplanation'] = {'layers': [_pick(l, ('key', 'label', 'applied', 'deltaHome'))
                                              for l in layers if isinstance(l, dict)]}
    snap['forecastQuality'] = _pick(row.get('forecastQuality'), ('level',))
    return snap


def attach_pregame_factors(recent, old_dashboard):
    """Attach ``pregame`` factor snapshots to archived recent-kickoff rows.

    Source priority: the previous dashboard's upcoming row (only if that
    dashboard was generated before kickoff), then a snapshot already carried on
    the previous dashboard's recent-kickoff row. Returns the number attached.
    """
    old_dashboard = old_dashboard if isinstance(old_dashboard, dict) else {}
    generated = _aware(old_dashboard.get('generatedAt'))
    upcoming = {str(g.get('id')): g for g in old_dashboard.get('nextGames') or [] if isinstance(g, dict)}
    carried = {str(g.get('id')): g.get('pregame') for g in old_dashboard.get('recentKickoffs') or []
               if isinstance(g, dict) and isinstance(g.get('pregame'), dict)}
    attached = 0
    for row in recent:
        gid, kick = str(row.get('id')), _aware(row.get('kickoff'))
        old = upcoming.get(gid)
        snap = None
        if (old and generated and kick and generated < kick and old.get('kickoff') and
                _aware(old.get('kickoff')) == kick and old.get('home') == row.get('home') and
                old.get('away') == row.get('away')):
            snap = {**factor_snapshot(old), 'capturedAt': generated.isoformat()}
        elif gid in carried:
            snap = carried[gid]
        if snap:
            row['pregame'] = snap
            attached += 1
    return attached
