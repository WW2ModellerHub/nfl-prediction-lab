"""Pregame NFL evidence reconciler and forecast confidence / wagering gates.

Quality is NOT a probability multiplier. It audits whether the *same*
published model probability has enough current, consistent pregame evidence
to be safely treated as checked. It never asserts an official starter from a
depth-chart rank, absence from the injury list, or a historical start count.

Evidence hierarchy:
  1. NFL weekly game-status fields as mirrored by nflverse, with row timestamp
  2. ESPN dated media injury observations (independently corroborating)
  3. nflverse/ESPN dated depth ranks (PROJECTIONS, not official starter)
  4. previous actual starting QBs (historical observation only)

Conflicting material data fails closed; source failures do not mean "healthy".
"""
from __future__ import annotations
from datetime import datetime,timezone,timedelta
from official_reports import norm,stamp

UNAVAILABLE={"OUT","DOUBTFUL","INJURED RESERVE","IR","OUT FOR SEASON","INACTIVE"}
UNCERTAIN={"QUESTIONABLE","DAY-TO-DAY","WEEK-TO-WEEK"}
CONFLICT_OUT={"OUT","INJURED RESERVE","IR","INACTIVE","OUT FOR SEASON"}

def normalized(v):
    s=str(v or "").upper().strip()
    if s in ("IR","INJURED RESERVE"):return "INJURED RESERVE"
    if s=="DOUBTFUL FOR GAME":return "DOUBTFUL"
    return s

def evaluate(game,now):
    now=stamp(now);kick=stamp(game.get("kickoff"))
    if not now or not kick:raise ValueError("Pregame verification requires timezone-aware dates")
    future=kick>now
    hours=(kick-now).total_seconds()/3600
    official=game.get("officialInjuryEvidence") or {}
    supplemental=game.get("supplementalInjuryWatch") or {}
    charts=game.get("qbSourceEvidence") or {}
    qbs=game.get("qbIntelligence") or {}
    team_checks=[];issues=[];blocking=[];needs_review=[]
    qb_auto_allowed=True
    for side in ("home","away"):
        name=game.get(side)
        q=qbs.get(side) or {}
        primary=q.get("primaryStarter") or {}
        established=primary.get("name")
        last=(q.get("lastGameLeader") or {}).get("name")
        projected=q.get("qb") if q.get("basis")=="depth_chart_projection" else None
        src=charts.get(side) or {}
        report=official.get(side) or {}
        qb_rows=report.get("qbs") or []
        media=supplemental.get(side) or []
        by_name={norm(r.get("name")):r for r in qb_rows if norm(r.get("name"))}
        qb_out=[r for r in qb_rows if normalized(r.get("gameStatus")) in UNAVAILABLE]
        qb_uncertain=[r for r in qb_rows if normalized(r.get("gameStatus")) in UNCERTAIN]
        absent={norm(r["name"]) for r in qb_out}
        # Compare only reports genuinely dated within the current game week.
        # Old media designations can be stale without contradicting a fresh
        # weekly report. Material disagreement is never silently reconciled.
        contradictions=[]
        for r in qb_rows:
            key=norm(r.get("name"));official_status=normalized(r.get("gameStatus"))
            at=stamp(r.get("reportDate"))
            if not at or not official_status:continue
            others=[m for m in media if norm(m.get("name"))==key
                    and str(m.get("position") or "").upper()=="QB"]
            for media_r in others:
                observed=stamp(media_r.get("reportDate"))
                if not observed or observed>now or observed>=kick or abs((at-observed).total_seconds())>72*3600:continue
                media_status=normalized(media_r.get("status"))
                if media_status in UNAVAILABLE|UNCERTAIN and (
                    (official_status in UNAVAILABLE)!=(media_status in UNAVAILABLE)
                    or (official_status in CONFLICT_OUT)!=(media_status in CONFLICT_OUT)
                    and media_status not in UNCERTAIN):
                    contradictions.append({"player":r.get("name"),
                        "officialReport":official_status,"mediaReport":media_status,
                        "officialAt":at.isoformat(),"mediaAt":observed.isoformat(),
                        "resolution":"Unresolved: QB adjustment suspended, inspect timestamped sources"})
        depth_conflict=bool(src.get("sourceConflict"))
        if depth_conflict:
            blocking.append(f"{name}: nflverse and ESPN projected starting QBs disagree")
            qb_auto_allowed=False
        if contradictions:
            blocking.append(f"{name}: QB game-status reports disagree")
            qb_auto_allowed=False
        projected_is_out=bool(projected and norm(projected) in absent)
        if projected_is_out:
            blocking.append(f"{name}: projected QB {projected} is listed unavailable on the weekly injury report")
            qb_auto_allowed=False
        primary_out=bool(established and norm(established) in absent)
        last_out=bool(last and norm(last) in absent)
        multiple_qb_out=len(absent)>=2
        if multiple_qb_out:
            blocking.append(f"{name}: {len(absent)} QBs designated unavailable, projected starter not officially confirmed")
        elif primary_out and (not projected or norm(established)!=norm(projected)):
            needs_review.append(f"{name}: established QB {established} unavailable; projected replacement not a confirmed starter")
        if qb_uncertain and (not projected or any(norm(r["name"])==norm(projected) for r in qb_uncertain)):
            needs_review.append(f"{name}: QB game status remains questionable")
        if future and hours<=96 and not projected:
            blocking.append(f"{name}: no current projected starting QB inside four days of kickoff")
            qb_auto_allowed=False
        nfl_fresh=bool(src.get("nflverseFresh"))
        # Source-agreement booleans alone must never clear a stale QB projection.
        nfl_at=stamp(src.get("nflverseAsOf"))
        espn_at=stamp(src.get("espnObservedAt"))
        near_kickoff=future and hours<=96
        nfl_limit=timedelta(days=7 if near_kickoff else 14)
        nfl_current=bool(nfl_fresh and nfl_at and timedelta(0)<=now-nfl_at<=nfl_limit)
        espn_current=bool(espn_at and timedelta(0)<=now-espn_at<=timedelta(hours=72))
        independent_agree=bool(src.get("sourcesAgree") and nfl_current and espn_current)
        if not independent_agree:
            needs_review.append(f"{name}: no agreement between two current dated projected-QB sources")
        if src.get("sourcesAgree") and not (nfl_current and espn_current):
            needs_review.append(f"{name}: projected QB evidence stale or missing a source timestamp")
        # Availability flags are not evidence: require actual dated rows observed
        # prospectively within the current week and near the current kickoff.
        source_rows=report.get("rows") or []
        report_dates=[stamp(r.get("reportDate")) for r in source_rows if isinstance(r,dict)]
        report_dates=[d for d in report_dates if d and d<=now and d<kick]
        newest_report=max(report_dates,default=None)
        report_limit=timedelta(hours=120 if near_kickoff else 264)
        report_current=bool(newest_report and timedelta(0)<=now-newest_report<=report_limit)
        report_ready=bool(report.get("isWeeklyReportAvailable") and
                          official.get("status") in ("loaded","snapshot-only") and report_current)
        if not report_ready:
            needs_review.append(f"{name}: no prospective same-week NFL injury report with current timestamps (missing, stale or not published)")
        if not projected:
            needs_review.append(f"{name}: starting QB is not projected by a current dated chart")
        if future and hours<=96 and not src.get("nflverseFresh") and not src.get("espnProjectedQB"):
            qb_auto_allowed=False
        team_checks.append({
            "team":name,"side":side,"establishedQB":established,
            "establishedObservedStarts":primary.get("verifiedStarts",0),
            "lastGameQB":last,"projectedQB":projected,
            "qbProjectionStatus":"two-sources-agree" if independent_agree else
                                "sources-disagree" if depth_conflict else
                                "one-source-only" if projected else "not-verified",
            "qbProjectionSource":src.get("projectionUsed","not-verified"),
            "nflverseQB":src.get("nflverseProjectedQB"),
            "espnQB":src.get("espnProjectedQB"),
            "nflverseChartAsOf":src.get("nflverseAsOf"),
            "espnObservedAt":src.get("espnObservedAt"),
            "qbSourceDatesCurrent":bool(nfl_current and espn_current),
            "officialReportLatestAt":newest_report.isoformat() if newest_report else None,
            "officialReportAgeHours":round((now-newest_report).total_seconds()/3600,1) if newest_report else None,
            "officialReportCurrent":report_current,
            "sourceConflict":depth_conflict,
            "officialReportForWeek":report_ready,
            "gameStatusEvidence":bool(qb_rows),
            "officialSourceType":official.get("sourceType","unavailable"),
            "reportTimestampBasis":(
                "download-observation" if any(r.get("timestampBasis")=="download-observation" for r in (report.get("rows") or []))
                else "row-updated" if report_ready else "unavailable"),
            "officialReportQBRows":[{"name":r.get("name"),"status":r.get("gameStatus"),
                                      "practice":r.get("practiceStatus"),"reportDate":r.get("reportDate")}
                                     for r in qb_rows[:10]],
            "reportedQBUnavailable":[{"name":r.get("name"),"status":r.get("gameStatus")}
                                      for r in qb_out[:10]],
            "reportedQBQuestionable":[r.get("name") for r in qb_uncertain[:10]],
            "establishedQBUnavailable":primary_out,
            "lastGameQBUnavailable":last_out,
            "projectedQBUnavailable":projected_is_out,
            "twoOrMoreQBsUnavailable":multiple_qb_out,
            "conflictingQBReports":contradictions,
            "starterOfficiallyConfirmed":False,
            "gameDayInactivesConfirmed":False,
            "note":"Projected QB is not an official starter confirmation; no inactive list feed is connected."})
    if not future:
        level="closed"
        status="not-a-pregame-forecast"
        risk="Game kickoff has passed; no new availability-based probabilities are issued"
    elif blocking:
        level="hold";status="manual-verification-required"
        risk="Material QB evidence is missing, contradictory or multiple quarterbacks are unavailable"
    elif needs_review:
        level="review";status="limited-source-verification"
        risk="Missing independent QB corroboration or weekly injury report"
    else:
        level="checked";status="sources-cross-checked-not-official-starter"
        risk="Projected QBs corroborated and injury source checked; starting QBs still not officially confirmed"
    # Preserve a numerical model prediction even while withholding any betting
    # or high-confidence claim. Never call a game 'high confidence' on odds alone.
    betting_ok=(level=="checked")
    all_issues=(blocking+needs_review+issues)[:24]
    return {
        "version":2,"level":level,"status":status,
        "bettingEligible":betting_ok,
        "highConfidenceEligible":betting_ok,
        "qbAutomationAllowed":qb_auto_allowed and not blocking,
        "timestamp":now.isoformat(),
        "kickoff":kick.isoformat(),"hoursToKickoff":round(hours,2),
        "gameId":game.get("id"),"officialMirrorAvailable":official.get("status") in ("loaded","snapshot-only"),
        "officialSourceType":official.get("sourceType","unavailable"),
        "officialReferenceURL":"https://www.nfl.com/injuries/",
        "teamChecks":team_checks,
        "blockingReasons":blocking[:12],
        "reviewReasons":needs_review[:12],
        "notes":issues[:12],
        "issues":all_issues,
        "riskSummary":risk,
        "starterConfirmation":"not-connected",
        "inactiveVerification":"not-connected",
        "note":"Quality gates do not change the win probability. Near kickoff, injury reports older than five days and nflverse QB chart observations older than seven days cannot pass source checks; ESPN chart observations must be within 72 hours. Dated same-week rows are required; flags alone cannot clear a forecast. NFL reports are mirrored via nflverse, and undated mirror rows are observed only from download time forward. 'Checked' never certifies a starter, inactive list, or profitable bet."}
