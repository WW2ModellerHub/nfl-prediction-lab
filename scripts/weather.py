"""Venue-area kickoff weather via Open-Meteo; never a validated win-probability input.
Coordinates are approximate stadium areas. Neutral games never use the home team's city.
API free for non-commercial personal use; forecasts require periodic refresh.
"""
import json
import urllib.parse
import urllib.request
from datetime import datetime,timezone,timedelta

SOURCE='https://api.open-meteo.com/v1/forecast'
GEO={
'ARI00':(33.53,-112.26),'ATL00':(33.76,-84.40),'BAL00':(39.28,-76.62),
'BUF00':(42.77,-78.79),'CAR00':(35.23,-80.85),'CHI98':(41.86,-87.62),
'CIN00':(39.10,-84.52),'CLE00':(41.51,-81.70),'DAL00':(32.75,-97.09),
'DEN00':(39.74,-105.02),'DET00':(42.34,-83.05),'GNB00':(44.50,-88.06),
'HOU00':(29.69,-95.41),'IND00':(39.76,-86.16),'JAX00':(30.32,-81.64),
'KAN00':(39.05,-94.48),'LAX01':(33.95,-118.34),'LVR00':(36.09,-115.18),
'MIA00':(25.96,-80.24),'MIN01':(44.97,-93.26),'BOS00':(42.09,-71.26),
'NOR00':(29.95,-90.08),'NYC01':(40.81,-74.07),'PHI00':(39.90,-75.17),
'PIT00':(40.45,-80.02),'SEA00':(47.59,-122.33),'SFO01':(37.40,-121.97),
'TAM00':(27.98,-82.50),'NAS00':(36.17,-86.77),'WAS00':(38.91,-76.86),
'MAD01':(40.45,-3.69),'ATL97':(33.75,-84.40),'LAX00':(34.02,-118.29)
}

def _dt(v):
    if isinstance(v,datetime):return v if v.tzinfo else v.replace(tzinfo=timezone.utc)
    try:return datetime.fromisoformat(str(v).replace('Z','+00:00')).astimezone(timezone.utc)
    except (TypeError,ValueError):return None

def parse_hourly(payload,kickoff):
    hourly=payload.get('hourly',{}) if isinstance(payload,dict) else {}
    times=hourly.get('time',[])
    kickoff=_dt(kickoff)
    if not isinstance(times,list) or not times or not kickoff:return None
    try:
        stamps=[datetime.fromtimestamp(v,timezone.utc) if isinstance(v,(float,int)) else _dt(v) for v in times]
    except (TypeError,ValueError,OverflowError):return None
    valid=[(abs((v-kickoff).total_seconds()),i) for i,v in enumerate(stamps) if v]
    if not valid:return None
    delta,i=min(valid)
    if delta>3600:return None
    def value(key):
        values=hourly.get(key)
        v=values[i] if isinstance(values,list) and len(values)>i else None
        return round(float(v),1) if isinstance(v,(int,float)) else None
    values={'temperatureC':value('temperature_2m'),
            'precipitationChancePct':value('precipitation_probability'),
            'windMph':value('wind_speed_10m'),'gustMph':value('wind_gusts_10m'),
            'snowfallCm':value('snowfall')}
    return {'forecastFor':stamps[i].isoformat(),**values} if any(v is not None for v in values.values()) else None

def fetch(lat,long):
    params={'latitude':lat,'longitude':long,'hourly':'temperature_2m,precipitation_probability,wind_speed_10m,wind_gusts_10m,snowfall',
            'forecast_days':16,'timezone':'GMT','timeformat':'unixtime','wind_speed_unit':'mph'}
    url=SOURCE+'?'+urllib.parse.urlencode(params)
    req=urllib.request.Request(url,headers={'User-Agent':'NFLPredictionLab/1.9 personal research'})
    with urllib.request.urlopen(req,timeout=15) as resp:raw=resp.read(350001)
    if len(raw)>350000:raise ValueError('Weather response too large')
    return json.loads(raw.decode('utf-8'))

def enrich(games,now=None,fetcher=None):
    now=now or datetime.now(timezone.utc)
    fetcher=fetcher or fetch
    cache={};errors=[];counts={}
    for game in games:
        roof=str(game.get('roof') or '').lower().strip()
        venue=game.get('stadium') or 'Stadium unspecified'
        venue_id=game.get('stadiumId') or ''
        kickoff=_dt(game.get('kickoff'))
        status='unavailable';extra={}
        if roof in ('dome','closed'):
            status='indoor';extra={'note':'Enclosed roof per nflverse stadium record'}
        elif not kickoff or kickoff<=now:
            extra={'note':'No future kickoff'}
        elif kickoff>now+timedelta(days=15,hours=23):
            status='outside-forecast-range';extra={'note':'Outside forecast horizon'}
        elif venue_id not in GEO:
            status='venue-unmapped';extra={'note':'Venue coordinates unrecognised; no substitute home city used'}
        else:
            if venue_id not in cache:
                try:cache[venue_id]=fetcher(*GEO[venue_id])
                except (OSError,ValueError,TypeError,TimeoutError) as e:
                    errors.append(venue_id+': '+type(e).__name__+': '+str(e)[:80])
                    cache[venue_id]=None
            hourly=parse_hourly(cache[venue_id],kickoff) if cache[venue_id] else None
            if hourly:
                status='forecast' if roof in ('outdoors','open') else 'roof-unconfirmed'
                extra=hourly
                if roof not in ('outdoors','open'):extra['note']='Roof status unconfirmed; only conditional outdoor forecast'
                elif kickoff-now>timedelta(days=7):extra['note']='Long-range forecast; check near kickoff'
            else:extra={'note':'No kickoff-hour forecast returned'}
        game['weather']={'status':status,'stadium':venue,'stadiumId':venue_id,'roof':roof or 'unknown',
                         'source':'Open-Meteo','sourceUrl':'https://open-meteo.com/en/docs',
                         'probabilityWeight':0,'locationBasis':'Approximate stadium area, not a stadium sensor',
                         'retrievedAt':now.isoformat() if status in ('forecast','roof-unconfirmed') else None,**extra}
        game['weatherStatus']='Indoor / external conditions not applicable' if status=='indoor' else 'Weather '+status+' (no probability weight)'
        counts[status]=counts.get(status,0)+1
    return {'status':'partial' if errors else 'loaded' if any(x in counts for x in ('forecast','indoor','roof-unconfirmed')) else 'unavailable',
            'source':SOURCE,'scope':'Non-commercial venue-area forecast; no probability weight',
            'queriedVenues':len(cache),'statuses':counts,'errors':errors[:8],'asOf':now.isoformat()}
