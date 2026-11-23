"""Shootout Heat: which games this week are likely to be the highest scoring.

A transparent, in-house rating (not HeatRadar's or any bookmaker's). It starts
from the model's projected total points and adds three adjustments built from
data the pipeline already has:

* passing matchup: each offence's EPA per dropback against the opposing
  defence's EPA allowed, relative to the slate average;
* explosive plays: each offence's explosive-pass rate against the opponent's
  explosive-pass rate allowed, relative to the slate average;
* weather: strong wind, likely rain/snow, snowfall and severe cold reduce
  scoring outdoors; enclosed stadiums get no weather adjustment.

The adjustment weights are heuristics, not fitted values. That is why every
pregame rating is archived before kickoff and later graded against actual
final totals (``data/shootout-log.json``): the record shows whether the heat
ranking, and the adjustments, actually beat the plain projected total.

Nothing here changes a win probability.
"""
from __future__ import annotations
from datetime import datetime, timezone
from pathlib import Path
import json
import math

VERSION = 1
LOG_PATH = Path('data/shootout-log.json')
# Rating scale: a "shootout total" of 36 points maps to 0 and 56 to 100.
SCALE_LOW, SCALE_HIGH = 36.0, 56.0
PASS_POINTS_PER_EPA = 30.0       # ~60 combined dropbacks × 0.5 shrinkage
EXPLOSIVE_POINTS_PER_RATE = 40.0  # ~60 dropbacks × ~1.3 pts per extra explosive × 0.5 shrinkage
TIERS = ((80, 'Shootout'), (60, 'High'), (40, 'Average'), (0, 'Low'))


def _num(x):
    if x is None or isinstance(x, bool):
        return None
    try:
        z = float(x)
        return z if math.isfinite(z) else None
    except (TypeError, ValueError):
        return None


def _date(x):
    try:
        d = x if isinstance(x, datetime) else datetime.fromisoformat(str(x).replace('Z', '+00:00'))
        return d.astimezone(timezone.utc) if d.tzinfo else None
    except (TypeError, ValueError, OverflowError):
        return None


def _mean(values):
    values = [v for v in values if v is not None]
    return sum(values) / len(values) if values else None


def tier(rating):
    return next(label for floor, label in TIERS if rating >= floor)


def _matchup(game, off_key, def_key):
    """Average of (offence metric + opposing defence allowed metric)/2 for both sides."""
    t = game.get('tactical') or {}
    if t.get('status') != 'ready':
        return None
    home, away = t.get('home') or {}, t.get('away') or {}
    pairs = [(_num(home.get(off_key)), _num(away.get(def_key))), (_num(away.get(off_key)), _num(home.get(def_key)))]
    if any(a is None or b is None for a, b in pairs):
        return None
    return sum((a + b) / 2 for a, b in pairs) / 2


def weather_adjustment(weather):
    """Return (points, reasons). Indoor/unknown weather contributes nothing."""
    w = weather or {}
    if w.get('status') not in ('forecast', 'roof-unconfirmed'):
        return 0.0, []
    # An unconfirmed roof may be closed: halve the outdoor effect.
    factor = 0.5 if w.get('status') == 'roof-unconfirmed' else 1.0
    pts, why = 0.0, []
    wind, gust = _num(w.get('windMph')), _num(w.get('gustMph'))
    if wind is not None and wind >= 12:
        p = min(6.0, (wind - 10) * 0.4)
        pts -= p
        why.append(f'wind {round(wind)} mph')
    elif gust is not None and gust >= 30:
        pts -= 1.0
        why.append(f'gusts {round(gust)} mph')
    rain = _num(w.get('precipitationChancePct'))
    if rain is not None and rain >= 50:
        pts -= 1.5
        why.append(f'{round(rain)}% precipitation')
    snow = _num(w.get('snowfallCm'))
    if snow is not None and snow >= 0.5:
        pts -= 2.0
        why.append(f'{snow:g} cm snow')
    temp = _num(w.get('temperatureC'))
    if temp is not None and temp <= -5:
        pts -= 1.0
        why.append(f'{round(temp)}°C')
    return round(pts * factor, 2), why


def rate_games(games):
    """Attach ``shootout`` to each upcoming game and return a summary dict."""
    rows = [g for g in games if isinstance(g, dict) and _num(g.get('predTotal')) is not None]
    pass_env = {g.get('id'): _matchup(g, 'passEPA', 'allowedPassEPA') for g in rows}
    expl_env = {g.get('id'): _matchup(g, 'explosivePass', 'explosiveAllowed') for g in rows}
    pass_avg, expl_avg = _mean(pass_env.values()), _mean(expl_env.values())
    for g in rows:
        total = _num(g['predTotal'])
        pe, ee = pass_env.get(g.get('id')), expl_env.get(g.get('id'))
        pass_pts = round((pe - pass_avg) * PASS_POINTS_PER_EPA, 2) if pe is not None and pass_avg is not None else 0.0
        expl_pts = round((ee - expl_avg) * EXPLOSIVE_POINTS_PER_RATE, 2) if ee is not None and expl_avg is not None else 0.0
        wx_pts, wx_why = weather_adjustment(g.get('weather'))
        shootout_total = round(total + pass_pts + expl_pts + wx_pts, 1)
        rating = int(round(max(0.0, min(100.0, (shootout_total - SCALE_LOW) / (SCALE_HIGH - SCALE_LOW) * 100))))
        g['shootout'] = {
            'version': VERSION, 'rating': rating, 'tier': tier(rating),
            'shootoutTotal': shootout_total, 'projectedTotal': total,
            'components': {'projectedTotal': total, 'passingMatchup': pass_pts,
                           'explosivePlays': expl_pts, 'weather': wx_pts},
            'weatherReasons': wx_why,
            'tacticalAvailable': pe is not None,
            'note': 'In-house heuristic; graded against final totals in the shootout record.'}
    # Rank within each week so the panel can show "this weekend".
    by_week = {}
    for g in rows:
        by_week.setdefault((g.get('season'), g.get('week')), []).append(g)
    for week_games in by_week.values():
        week_games.sort(key=lambda g: (-g['shootout']['shootoutTotal'], g.get('kickoff') or '', g.get('id') or ''))
        for i, g in enumerate(week_games, 1):
            g['shootout']['weekRank'] = i
            g['shootout']['weekGames'] = len(week_games)
    return len(rows)


def _spearman(xs, ys):
    n = len(xs)
    if n < 3:
        return None
    def ranks(v):
        order = sorted(range(n), key=lambda i: v[i])
        r = [0.0] * n
        i = 0
        while i < n:
            j = i
            while j + 1 < n and v[order[j + 1]] == v[order[i]]:
                j += 1
            for k in range(i, j + 1):
                r[order[k]] = (i + j) / 2 + 1
            i = j + 1
        return r
    rx, ry = ranks(xs), ranks(ys)
    mx, my = sum(rx) / n, sum(ry) / n
    cov = sum((a - mx) * (b - my) for a, b in zip(rx, ry))
    vx = math.sqrt(sum((a - mx) ** 2 for a in rx))
    vy = math.sqrt(sum((b - my) ** 2 for b in ry))
    return round(cov / (vx * vy), 3) if vx and vy else None


def record(games, schedule, now, path=LOG_PATH):
    """Archive the latest pre-kickoff rating per game, grade finals, return the record."""
    now = _date(now)
    if now is None:
        raise ValueError('Timezone-aware timestamp required')
    try:
        previous = json.loads(path.read_text(encoding='utf8')) if path.exists() else {}
    except (OSError, ValueError):
        raise ValueError('Unreadable shootout log; refusing to overwrite it')
    if previous and previous.get('schemaVersion') != VERSION:
        raise ValueError('Unexpected shootout log schema; refusing to overwrite it')
    entries = dict(previous.get('entries') or {})
    for g in games:
        s, kick = g.get('shootout'), _date(g.get('kickoff'))
        if not s or not kick or not now < kick:
            continue  # never record or revise a rating at/after kickoff
        entries[g['id']] = {'season': g.get('season'), 'week': g.get('week'), 'home': g.get('home'),
                            'away': g.get('away'), 'kickoff': kick.isoformat(), 'recordedAt': now.isoformat(),
                            'rating': s['rating'], 'tier': s['tier'], 'shootoutTotal': s['shootoutTotal'],
                            'projectedTotal': s['projectedTotal'], 'components': s['components'],
                            **{k: v for k, v in (entries.get(g['id']) or {}).items() if k == 'firstRecordedAt'}}
        entries[g['id']].setdefault('firstRecordedAt', now.isoformat())
    finals = {str(x.get('id')): x for x in schedule or []
              if x.get('home_score') is not None and x.get('away_score') is not None}
    for gid, e in entries.items():
        f = finals.get(gid)
        if f and _date(e.get('recordedAt')) and _date(e['recordedAt']) < _date(e['kickoff']):
            e['actualTotal'] = int(f['home_score']) + int(f['away_score'])
    out = {'schemaVersion': VERSION, 'updatedAt': now.isoformat(), 'entries': dict(sorted(entries.items()))}
    path.parent.mkdir(exist_ok=True)
    path.write_text(json.dumps(out, ensure_ascii=False, indent=2) + '\n')
    return summarize(out['entries'])


def summarize(entries):
    """Grade the ranking per completed week, compared with the plain projected total."""
    weeks = {}
    for gid, e in entries.items():
        if e.get('actualTotal') is not None:
            weeks.setdefault((e.get('season'), e.get('week')), []).append({**e, 'id': gid})
    graded, hits, possible, heat_err, base_err, corr_heat, corr_base = [], 0, 0, [], [], [], []
    for (season, week), rows in sorted(weeks.items(), key=lambda kv: (kv[0][0] or 0, kv[0][1] or 0)):
        if len(rows) < 4:
            continue
        top_n = 3
        ours = {r['id'] for r in sorted(rows, key=lambda r: -r['shootoutTotal'])[:top_n]}
        actual = {r['id'] for r in sorted(rows, key=lambda r: -r['actualTotal'])[:top_n]}
        hit = len(ours & actual)
        hits += hit
        possible += top_n
        sh = _spearman([r['shootoutTotal'] for r in rows], [r['actualTotal'] for r in rows])
        sb = _spearman([r['projectedTotal'] for r in rows], [r['actualTotal'] for r in rows])
        if sh is not None:
            corr_heat.append(sh)
        if sb is not None:
            corr_base.append(sb)
        heat_err += [abs(r['shootoutTotal'] - r['actualTotal']) for r in rows]
        base_err += [abs(r['projectedTotal'] - r['actualTotal']) for r in rows]
        hottest = max(rows, key=lambda r: r['shootoutTotal'])
        highest = max(rows, key=lambda r: r['actualTotal'])
        graded.append({'season': season, 'week': week, 'games': len(rows), 'top3Hits': hit,
                       'rankCorrelation': sh, 'projectedTotalRankCorrelation': sb,
                       'hottest': {'game': f"{hottest['away']} @ {hottest['home']}", 'rating': hottest['rating'],
                                   'actualTotal': hottest['actualTotal']},
                       'highestScoring': {'game': f"{highest['away']} @ {highest['home']}",
                                          'actualTotal': highest['actualTotal'], 'rating': highest['rating']}})
    n = len(heat_err)
    return {'version': VERSION, 'gradedWeeks': len(graded), 'gradedGames': n,
            'top3HitRate': round(hits / possible, 3) if possible else None,
            'meanRankCorrelation': round(sum(corr_heat) / len(corr_heat), 3) if corr_heat else None,
            'meanProjectedTotalRankCorrelation': round(sum(corr_base) / len(corr_base), 3) if corr_base else None,
            'heatTotalMAE': round(sum(heat_err) / n, 2) if n else None,
            'projectedTotalMAE': round(sum(base_err) / n, 2) if n else None,
            'pendingGames': sum(1 for e in entries.values() if e.get('actualTotal') is None),
            'weeks': graded[-8:][::-1],
            'note': 'Top-3 hit rate: share of our three hottest games per week that finished among the three '
                    'highest-scoring. Rank correlation 1 = perfect ordering, 0 = no better than random.'}
