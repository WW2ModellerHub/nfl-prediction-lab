"""Observed previous-game snap participation from nflreadpy, not availability."""
from collections import defaultdict
from datetime import datetime, timezone
import re

SOURCE='nflverse/PFR snap counts via nflreadpy (attribution: CC BY 4.0)'
ALIASES={'JAC':'JAX','LAR':'LA','WSH':'WAS','OAK':'LV','SD':'LAC','STL':'LA'}

def _key(value):
    s=re.sub(r'\b(jr|sr|ii|iii|iv)\b','',str(value or '').lower())
    return re.sub('[^a-z0-9]','',s)

def _pct(value):
    try:x=float(value)
    except (TypeError,ValueError):return None
    if x<0 or x>100:return None
    return x/100 if x>1 else x

def load_snap_counts(seasons):
    meta={'status':'unavailable','source':SOURCE,'seasons':list(seasons),'records':0}
    try:
        import nflreadpy
        frame=nflreadpy.load_snap_counts(list(seasons))
        required={'game_id','team','player','position','offense_pct','defense_pct'}
        if not required.issubset(frame.columns):
            raise ValueError('Unexpected snap columns: '+','.join(sorted(required-set(frame.columns))))
        rows=frame.select(['game_id','team','player','offense_pct','defense_pct']).to_dicts()
        meta.update(status='loaded' if rows else 'empty',records=len(rows))
        return rows,meta
    except Exception as exc:
        meta['error']=type(exc).__name__+': '+str(exc)[:180]
        return [],meta

class UsageHistory:
    def __init__(self,rows,games):
        times={g['id']:g['kickoff'] for g in games if isinstance(g.get('kickoff'),datetime)}
        self.lookup=defaultdict(list)
        for r in rows:
            kickoff=times.get(str(r.get('game_id') or ''))
            team=ALIASES.get(str(r.get('team') or '').upper(),str(r.get('team') or '').upper())
            key=_key(r.get('player'))
            a,b=_pct(r.get('offense_pct')),_pct(r.get('defense_pct'))
            if not kickoff or not team or not key or (a is None and b is None):continue
            self.lookup[team,key].append((kickoff,str(r.get('game_id')),a,b))
        for value in self.lookup.values():value.sort(key=lambda x:x[0])

    def recent(self,team,name,cutoff,limit=3):
        t=ALIASES.get(team,team)
        past={r[1]:r for r in self.lookup.get((t,_key(name)),[]) if r[0]<cutoff}
        chosen=sorted(past.values(),key=lambda x:x[0])[-limit:]
        if not chosen:return None
        off=[r[2] for r in chosen if r[2] is not None]
        de=[r[3] for r in chosen if r[3] is not None]
        return {'games':len(chosen),
                'offensePct':round(sum(off)/len(off),3) if off else None,
                'defensePct':round(sum(de)/len(de),3) if de else None,
                'lastGame':chosen[-1][0].astimezone(timezone.utc).isoformat(),
                'basis':'previous recorded snap counts only','availabilityConfirmed':False}

def enrich_upcoming(games,history,now):
    count=0
    for g in games:
        try:kick=datetime.fromisoformat(g['kickoff'].replace('Z','+00:00'))
        except (ValueError,TypeError,KeyError):continue
        cutoff=min(kick,now)
        for side in ('home','away'):
            for item in (g.get('supplementalInjuryWatch') or {}).get(side,[]):
                usage=history.recent(g[side],item.get('name'),cutoff)
                if usage:
                    item['recentUsage']=usage
                    count+=1
    return count
