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
        self.assertLess(r['marginDelta'],0)

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

if __name__=='__main__':unittest.main()
