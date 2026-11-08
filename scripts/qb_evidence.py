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

def depth_structure(payload):
    """Small schema-only diagnostic; never archive third-party response bodies."""
    root=payload.get("depthchart",payload.get("depthCharts")) if isinstance(payload,dict) else None
    summary={"rootType":type(root).__name__,"examples":[],"qbCandidates":[]}
    stack=[("depthchart",root,0)]
    count=0
    while stack and count<4000 and len(summary["qbCandidates"])<12:
        path,node,level=stack.pop()
        count+=1
        if isinstance(node,dict):
            keys=list(node)
            if level<=2 and len(summary["examples"])<12:
                summary["examples"].append({"path":path,"keys":keys[:14]})
            label=str(value(node.get("position") or node.get("abbreviation") or
                            node.get("name") or node.get("label"))).casefold()
            if label in ("qb","quarterback") or "quarterback" in (k.casefold() for k in keys):
                summary["qbCandidates"].append({
                    "path":path,"keys":keys[:14],"position":label[:30],
                    "rankKeys":[k for k in keys if "rank" in k.lower() or "depth" in k.lower()]})
            if level<12:
                for k,v in list(node.items())[:25]:
                    if isinstance(v,(list,dict)):
                        stack.append((path+"."+str(k),v,level+1))
        elif isinstance(node,list) and level<12:
            for i,v in enumerate(node[:25]):
                if isinstance(v,(list,dict)):
                    stack.append((path+"["+str(i)+"]",v,level+1))
    summary["nodesVisited"]=count
    # Target only the QB field; schema and ranking keys, never names/IDs.
    summary["qbAthleteShapes"]=[]
    charts=root if isinstance(root,list) else [root]
    for formation in charts:
        if not isinstance(formation,dict):continue
        positions=formation.get("positions") or {}
        if not isinstance(positions,dict):continue
        for key,group in positions.items():
            if str(key).casefold() not in ("qb","quarterback") or not isinstance(group,dict):continue
            athletes=group.get("athletes") or []
            summary["qbAthletesContainerType"]=type(athletes).__name__
            if isinstance(athletes,list):
                for player in athletes[:4]:
                    if not isinstance(player,dict):
                        summary["qbAthleteShapes"].append({"type":type(player).__name__})
                        continue
                    summary["qbAthleteShapes"].append({"keys":list(player)[:20],
                        "rankFields":{k:str(v)[:55] for k,v in player.items()
                            if any(term in k.casefold() for term in ("rank","depth","slot","order"))},
                        "athleteType":type(player.get("athlete")).__name__,
                        "athleteKeys":list(player.get("athlete") or {})[:15]
                            if isinstance(player.get("athlete"),dict) else []})
    return summary

def parse_depth(payload,observed_at):
    """Accept legacy depthCharts and 2026 depthchart shapes; require explicit QB1.

    Position and rank MUST both be present. Search nested group variations
    because ESPN's actual 2026 API uses the *singular* depthchart field and
    some public examples show an obsolete depthCharts list. Never promote the
    first listed athlete, rank-2 QB or any rank-1 non-QB.
    """
    t=aware(observed_at)
    if not t:raise ValueError("Timezone-aware observation required")
    if not isinstance(payload,dict):
        raise ValueError("Depth chart is not a JSON object")
    root=payload.get("depthchart",payload.get("depthCharts"))
    if root is None:raise ValueError("No depthchart or depthCharts field in ESPN response")
    found=[];nodes=[0]
    def is_qb_label(label):
        if isinstance(label,dict):
            label=label.get("abbreviation") or label.get("name") or label.get("displayName")
        return str(label or "").strip().casefold() in ("qb","quarterback")
    def visit(node,parent_qb=False,depth=0):
        nodes[0]+=1
        if depth>15 or nodes[0]>12000:return
        if isinstance(node,list):
            for row in node:visit(row,parent_qb,depth+1)
            return
        if not isinstance(node,dict):return
        qb_context=(parent_qb or is_qb_label(node.get("position")) or
                    is_qb_label(node.get("abbreviation")) or
                    is_qb_label(node.get("name") if "athlete" not in node else None))
        rank=node.get("rank",node.get("depthRank",node.get("depthOrder")))
        try:rank=int(rank)
        except (TypeError,ValueError):rank=None
        if qb_context and rank==1:
            athlete=node.get("athlete") or node.get("player") or node
            if isinstance(athlete,dict):
                name=value(athlete.get("displayName") or athlete.get("fullName") or
                           athlete.get("name"))
                if name:
                    found.append({"name":name,"espnAthleteId":str(athlete.get("id") or ""),
                                  "rank":1,"observedAt":t.isoformat(),
                                  "timestampBasis":"download-observation",
                                  "source":"ESPN team depthcharts (unofficial)"})
        for k,v in node.items():
            if isinstance(v,(list,dict)):
                visit(v,qb_context or is_qb_label(k),depth+1)
    visit(root)
    names={clean_name(x["name"]) for x in found}
    if not names:raise ValueError("ESPN depthchart has no explicit rank-1 QB")
    if len(names)>1:raise ValueError("ESPN depthchart contains conflicting rank-1 QBs")
    # ESPN's live 2026 chart provides position-specific athletes in an
    # ordered list but sometimes provides NO rank field at all. Preserve the
    # difference between an explicit rank-1 and a first-listed projection.
    # Do not silently promote any rank-2 entry or the first roster QB.
    ordered=[]
    visited=[0]
    def ordered_visit(node,parent_key="",depth=0):
        visited[0]+=1
        if depth>14 or visited[0]>14000:return
        if isinstance(node,list):
            for item in node:ordered_visit(item,parent_key,depth+1)
            return
        if not isinstance(node,dict):return
        labelled=(parent_key.casefold() in ("qb","quarterback") or
                  is_qb_label(node.get("position")) or
                  is_qb_label(node.get("abbreviation")))
        athletes=node.get("athletes")
        if labelled and isinstance(athletes,list) and athletes:
            # Explicit ranks are authoritative: if present but no QB1,
            # mark as unavailable rather than using list position.
            has_any_rank=any(isinstance(item,dict) and any(
                k in item for k in ("rank","depthRank","depthOrder","depth","order"))
                for item in athletes)
            if not has_any_rank:
                candidates=[]
                for item in athletes:
                    athlete=item.get("athlete") or item.get("player") or item if isinstance(item,dict) else {}
                    if not isinstance(athlete,dict):continue
                    name=value(athlete.get("displayName") or athlete.get("fullName") or athlete.get("name"))
                    if name:candidates.append((name,str(athlete.get("id") or "")))
                if candidates and len({clean_name(n) for n,_ in candidates})==len(candidates):
                    ordered.append(candidates[0])
        for key,val in node.items():
            if isinstance(val,(dict,list)):ordered_visit(val,key,depth+1)
    ordered_visit(root)
    # Conflicting explicit and ordered chart formations need review.
    all_names=names | {clean_name(n) for n,_ in ordered}
    if len(all_names)>1:raise ValueError("ESPN formations disagree on first-listed QB")
    if found:return {**found[0],"rankingBasis":"explicit-rank-1"}
    if len(all_names)!=1:raise ValueError("ESPN depthchart has no explicit rank-1 QB or unambiguous ordered QB list")
    name,athlete_id=ordered[0]
    return {"name":name,"espnAthleteId":athlete_id,
            "rank":None,"rankingBasis":"first-listed-no-explicit-rank",
            "observedAt":t.isoformat(),"timestampBasis":"download-observation",
            "source":"ESPN QB position ordering (unconfirmed, rank not explicit)"}

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

def parse_roster(payload,observed_at):
    """Roster membership for context only: NEVER assume the first QB will start."""
    t=aware(observed_at)
    if not t:raise ValueError("Timezone-aware roster observation required")
    if not isinstance(payload,dict) or not isinstance(payload.get("athletes"),list):
        raise ValueError("ESPN roster missing expected athletes array")
    found={}
    for group in payload["athletes"]:
        if not isinstance(group,dict):continue
        arr=group.get("items")
        arr=arr if isinstance(arr,list) else [group]
        group_pos=value(group.get("position")).upper()
        for athlete in arr:
            if not isinstance(athlete,dict):continue
            pos=value(athlete.get("position")).upper() or group_pos
            if pos not in ("QB","QUARTERBACK"):continue
            name=value(athlete.get("fullName") or athlete.get("displayName"))
            if not name:continue
            found[clean_name(name)]={"name":name,"espnAthleteId":str(athlete.get("id") or ""),
                "observedAt":t.isoformat(),"role":"roster QB, not verified starter",
                "source":"ESPN team roster (unofficial)"}
    if not found:raise ValueError("ESPN roster contains no labelled QB athletes")
    return sorted(found.values(),key=lambda x:x["name"])

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
    result={"team":team,"observedAt":now.isoformat(),"depth":None,"rosterQBs":[],
            "depthStatus":"unavailable","rosterStatus":"unavailable",
            "sourceUrls":{"depth":f"{BASE}/{id}/depthcharts",
                          "roster":f"{BASE}/{id}/roster"},
            "responseKeys":{},"errors":[]}
    for kind,url in result["sourceUrls"].items():
        try:
            payload=fetch_json(url,opener)
            result["responseKeys"][kind]=sorted(payload)[:18] if isinstance(payload,dict) else [type(payload).__name__]
            if kind=="depth":
                result["depthShape"]=depth_structure(payload)
                result["depth"]=parse_depth(payload,now)
                result["depthStatus"]="loaded"
            else:
                result["rosterQBs"]=parse_roster(payload,now)
                result["rosterStatus"]="loaded"
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
                teams[team]={"team":team,"depth":None,"rosterQBs":[],"depthStatus":"unavailable",
                             "rosterStatus":"unavailable","errors":[f"Unexpected fetch failure: {type(e).__name__}"]}
    depths=sum(x.get("depthStatus")=="loaded" for x in teams.values())
    rosters=sum(x.get("rosterStatus")=="loaded" for x in teams.values())
    metadata={"status":"loaded" if depths else "partial" if rosters else "unavailable",
       "source":"ESPN team-specific depthcharts and QB rosters (unofficial)",
       "observationTime":now.isoformat(),"selectedTeams":sorted(target),
       "attemptedTeams":len(target),"depthChartsLoaded":depths,
       "qbRostersLoaded":rosters,"rosterQBCandidates":sum(len(x.get("rosterQBs") or []) for x in teams.values()),
       "errors":{t:x["errors"] for t,x in teams.items() if x.get("errors")},
       "responseKeys":{t:x["responseKeys"] for t,x in teams.items() if x.get("responseKeys")},
       "depthShapeSamples":{t:teams[t]["depthShape"] for t in sorted(teams)[:3]
                            if teams[t].get("depthShape")},
       "notes":"ESPN's live depthchart has a QB athlete list that may omit rank fields. A first-listed player is an unconfirmed projection, NOT an explicitly ranked starter. nflverse and ESPN depth charts may share origin. QB rosters are context only, never a starter confirmation."}
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
        ranking_basis=ep.get("rankingBasis","explicit-rank-1" if ep.get("rank")==1 else "unavailable")
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
            q["projectionSource"]=("ESPN explicitly ranked QB1 (unconfirmed)" if
                ranking_basis=="explicit-rank-1" else
                "ESPN first-listed QB, no explicit rank (unconfirmed)")
            q["espnAthleteId"]=ep.get("espnAthleteId")
            q["label"]=("ESPN explicitly ranked QB1, not confirmed starting QB" if
                ranking_basis=="explicit-rank-1" else
                "ESPN first-listed QB, rank unspecified, NOT confirmed starter")
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
        qb_reports=[{"name":item.get("name"),"status":item.get("status"),
                     "reportDate":item.get("reportDate"),"source":item.get("source")}
                    for item in (media.get(side) or []) if isinstance(item,dict)
                    and str(item.get("position") or "").upper()=="QB"][:8]
        sides[side]={"team":team,"nflverseProjectedQB":nf_name,"nflverseAsOf":nf_time.isoformat() if nf_time else None,
            "nflverseFresh":nf_fresh,"espnProjectedQB":ep_name,
            "espnObservedAt":ep.get("observedAt"),"espnDepthStatus":record.get("depthStatus","unavailable"),
            "espnRosterStatus":record.get("rosterStatus","unavailable"),
            "espnRosterQBs":[x["name"] for x in (record.get("rosterQBs") or [])][:8],
            "datedQBInjuryReports":qb_reports,"sourceConflict":conflict,"sourcesAgree":aligned,
            "espnRankingBasis":ranking_basis,
            # nflverse charts are often derived from ESPN; two copies of
            # the same underlying chart are NOT independent confirmation.
            "independentConfirmation":False,
            "corroborationBasis":"ESPN-derived mirror comparison, not an independent starter source",
            "projectionUsed":("ESPN first-listed fallback" if ranking_basis=="first-listed-no-explicit-rank"
                              else "ESPN explicit rank-1 fallback") if use_espn else
                              "nflverse" if nf_fresh else "not verified",
            "evidenceStatus":"conflict" if conflict else "corroborated" if aligned else
                "ESPN-only projection" if use_espn else "missing evidence"}
    if media.get("status")=="loaded" and not media.get("retrievedAt"):
        media["retrievedAt"]=now.isoformat()
    game["qbIntelligence"]=current
    game["personnelDepthChart"]=chart
    game["supplementalInjuryWatch"]=media
    game["qbSourceEvidence"]={"status":meta.get("status","unavailable"),
        "observedAt":meta.get("observationTime"),"home":sides["home"],"away":sides["away"],
        "note":"ESPN and nflverse depth-chart snapshots may have the SAME originating provider. Agreement is a consistency check only, not independent starter confirmation. First-listed QB can lack an explicit ranking. Roster-only membership does not identify a starter."}
    return game
