"""Pregame verification and official-report evidence safety."""
import sys,io,unittest
from datetime import datetime,timezone,timedelta
from pathlib import Path
from unittest.mock import patch
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/"scripts"))
from official_reports import parse,fetch,from_existing,attach,status
from pregame_verification import evaluate
from update import apply_personnel_forecasts

NOW=datetime(2026,11,8,12,tzinfo=timezone.utc)
K=(NOW+timedelta(days=1)).isoformat()
H=(NOW-timedelta(days=1)).isoformat()
COLUMNS="season,week,team,gsis_id,full_name,position,report_status,practice_status,date_modified,report_primary_injury\n"

def rows():
    return (COLUMNS+
      f"2026,9,BAL,001,Franchise QB,QB,Out,DNP,{H},Thumb\n"+
      f"2026,9,BAL,002,Backup QB,QB,Out,DNP,{H},Toe\n"+
      f"2026,9,BAL,003,Third QB,QB,,Full,{H},\n"+
      f"2026,9,JAX,111,Jacksonville WR,WR,Questionable,Limited,{H},Hamstring\n"+
      f"2026,8,BAL,001,Franchise QB,QB,Out,DNP,{H},Thumb\n"+
      f"2026,9,BAL,444,QB Practice Only,QB,,DNP,{H},Toe\n")

def game():
    return {'id':'2026_09_JAX_BAL','season':2026,'week':9,'kickoff':K,
       'home':'BAL','away':'JAX','homeProbability':.47,
       'qbIntelligence':{'home':{'qb':'Third QB','basis':'depth_chart_projection',
           'primaryStarter':{'name':'Franchise QB','verifiedStarts':5},
           'lastGameLeader':{'name':'Backup QB'}},
           'away':{'qb':'Jacksonville QB','basis':'depth_chart_projection',
                   'primaryStarter':{'name':'Jacksonville QB','verifiedStarts':8},
                   'lastGameLeader':{'name':'Jacksonville QB'}}},
       'qbSourceEvidence':{'home':{'nflverseFresh':True,
                   'nflverseProjectedQB':'Third QB','espnProjectedQB':'Third QB',
                   'sourcesAgree':True,'projectionUsed':'nflverse'},
                 'away':{'nflverseFresh':True,
                   'nflverseProjectedQB':'Jacksonville QB','espnProjectedQB':'Jacksonville QB',
                   'sourcesAgree':True,'projectionUsed':'nflverse'}},
       'supplementalInjuryWatch':{'status':'loaded','home':[],'away':[]}}

def merged():
    g=game()
    raw=parse(rows(),2026,NOW)
    attach(g,raw,{'status':'loaded','observedAt':NOW.isoformat()},NOW)
    return g

class OfficialReportTests(unittest.TestCase):
    def test_robust_report_fields_and_week_scope(self):
        x=parse(rows(),2026,NOW)
        self.assertEqual(len(x),6)
        self.assertEqual(next(y for y in x if y['name']=='Franchise QB' and y['week']==9)['gameStatus'],'OUT')
        self.assertIsNone(next(y for y in x if y['name']=='QB Practice Only')['gameStatus'])
        self.assertEqual(next(y for y in x if y['name']=='QB Practice Only')['practiceStatus'],'DNP')
        self.assertEqual(status('Did Not Practice'),None)
        self.assertEqual(status('IR'),'INJURED RESERVE')
        self.assertEqual(next(y for y in x if y['name']=='Franchise QB')['officialNFLDomain'],False)

    def test_malformed_csv_fails_closed(self):
        with self.assertRaises(ValueError):
            parse('season,name\n2026,Joe',2026,NOW)

    def test_future_report_is_not_used_for_pregame(self):
        after=(NOW+timedelta(hours=2)).isoformat()
        txt=COLUMNS+f"2026,9,BAL,01,Future QB,QB,Out,DNP,{after},Knee\n"
        self.assertFalse(parse(txt,2026,NOW))

    def test_undated_report_is_observed_now_not_earlier_or_invented_publication(self):
        txt=COLUMNS+"2026,9,BAL,01,Undated QB,QB,Out,DNP,,Knee\n"
        records=parse(txt,2026,NOW)
        self.assertEqual(records[0]['reportDate'],NOW.isoformat())
        self.assertIsNone(records[0]['sourceUpdatedAt'])
        self.assertEqual(records[0]['timestampBasis'],'download-observation')
        game_after=game()
        attach(game_after,records,{'status':'snapshot-only'},NOW)
        self.assertEqual(len(game_after['officialInjuryEvidence']['home']['qbs']),1)
        game_before=game()
        attach(game_before,records,{'status':'snapshot-only'},NOW-timedelta(hours=1))
        self.assertFalse(game_before['officialInjuryEvidence']['home']['qbs'])
        game_started=game()
        game_started['kickoff']=(NOW-timedelta(minutes=3)).isoformat()
        attach(game_started,records,{'status':'snapshot-only'},NOW)
        self.assertFalse(game_started['officialInjuryEvidence']['home']['qbs'])

    def test_fetch_counts_and_records_provenance(self):
        class Response:
            def __enter__(self):return self
            def __exit__(self,*args):pass
            def read(self,n):return rows().encode()[:n]
        def opener(req,timeout):return Response()
        actual,meta=fetch(2026,NOW,opener=opener)
        self.assertEqual(meta['status'],'loaded')
        self.assertEqual(meta['sourceType'],'official-report-derived-mirror')
        self.assertEqual(meta['records'],6)
        self.assertFalse(any(x['starterConfirmed'] for x in actual))

    def test_existing_full_mode_reuse_preserves_original_row_timestamp(self):
        old={'season':2026,'week':9,'team':'BAL','name':'Franchise QB','id':'01',
             'position':'QB','reportStatus':'Out','practiceStatus':'DNP',
             'asOf':datetime.fromisoformat(H),'timestampBasis':'row-updated','injury':'Thumb'}
        rec,meta=from_existing([old],2026,NOW)
        self.assertEqual(rec[0]['gameStatus'],'OUT')
        self.assertEqual(rec[0]['reportDate'],H)
        self.assertEqual(meta['gameStatuses'],1)

    def test_snapshot_mirror_counts_game_status_without_claiming_source_modification_time(self):
        row={'season':2026,'week':9,'team':'BAL','name':'Franchise QB','id':'01',
             'position':'QB','reportStatus':'Out','practiceStatus':'DNP',
             'asOf':NOW,'timestampBasis':'download-observation','injury':'Thumb'}
        entries,meta=from_existing([row],2026,NOW)
        self.assertEqual(meta['status'],'snapshot-only')
        self.assertEqual(meta['gameStatuses'],1)
        self.assertEqual(meta['dated'],0)
        self.assertEqual(meta['sourceTimestampedGameStatuses'],0)
        self.assertIsNone(entries[0]['sourceUpdatedAt'])
        self.assertEqual(entries[0]['reportDate'],NOW.isoformat())

    def test_game_week_and_kickoff_cannot_leak(self):
        g=merged()
        self.assertEqual(g['officialInjuryEvidence']['home']['qualifiedQBOut'][0]['name'],'Backup QB')
        self.assertEqual(len(g['officialInjuryEvidence']['home']['qualifiedQBOut']),2)
        self.assertFalse(any(r['name']=='Franchise QB' and r['week']==8
                       for r in g['officialInjuryEvidence']['home']['rows']))
        self.assertEqual(g['officialInjuryEvidence']['away']['qbs'],[])
        self.assertTrue(g['officialInjuryEvidence']['home']['isWeeklyReportAvailable'])

class VerificationTests(unittest.TestCase):
    def test_two_official_reported_qbs_unavailable_requires_hold(self):
        g=merged()
        q=evaluate(g,NOW)
        self.assertEqual(q['level'],'hold')
        self.assertFalse(q['bettingEligible'])
        self.assertFalse(q['highConfidenceEligible'])
        self.assertTrue(q['teamChecks'][0]['twoOrMoreQBsUnavailable'])
        self.assertTrue(q['teamChecks'][0]['establishedQBUnavailable'])
        self.assertTrue(q['teamChecks'][0]['lastGameQBUnavailable'])
        self.assertFalse(q['teamChecks'][0]['starterOfficiallyConfirmed'])
        self.assertTrue(any('2 QBs' in s for s in q['blockingReasons']))

    def test_projected_qb_reported_out_holds_everything(self):
        g=merged()
        g['qbIntelligence']['home']['qb']='Franchise QB'
        self.assertEqual(evaluate(g,NOW)['teamChecks'][0]['projectedQBUnavailable'],True)
        self.assertEqual(evaluate(g,NOW)['level'],'hold')

    def test_duplicate_media_disagrees_with_official_status(self):
        g=merged()
        g['supplementalInjuryWatch']['home']=[{
           'name':'Backup QB','position':'QB','status':'Questionable',
           'reportDate':H,'source':'ESPN media injury list'}]
        v=evaluate(g,NOW)
        self.assertEqual(v['level'],'hold')
        self.assertEqual(v['qbAutomationAllowed'],False)
        self.assertEqual(v['teamChecks'][0]['conflictingQBReports'][0]['player'],'Backup QB')

    def test_old_media_does_not_overturn_new_official_report(self):
        g=merged()
        g['supplementalInjuryWatch']['home']=[{
           'name':'Backup QB','position':'QB','status':'Questionable',
           'reportDate':(NOW-timedelta(days=8)).isoformat(),
           'source':'ESPN media injury list'}]
        v=evaluate(g,NOW)
        self.assertFalse(v['teamChecks'][0]['conflictingQBReports'])

    def test_missing_weekly_report_is_review_not_healthy(self):
        g=game()
        g['officialInjuryEvidence']={'status':'unavailable','home':{},'away':{}}
        v=evaluate(g,NOW)
        self.assertEqual(v['level'],'review')
        self.assertFalse(v['bettingEligible'])
        self.assertTrue(any('no prospective same-week' in x for x in v['reviewReasons']))

    def test_future_week_without_report_is_never_marked_checked(self):
        g=game()
        g['kickoff']=(NOW+timedelta(days=10)).isoformat()
        g['officialInjuryEvidence']={'status':'unavailable','home':{},'away':{}}
        result=evaluate(g,NOW)
        self.assertEqual(result['level'],'review')
        self.assertFalse(result['bettingEligible'])

    def test_snapshot_observed_this_week_is_prospective_evidence(self):
        g=game()
        txt=COLUMNS+f"2026,9,BAL,01,Franchise QB,QB,Out,DNP,,Thumb\n"
        attach(g,parse(txt,2026,NOW),{'status':'snapshot-only'},NOW)
        q=evaluate(g,NOW)
        h=q['teamChecks'][0]
        self.assertTrue(h['officialReportForWeek'])
        self.assertEqual(h['reportTimestampBasis'],'download-observation')
        self.assertTrue(h['establishedQBUnavailable'])
        self.assertFalse(h['starterOfficiallyConfirmed'])

    def test_checked_sources_are_not_falsely_confirmed_starters(self):
        g=game()
        reports={
            'status':'loaded',
            'home':{'isWeeklyReportAvailable':True,'qbs':[]},
            'away':{'isWeeklyReportAvailable':True,'qbs':[]}}
        g['officialInjuryEvidence']=reports
        v=evaluate(g,NOW)
        self.assertEqual(v['level'],'checked')
        self.assertTrue(v['bettingEligible'])
        self.assertEqual(v['starterConfirmation'],'not-connected')
        self.assertFalse(v['teamChecks'][0]['starterOfficiallyConfirmed'])
        self.assertEqual(g['homeProbability'],.47)

    def test_no_projection_near_kickoff_fails_closed(self):
        g=game()
        g['qbIntelligence']['home']['qb']=None
        g['qbSourceEvidence']['home'].update(nflverseFresh=False,espnProjectedQB=None)
        self.assertEqual(evaluate(g,NOW)['level'],'hold')

    def test_source_conflict_and_no_betting_in_preliminary(self):
        g=game()
        g['qbSourceEvidence']['home']['sourceConflict']=True
        self.assertEqual(evaluate(g,NOW)['level'],'hold')

    def test_post_kickoff_not_treated_as_pregame(self):
        g=game()
        g['kickoff']=(NOW-timedelta(minutes=1)).isoformat()
        q=evaluate(g,NOW)
        self.assertEqual(q['level'],'closed')
        self.assertFalse(q['bettingEligible'])

    def test_blocked_quality_suppresses_qb_overlay_without_touching_baseline(self):
        from unittest.mock import patch
        g=game()
        g.update(id='fixture',predHome=24,predAway=22,predMargin=2,predTotal=46,model='baseline')
        g['forecastQuality']={'level':'hold','qbAutomationAllowed':False,
                              'bettingEligible':False,'highConfidenceEligible':False}
        candidate={'affectsPrediction':True,'homeProbability':.77,'homeDelta':.3,
                   'marginDelta':8.,'factors':[{'kind':'qb-stat'}]}
        replacement={'affectsPrediction':True,'homeProbability':.1,'homeDelta':-.37,
                     'marginDelta':-12.,'factors':[{'kind':'qb-replacement'}],
                     'scenarios':[]}
        none={'affectsPrediction':False,'homeProbability':.47,
              'marginDelta':0,'factors':[]}
        with patch('update.qb_efficiency_preview',return_value=candidate), \
             patch('update.assess_replacement',return_value=replacement), \
             patch('update.assess_personnel',return_value=none):
            apply_personnel_forecasts({'nextGames':[g]}, {},NOW,'full',[])
        self.assertAlmostEqual(g['homeProbability'],.47)
        self.assertEqual(g['confidence'],'Unverified')
        self.assertFalse(g['personnelScenario']['affectsPrediction'])
        self.assertFalse(g['qbReplacement']['affectsPrediction'])

    def test_immutable_revision_captures_quality_gate_and_snapshot_time_basis(self):
        from forecast_revisions import snapshot
        g=game()
        txt=COLUMNS+f"2026,9,BAL,001,Franchise QB,QB,Out,DNP,,Thumb\n"
        attach(g,parse(txt,2026,NOW),{'status':'snapshot-only'},NOW)
        g['forecastQuality']=evaluate(g,NOW)
        record=snapshot(g,NOW,'refresh','model-generated')
        self.assertEqual(record['verificationLevel'],g['forecastQuality']['level'])
        self.assertEqual(record['reportTimestampBasis']['home'],'download-observation')
        self.assertEqual(record['reportMirrorStatus'],'snapshot-only')
        self.assertEqual(record['verificationAt'],NOW.isoformat())
        self.assertTrue(record['verificationIssues'])
        self.assertEqual(record['homeProbability'],.47)


if __name__=='__main__':unittest.main()
