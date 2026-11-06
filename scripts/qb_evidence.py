"""Collect secondary, timestamped NFL QB evidence from ESPN team feeds.

ESPN Site API is unofficial. Rank 1 on its depth chart is a projection,
not a confirmed starter; a downloaded snapshot is observed AT retrieval,
not on the day ESPN last changed it. Undated injury designations are never
backdated or treated as official game-day inactives.

The nflverse dated depth chart remains primary when fresh. Disagreements
are explicit and never silently turned into a confirmed starter.
"""
from __future__ import annotations
import json
import urllib.request
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone, timedelta

BASE="https://site.api.espn.com/apis/site/v2/sports/football/nfl/teams"
TEAM_IDS={"ARI":22,"ATL":1,"BAL":33,"BUF":2,"CAR":29,"CHI":3,
"CIN":4,"CLE":5,"DAL":6,"DEN":7,"DET":8,"GB":9,"HOU":34,
"IND":11,"JAX":30,"KC":12,"LV":13,"LAC":24,"LA":14,"LAR":14,
"MIA":15,"MIN":16,"NE":17,"NO":18,"NYG":19,"NYJ":20,
"PHI":21,"PIT":23,"SF":25,"SEA":26,"TB":27,"TEN":10,"WAS":28,"WSH":28}
KNOWN_STATUS={"OUT","QUESTIONABLE","DOUBTFUL","INJURED RESERVE","IR",
              "OUT FOR SEASON","INACTIVE","WEEK-TO-WEEK","DAY-TO-DAY"}
MAX_BYTES=3_000_000

def aware(t):
    try:
        d=t if isinstance(t,datetime) else datetime.fromisoformat(str(t).replace("Z","+00:00"))
        return d.astimezone(timezone.utc) if d.tzinfo else None
    except (ValueError,TypeError,OverflowError):return None

def value(v):
    if isinstance(v,dict):
        return str(v.get("abbreviation") or v.get("displayName") or
                   v.get("name") or v.get("description") or "").strip()
    return str(v or "").strip()

def clean_name(v):
    return "".join(c for c in str(v or "").casefold() if c.isalnum())

def parse_depth(payload,observed_at):
    """Require an explicitly first-ranked QB; no inference from list order."""
    t=aware(observed_at)
    if not t:raise ValueError("Timezone-aware observation required")
    if not isinstance(payload,dict) or not isinstance(payload.get("depthCharts"),list):
        raise ValueError("ESPN depth chart missing expected depthCharts array")
    candidates=[]
    for chart in payload["depthCharts"]:
        if not isinstance(chart,dict):continue
        positions=chart.get("positions")
        if isinstance(positions,dict):
            groups=list(positions.items())
        elif isinstance(positions,list):
            groups=[("",p) for p in positions]
        else:continue
        for key,p in groups:
            if not isinstance(p,dict):continue
            position=p.get("position") or {}
            abbreviation=value(position.get("abbreviation") if isinstance(position,dict) else "")
            if str(key).lower() not in ("qb","quarterback") and abbreviation.upper()!="QB":
                continue
            for item in p.get("athletes") or []:
                if not isinstance(item,dict):continue
                athlete=item.get("athlete") or {}
                if not isinstance(athlete,dict):continue
                try:rank=int(item.get("rank"))
                except (TypeError,ValueError):continue
                name=value(athlete.get("displayName") or athlete.get("fullName"))
                if name and rank==1:
                    candidates.append({"name":name,"espnAthleteId":str(athlete.get("id") or ""),
                       "rank":rank,"observedAt":t.isoformat(),
                       "timestampBasis":"download-observation",
                       "source":"ESPN team depthcharts (unofficial)"})
    if not candidates:raise ValueError("No explicit rank-1 QB in ESPN depth-chart response")
    if len({clean_name(x["name"]) for x in candidates})>1:
        raise ValueError("Conflicting rank-1 quarterbacks within ESPN depth-chart feed")
    return candidates[0]

def parse_injuries(payload,observed_at):
    """Only athlete-specific, independently dated records can drive forecasts."""
    now=aware(observed_at)
    if not now:raise ValueError("Timezone-aware observation required")
    if not isinstance(payload,dict) or not isinstance(payload.get("injuries"),list):
        raise ValueError("ESPN team injuries missing expected injuries array")
    rows=[]
    for item in payload["injuries"]:
        if not isinstance(item,dict):continue
        nested=item.get("injuries")
        items=nested if isinstance(nested,list) else [item]
        for rec in items:
            if not isinstance(rec,dict):continue
            athlete=rec.get("athlete") or {}
            if not isinstance(athlete,dict):continue
            name=value(athlete.get("fullName") or athlete.get("displayName"))
            position=value(athlete.get("position")).upper()
            status=value(rec.get("status")).upper()
            at=aware(rec.get("date") or rec.get("lastUpdated"))
            if not name or not position or status not in KNOWN_STATUS or not at:
                continue
            if at>now+timedelta(minutes=5) or now-at>timedelta(days=35):continue
            rows.append({"name":name,"position":position,"status":status,
               "reportDate":at.isoformat(),"source":"ESPN team injuries (unofficial)",
               "observedAt":now.isoformat(),"officialGameStatus":False,
               "starterConfirmed":False})
    latest={}
    for r in rows:
        key=(clean_name(r["name"]),r["position"])
        if key not in latest or latest[key]["reportDate"]<r["reportDate"]:
            latest[key]=r
    return list(latest.values())

def fetch_json(url,opener=None):
    """Fixed endpoint on ESPN; limit size and fail closed when blocked."""
    req=urllib.request.Request(url,headers={
        "User-Agent":"NFLPredictionLab/2.6 (personal research)",
        "Accept":"application/json"})
    open_call=opener or urllib.request.urlopen
    with open_call(req,timeout=9) as response:
        raw=response.read(MAX_BYTES+1)
    if len(raw)>MAX_BYTES:raise ValueError("Feed exceeds bounded response size")
    return json.loads(raw.decode("utf8"))

def _load_team(team,now,opener=None):
    id=TEAM_IDS[team]
    result={"team":team,"observedAt":now.isoformat(),"depth":None,"injuries":[],
            "depthStatus":"unavailable","injuryStatus":"unavailable",
            "sourceUrls":{"depth":f"{BASE}/{id}/depthcharts",
                          "injuries":f"{BASE}/{id}/injuries"},
            "errors":[]}
    for kind,url in result["sourceUrls"].items():
        try:
            payload=fetch_json(url,opener)
            if kind=="depth":
                result["depth"]=parse_depth(payload,now)
                result["depthStatus"]="loaded"
            else:
                result["injuries"]=parse_injuries(payload,now)
                result["injuryStatus"]="loaded" if result["injuries"] else "no-dated-records"
        except (OSError,TimeoutError,UnicodeError,ValueError,TypeError,KeyError) as e:
            result["errors"].append(f"{kind}: {type(e).__name__}: {str(e)[:145]}")
    return result

def gather(games,now=None,opener=None,max_workers=5):
    """Fetch only teams with games within seven days, never scan all 32 by default."""
    now=aware(now or datetime.now(timezone.utc))
    if not now:raise ValueError("Timezone-aware timestamp required")
    target=set()
    for g in games:
        kickoff=aware(g.get("kickoff"))
        if kickoff and now<kickoff<=now+timedelta(days=7):
            for side in ("home","away"):
                team=g.get(side)
                if team in TEAM_IDS:target.add(team)
    teams={}
    with ThreadPoolExecutor(max_workers=max(1,min(int(max_workers),6))) as pool:
        jobs={pool.submit(_load_team,team,now,opener):team for team in sorted(target)}
        for future in as_completed(jobs):
            team=jobs[future]
            try:teams[team]=future.result()
            except Exception as e:
                teams[team]={"team":team,"depth":None,"injuries":[],"depthStatus":"unavailable",
                             "injuryStatus":"unavailable","errors":[f"Unexpected fetch failure: {type(e).__name__}"]}
    depths=sum(x.get("depthStatus")=="loaded" for x in teams.values())
    injuries=sum(x.get("injuryStatus")=="loaded" for x in teams.values())
    metadata={"status":"loaded" if depths else "partial" if injuries else "unavailable",
       "source":"ESPN team-specific depthcharts and injuries (unofficial)",
       "observationTime":now.isoformat(),"selectedTeams":sorted(target),
       "attemptedTeams":len(target),"depthChartsLoaded":depths,
       "datedInjuryTeams":injuries,
       "errors":{t:x["errors"] for t,x in teams.items() if x.get("errors")},
       "notes":"ESPN is an unofficial best-effort second source. Rank 1 is not a confirmed starter. Download observation is not ESPN's update time. Only explicitly dated statuses qualify as injury records."}
    return teams,metadata

def attach(game,records,meta,now):
    """Add observed ESPN evidence to a forthcoming game without inventing a starter.

    A fresh nflverse projected QB remains primary. Where nflverse projection is
    absent/stale, an ESPN rank-1 QB can fill the *projected-only* slot. This
    never asserts starter confirmation, and mismatch between two fresh
    sources leaves original projection unchanged and flags the disagreement.
    """
    now=aware(now)
    current=(game.get("qbIntelligence") or {})
    chart=(game.get("personnelDepthChart") or {})
    media=game.get("supplementalInjuryWatch") or {}
    sides={}
    for side in ("home","away"):
        team=game.get(side)
        record=records.get(team) or {}
        q=current.get(side) or {}
        nf_name=q.get("qb") if q.get("basis")=="depth_chart_projection" else None
        nf_time=aware((chart.get(side) or {}).get("asOf"))
        nf_fresh=bool(nf_name and nf_time and timedelta(0)<=now-nf_time<=timedelta(days=14))
        ep=record.get("depth") or {}
        ep_name=ep.get("name")
        conflict=bool(nf_fresh and ep_name and clean_name(nf_name)!=clean_name(ep_name))
        aligned=bool(nf_fresh and ep_name and clean_name(nf_name)==clean_name(ep_name))
        use_espn=bool(ep_name and not nf_fresh)
        if conflict:
            game["qbResearch"]={**(game.get("qbResearch") or {}),"eligible":False,
                "reason":"Two independent fresh projected QB sources disagree; QB statistical preview withheld"}
        if use_espn:
            prev=q.get("lastGameLeader") or {}
            previous_matches=clean_name(prev.get("name"))==clean_name(ep_name)
            q["qb"]=ep_name
            q["basis"]="depth_chart_projection"
            q["confirmedStarter"]=False
            q["projectionSource"]="ESPN depth rank 1, observed at download (unconfirmed)"
            q["espnAthleteId"]=ep.get("espnAthleteId")
            q["label"]="ESPN depth-chart rank 1, not confirmed starting QB"
            # ESPN athlete IDs and nflverse GSIS IDs must never be equated.
            # Recompute no player stats using the new ESPN identity.
            q["sample"]=q.get("previousQBsample") if previous_matches else None
            q["playerId"]=prev.get("id") if previous_matches else None
            q["starterChangeWatch"]=bool(prev and not previous_matches)
            current[side]=q
            if not isinstance(chart.get(side),dict):chart[side]={}
            chart[side]["asOf"]=ep["observedAt"]
            chart[side]["source"]=ep["source"]
            chart[side]["timestampBasis"]="download-observation"
            game["qbResearch"]={**(game.get("qbResearch") or {}),"eligible":False,
                "reason":"ESPN fallback changed projected QB after historical QB feature snapshot; statistical QB preview withheld"}
        new_media=record.get("injuries") or []
        existing=(media.get(side) or [])
        merged={}
        for item in existing+new_media:
            if not isinstance(item,dict):continue
            name=clean_name(item.get("name"))
            at=aware(item.get("reportDate"))
            if not name or not at:continue
            if name not in merged or merged[name]["reportDate"]<at.isoformat():
                merged[name]=item
        if new_media:
            media[side]=sorted(merged.values(),key=lambda v:v.get("reportDate",""),reverse=True)[:24]
            media["status"]="loaded"
        sides[side]={"team":team,"nflverseProjectedQB":nf_name,"nflverseAsOf":nf_time.isoformat() if nf_time else None,
            "nflverseFresh":nf_fresh,"espnProjectedQB":ep_name,
            "espnObservedAt":ep.get("observedAt"),"espnDepthStatus":record.get("depthStatus","unavailable"),
            "espnInjuryStatus":record.get("injuryStatus","unavailable"),
            "espnDatedInjuries":len(new_media),"sourceConflict":conflict,"sourcesAgree":aligned,
            "projectionUsed":"ESPN rank-1 fallback" if use_espn else "nflverse" if nf_fresh else "not verified",
            "evidenceStatus":"conflict" if conflict else "corroborated" if aligned else
                "ESPN-only projection" if use_espn else "missing evidence"}
    if media.get("status")=="loaded" and not media.get("retrievedAt"):
        media["retrievedAt"]=now.isoformat()
    game["qbIntelligence"]=current
    game["personnelDepthChart"]=chart
    game["supplementalInjuryWatch"]=media
    game["qbSourceEvidence"]={"status":meta.get("status","unavailable"),
        "observedAt":meta.get("observationTime"),"home":sides["home"],"away":sides["away"],
        "note":"Independent sources may disagree. Depth rank 1 is a projection, not official confirmation."}
    return game
