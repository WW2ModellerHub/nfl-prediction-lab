"""Leakage-safe quarterback replacement scenarios and empirical rookie priors."""
import math
import sys
import unittest
from datetime import datetime,timezone,timedelta
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
from qb_replacement import evaluate,historical_screen
from qb_injuries import QBEngine

NOW=datetime(2026,11,5,12,tzinfo=timezone.utc)
def item(status='Out',at=NOW,name="Star QB"):
    return {'name':name,'position':'QB','status':status,'reportDate':at.isoformat()}
def matchup():
    return {'id':'2026_09_TEAMA_TEAMB','season':2026,'week':9,
            'home':'BAL','away':'JAX','homeProbability':.53,
            'kickoff':(NOW+timedelta(days=1)).isoformat(),
            'personnelDepthChart':{'home':{'asOf':(NOW-timedelta(days=1)).isoformat()},
                                   'away':{'asOf':(NOW-timedelta(days=1)).isoformat()}},
            'qbIntelligence':{'firstStartPrior':{'status':'observed','starts':60,
                                                 'epaPerDropback':-.17,'stddev':.34},
                'home':{'team':'BAL','qb':'New QB','basis':'depth_chart_projection',
                        'playerId':'rookie','lastGameLeader':{
                          'name':'Star QB','id':'star','date':(NOW-timedelta(days=6)).isoformat(),
                          'season':2026},
                        'previousQBsample':{'dropbacks':350,'games':8,'epaPerDropback':.30},
                        'sample':None},
                'away':{'team':'JAX','qb':'Away QB','basis':'depth_chart_projection'}},
            'supplementalInjuryWatch':{'status':'loaded','retrievedAt':NOW.isoformat(),
                                       'home':[item()],'away':[]}}

class QBReplacementTests(unittest.TestCase):
    def test_elite_out_and_first_start_changes_prob_without_fixed_penalty(self):
        g=matchup()
        original=g['homeProbability']
        r=evaluate(g,NOW)
        self.assertTrue(r['affectsPrediction'])
        self.assertLess(r['homeProbability'],.28) # a very large conditional gap, not a hard-coded 78%
        self.assertLessEqual(abs(r['marginDelta']),13)
        self.assertEqual(r['scenarios'][0]['firstStartObservations'],60)
        self.assertEqual(r['scenarios'][0]['replacementQBdropbacks'],0)
        self.assertEqual(r['factors'][0]['kind'],'qb-replacement')
        self.assertFalse(r['validated'])
        self.assertEqual(g['homeProbability'],original)
        self.assertGreater(r['homeProbability'],0)

    def test_projection_without_dated_out_is_conditional_only(self):
        g=matchup()
        g['supplementalInjuryWatch']['home']=[]
        r=evaluate(g,NOW)
        self.assertFalse(r['affectsPrediction'])
        self.assertEqual(r['homeProbability'],.53)
        self.assertEqual(r['status'],'projection-scenarios-only')
        self.assertLess(r['scenarios'][0]['conditionalHomeProbability'],.28)
        self.assertIn('sensitivity',r['scenarios'][0]['intervalType'])
        self.assertEqual(r['marginDelta'],0)

    def test_questionable_not_assumed_out(self):
        g=matchup()
        g['supplementalInjuryWatch']['home']=[item('Questionable')]
        r=evaluate(g,NOW)
        self.assertFalse(r['affectsPrediction'])
        self.assertTrue(any('questionable' in w for w in r['warnings']))

    def test_stale_and_future_report_never_used(self):
        for t in (NOW-timedelta(days=9),NOW+timedelta(minutes=2)):
            g=matchup()
            g['supplementalInjuryWatch']['home']=[item(at=t)]
            self.assertFalse(evaluate(g,NOW)['affectsPrediction'])

    def test_stale_chart_and_future_fixture_never_adjusted(self):
        g=matchup()
        g['personnelDepthChart']['home']['asOf']=(NOW-timedelta(days=40)).isoformat()
        self.assertFalse(evaluate(g,NOW)['affectsPrediction'])
        g=matchup()
        g['kickoff']=(NOW+timedelta(days=15)).isoformat()
        self.assertEqual(evaluate(g,NOW)['status'],'future-week-monitor')
        g=matchup()
        self.assertFalse(evaluate(g,NOW+timedelta(days=2))['affectsPrediction'])

    def test_low_population_blocks_unknown_replacement_value(self):
        g=matchup()
        g['qbIntelligence']['firstStartPrior']['starts']=19
        self.assertFalse(evaluate(g,NOW)['affectsPrediction'])

    def test_known_stronger_replacement_can_improve_team(self):
        g=matchup()
        g['qbIntelligence']['home']['sample']={'dropbacks':250,'epaPerDropback':.28}
        g['qbIntelligence']['home']['previousQBsample']['epaPerDropback']=-.25
        r=evaluate(g,NOW)
        self.assertGreater(r['homeProbability'],.53)
        self.assertGreater(r['marginDelta'],0)  # better home QB raises expected home scoring margin

    def test_report_for_other_qb_does_not_trigger(self):
        g=matchup()
        g['supplementalInjuryWatch']['home']=[item(name="Different QB")]
        self.assertFalse(evaluate(g,NOW)['affectsPrediction'])

    def test_no_qb_identified_or_previous_starter_too_old(self):
        g=matchup()
        g['qbIntelligence']['home']['lastGameLeader']['date']=(NOW-timedelta(days=60)).isoformat()
        self.assertFalse(evaluate(g,NOW)['affectsPrediction'])
        g=matchup();g['qbIntelligence']['home']['qb']='Star QB'
        self.assertFalse(evaluate(g,NOW)['affectsPrediction'])

    def test_historical_research_does_not_use_current_season(self):
        older=[{'season':2025,'week':3,'y':1,'baseline':.55,
                'conditional':.62,'eligible':True}]
        recent=[{'season':2026,'week':9,'y':0,'baseline':.9,
                 'conditional':.1,'eligible':True}]
        self.assertEqual(historical_screen(older+recent,2026),
                         historical_screen(older,2026))
        self.assertFalse(historical_screen(older+recent,2026)['productionApproved'])

    def test_first_start_prior_built_only_after_completed_game_update(self):
        engine=QBEngine({'g':{'BAL':{'p01':{'id':'p01','name':'New QB','team':'BAL',
                   'dropbacks':26,'epaPlays':26,'epaTotal':-5.2,
                   'attempts':22,'completions':12,'passYards':210,'sacks':1,
                   'hitsOrSacks':2,'interceptions':1,'cpoeTotal':0,'cpoePlays':0}}}})
        g={'id':'g','home':'BAL','away':'JAX','season':2025,'kickoff':NOW,
           'home_qb_id':'p01','home_qb_name':'New QB','away_qb_id':'','away_qb_name':''}
        future={**g,'id':'later','kickoff':NOW+timedelta(days=8),'season':2025}
        self.assertEqual(engine.first_start_prior(g)['starts'],0)
        engine.update(g)
        self.assertEqual(engine.first_start_prior(g)['starts'],0)
        self.assertEqual(engine.first_start_prior(future)['starts'],1)
        self.assertAlmostEqual(engine.first_start_history[0]['epaPerDropback'],-.2)


    def test_reports_missing_replacement_for_recorded_out_qb(self):
        g=matchup()
        g['qbIntelligence']['home']['basis']='unknown'
        g['qbIntelligence']['home']['qb']=None
        result=evaluate(g,NOW)
        self.assertFalse(result['affectsPrediction'])
        self.assertEqual(result['status'],'reported-absence-unpriced')
        self.assertEqual(result['coverageStatus'],'reported-absence-unpriced')
        home=next(t for t in result['teamChecks'] if t['side']=='home')
        self.assertEqual(home['lastRecordedQB'],'Star QB')
        self.assertEqual(home['injuryReportStatus'],'OUT')
        self.assertIsNone(home['projectedQB'])
        self.assertTrue(any('replacement' in x.lower() for x in home['missingReasons']))

    def test_unverified_projection_identifies_missing_report_not_zero_value(self):
        g=matchup()
        g['supplementalInjuryWatch']['home']=[]
        result=evaluate(g,NOW)
        self.assertFalse(result['affectsPrediction'])
        self.assertEqual(result['coverageStatus'],'qb-change-evidence')
        home=next(t for t in result['teamChecks'] if t['side']=='home')
        self.assertEqual(home['state'],'projection-only')
        self.assertTrue(home['differentQBProjected'])
        self.assertTrue(any('OUT/DOUBTFUL' in s for s in home['missingReasons']))
        self.assertEqual(result['scenarios'][0]['mode'],'scenario-only')

    def test_no_change_is_reported_for_specific_team_and_missing_others(self):
        g=matchup()
        g['supplementalInjuryWatch']['home']=[]
        g['qbIntelligence']['home']['qb']='Star QB'
        result=evaluate(g,NOW)
        home=next(t for t in result['teamChecks'] if t['side']=='home')
        away=next(t for t in result['teamChecks'] if t['side']=='away')
        self.assertEqual(home['state'],'no-change')
        self.assertEqual(away['state'],'missing-data')
        self.assertFalse(result['affectsPrediction'])
        self.assertEqual(result['coverageStatus'],'missing-data')

    def test_out_report_with_same_projected_qb_is_unpriced_contradiction(self):
        g=matchup()
        g['qbIntelligence']['home']['qb']='Star QB'
        result=evaluate(g,NOW)
        home=next(x for x in result['teamChecks'] if x['side']=='home')
        self.assertEqual(home['state'],'reported-absence-unpriced')
        self.assertEqual(result['coverageStatus'],'reported-absence-unpriced')
        self.assertFalse(result['affectsPrediction'])
        self.assertTrue(any('replacement' in x.lower() for x in home['missingReasons']))

    def test_missing_first_start_reference_still_exposes_qb_evidence(self):
        g=matchup()
        g['qbIntelligence']['firstStartPrior']['starts']=0
        r=evaluate(g,NOW)
        self.assertEqual(r['status'],'insufficient-empirical-first-starts')
        self.assertEqual(len(r['teamChecks']),2)
        self.assertFalse(r['affectsPrediction'])


    def test_conflicting_espn_and_nflverse_qb_projections_never_price_as_confirmed(self):
        g=matchup()
        g["qbSourceEvidence"]={"home":{"sourceConflict":True},"away":{"sourceConflict":False}}
        result=evaluate(g,NOW)
        self.assertFalse(result["affectsPrediction"])
        self.assertEqual(result["coverageStatus"],"conflicting-sources")
        self.assertEqual(result["teamChecks"][0]["state"],"conflicting-sources")
        self.assertEqual(result["scenarios"][0]["mode"],"scenario-only")
        self.assertTrue(any("conflict" in x for x in result["warnings"]))


    def test_team_primary_survives_two_backup_starts(self):
        engine=QBEngine()
        def completed(i,qb,pid):
            return {'id':'g'+str(i),'home':'BAL','away':'JAX','season':2026,
                'kickoff':NOW-timedelta(days=(14-i)),'home_qb_name':qb,
                'home_qb_id':pid,'away_qb_name':'','away_qb_id':''}
        for i in range(1,7):engine.update(completed(i,'Franchise QB','primary'))
        for i in range(7,9):engine.update(completed(i,'Backup QB','backup'))
        future={'id':'upcoming','home':'BAL','away':'JAX','season':2026,
                'kickoff':NOW+timedelta(days=1)}
        qb=engine.matchup(future)
        room=qb['home']['starterHierarchy']
        self.assertEqual(qb['home']['lastGameLeader']['name'],'Backup QB')
        self.assertEqual(room['status'],'observed-primary')
        self.assertEqual(qb['home']['primaryStarter']['name'],'Franchise QB')
        self.assertEqual(qb['home']['primaryStarter']['verifiedStarts'],6)
        self.assertFalse(qb['home']['lastGameIsPrimary'])
        self.assertEqual(qb['home']['lastGameLeader']['basis'],'last_game_recorded_starter')
        self.assertEqual(room['countedStarts'],8)

    def test_tied_starts_or_not_enough_starts_cannot_invent_primary(self):
        engine=QBEngine()
        def observed(i,pid):
            return {'id':'u'+str(i),'home':'BAL','away':'JAX','season':2026,
                'kickoff':NOW-timedelta(days=10-i),'home_qb_name':pid,
                'home_qb_id':pid,'away_qb_name':'','away_qb_id':''}
        engine.update(observed(1,'A'))
        target={'id':'future','home':'BAL','away':'JAX','season':2026,
                'kickoff':NOW+timedelta(days=1)}
        self.assertIsNone(engine.matchup(target)['home']['primaryStarter'])
        engine.update(observed(2,'B'))
        self.assertEqual(engine.matchup(target)['home']['starterHierarchy']['status'],
                         'tied-observed-starters')
        self.assertIsNone(engine.matchup(target)['home']['primaryStarter'])

    def test_double_qb_absence_uses_backup_to_third_string_once(self):
        g=matchup()
        g['qbIntelligence']['home']['lastGameLeader']={
            'name':'Backup QB','id':'backup','date':(NOW-timedelta(days=6)).isoformat(),
            'season':2026,'basis':'last_game_recorded_starter'}
        g['qbIntelligence']['home']['primaryStarter']={
            'name':'Franchise QB','id':'star','verifiedStarts':6,
            'lastStartAt':(NOW-timedelta(days=20)).isoformat()}
        g['qbIntelligence']['home']['previousQBsample']={
            'dropbacks':160,'games':4,'epaPerDropback':.02}
        g['qbIntelligence']['home']['qb']='Third QB'
        g['supplementalInjuryWatch']['home']=[
            item('Out',name='Franchise QB'),
            item('Out',name='Backup QB')]
        r=evaluate(g,NOW)
        self.assertTrue(r['affectsPrediction'])
        self.assertEqual(len(r['factors']),1)
        self.assertTrue(r['factors'][0]['bothPreviousQBsReportedUnavailable'])
        self.assertEqual(r['scenarios'][0]['establishedQB'],'Franchise QB')
        self.assertEqual(r['scenarios'][0]['lastGameQB'],'Backup QB')
        self.assertTrue(r['scenarios'][0]['twoQBAbsencesReported'])
        self.assertEqual(r['scenarios'][0]['replacementReferencePolicy'],
            'Apply ONLY last-game starter to projected replacement; never add original established-starter penalty twice')
        self.assertAlmostEqual(r['scenarios'][0]['fullAbsencePoints'],7.212,places=2)
        self.assertLess(r['homeProbability'],.53)
        self.assertGreater(r['homeProbability'],.29) # not a second elite-QB subtraction

    def test_prior_starter_out_but_backup_continuing_has_no_new_penalty(self):
        g=matchup()
        g['qbIntelligence']['home']['lastGameLeader']={
            'name':'Backup QB','id':'backup','date':(NOW-timedelta(days=6)).isoformat(),
            'season':2026,'basis':'last_game_recorded_starter'}
        g['qbIntelligence']['home']['primaryStarter']={
            'name':'Franchise QB','id':'franchise','verifiedStarts':6,
            'lastStartAt':(NOW-timedelta(days=20)).isoformat()}
        g['qbIntelligence']['home']['qb']='Backup QB'
        g['supplementalInjuryWatch']['home']=[item('Out',name='Franchise QB')]
        r=evaluate(g,NOW)
        self.assertFalse(r['affectsPrediction'])
        self.assertEqual(r['homeProbability'],.53)
        check=next(c for c in r['teamChecks'] if c['side']=='home')
        self.assertTrue(check['alreadyMissingFromLastGame'])
        self.assertEqual(check['establishedQBStatus'],'OUT')
        self.assertFalse(check['doubleAbsenceReported'])
        self.assertEqual(check['state'],'established-absence-in-baseline')
        self.assertTrue(any('do not deduct' in reason for reason in check['missingReasons']))

    def test_primary_status_does_not_equal_new_backup_status(self):
        g=matchup()
        g['qbIntelligence']['home']['lastGameLeader']={
            'name':'Backup QB','id':'backup','date':(NOW-timedelta(days=6)).isoformat(),
            'season':2026,'basis':'last_game_recorded_starter'}
        g['qbIntelligence']['home']['primaryStarter']={
            'name':'Franchise QB','verifiedStarts':7}
        g['qbIntelligence']['home']['previousQBsample']={
            'dropbacks':160,'games':4,'epaPerDropback':.02}
        g['qbIntelligence']['home']['qb']='Third QB'
        g['supplementalInjuryWatch']['home']=[item('Out',name='Franchise QB')]
        r=evaluate(g,NOW)
        self.assertFalse(r['affectsPrediction'])
        self.assertFalse(r['scenarios'][0]['twoQBAbsencesReported'])
        self.assertEqual(r['scenarios'][0]['reportStatus'],'unverified projected switch')



    def test_applied_replacement_suppresses_overlapping_qb_efficiency(self):
        """Two statistical descriptions of the same QB change cannot stack."""
        from unittest.mock import patch
        from update import apply_personnel_forecasts
        row={'id':'fixture','home':'BAL','away':'JAX','season':2026,'week':9,
             'kickoff':(NOW+timedelta(days=1)).isoformat(),
             'homeProbability':.5,'predMargin':0,'predHome':24,'predAway':24,
             'predTotal':48,'model':'Elo/form'}
        candidate={'status':'qb-efficiency-provisional','affectsPrediction':True,
                   'homeProbability':.6,'homeDelta':.1,'marginDelta':2.,
                   'factors':[{'kind':'qb-efficiency'}]}
        observed_inputs=[]
        def replace(game,now):
            p=game['homeProbability']
            observed_inputs.append(p)  # capture before output row is mutated
            return {'status':'reported-absence-provisional','affectsPrediction':True,
                    'homeProbability':round(p-.1,5),'homeDelta':-.1,'marginDelta':-3.,
                    'scenarios':[],'factors':[{'kind':'qb-replacement'}]}
        def injury(game,now,exclude_qb=False):
            self.assertTrue(exclude_qb)
            return {'status':'none','affectsPrediction':False,
                    'homeProbability':game['homeProbability'],
                    'homeDelta':0.,'marginDelta':0.,'factors':[]}
        with patch('update.qb_efficiency_preview',return_value=candidate), \
             patch('update.assess_replacement',side_effect=replace) as replace_mock, \
             patch('update.assess_personnel',side_effect=injury):
            dash={'nextGames':[row], 'qbValidation':{}}
            apply_personnel_forecasts(dash,{},NOW,'full',[])
        self.assertEqual(replace_mock.call_count,1)
        self.assertEqual(observed_inputs,[.5])
        self.assertEqual(row['homeProbability'],.4)
        summary=row['personnelScenario']
        self.assertEqual(summary['qbStatisticalHomeDelta'],0.)
        self.assertEqual(summary['qbReplacementHomeDelta'],-.1)
        self.assertEqual(summary['statisticalQB']['status'],
                         'withheld-overlapping-replacement-impact')
        self.assertEqual(summary['statisticalQB']['candidateHomeDelta'],.1)
        self.assertEqual(len(summary['factors']),1)
        self.assertEqual(summary['factors'][0]['kind'],'qb-replacement')
        self.assertEqual(dash['qbReplacementSource']['counts']['suppressedOverlappingQB'],1)

    def test_statistical_qb_remains_if_replacement_not_source_verified(self):
        from unittest.mock import patch
        from update import apply_personnel_forecasts
        row={'id':'fixture','home':'BAL','away':'JAX',
             'homeProbability':.5,'predMargin':0,'predHome':24,'predAway':24,
             'predTotal':48,'model':'Elo/form'}
        candidate={'status':'qb-efficiency-provisional','affectsPrediction':True,
                   'homeProbability':.6,'homeDelta':.1,'marginDelta':2.,
                   'factors':[{'kind':'qb-efficiency'}]}
        def no_replacement(game,now):
            return {'status':'projection-only','affectsPrediction':False,
                    'homeProbability':game['homeProbability'],'marginDelta':0.,
                    'scenarios':[],'factors':[]}
        def no_injury(game,now,exclude_qb=False):
            return {'status':'none','affectsPrediction':False,
                    'homeProbability':game['homeProbability'],'marginDelta':0.,
                    'factors':[]}
        with patch('update.qb_efficiency_preview',return_value=candidate), \
             patch('update.assess_replacement',side_effect=no_replacement), \
             patch('update.assess_personnel',side_effect=no_injury):
            apply_personnel_forecasts({'nextGames':[row]}, {},NOW,'full',[])
        self.assertEqual(row['homeProbability'],.6)
        self.assertEqual(row['personnelScenario']['qbStatisticalHomeDelta'],.1)
        self.assertEqual(row['personnelScenario']['qbReplacementHomeDelta'],0.)

if __name__=='__main__':unittest.main()
