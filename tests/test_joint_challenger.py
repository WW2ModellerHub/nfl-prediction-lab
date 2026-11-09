"""Joint model: as-of feature safety, matched seasonal tests, exact SHAP reconciliation."""
import sys, unittest, math
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
from shadow_ensemble import (
    FEATURES,GROUPS,VERSION,vector,_fit,_explain,_predict,run,
)

def fixture():
    return {
       'situation':{'home':{'fullRestDays':9},'away':{'fullRestDays':5},
         'signals':[{'id':'rest_edge','side':'home','direction':'back'},
                    {'id':'repeat_road','side':'away','direction':'fade'}]},
       'elo_home':1570,'elo_away':1470,'home_form':27,'away_form':21,
       'home_allowed':22,'away_allowed':28,
       'qb_research':{'eligible':True,'features':[.22,.07,1]},
       'tactical':{'status':'ready','features':[.7,.3,.25,.1]},
       'player_impact':{'eligible':True,'features':[.22,1,.07,1.4],
                        'injuryArchiveLoaded':True},
    }

class JointModelTests(unittest.TestCase):
    def test_feature_groups_and_missing_injury_are_distinct(self):
        g={'neutral':False}
        x=vector(g,fixture())
        self.assertEqual(len(x),len(FEATURES))
        self.assertEqual(x[FEATURES.index('rest_edge')],1)
        self.assertEqual(x[FEATURES.index('qb_change_watch')],1)
        self.assertEqual(x[FEATURES.index('injury_archive_available')],1)
        f=fixture()
        f['player_impact']['injuryArchiveLoaded']=False
        absent=vector(g,f)
        self.assertEqual(absent[FEATURES.index('injury_archive_available')],0)
        self.assertEqual(absent[FEATURES.index('reported_absence_edge')],0)
        f['qb_research']['eligible']=False
        missing=vector(g,f)
        self.assertEqual(missing[FEATURES.index('qb_available')],0)
        self.assertEqual(missing[FEATURES.index('qb_epa_edge')],0)

    def test_reject_unknown_data_as_zero_instead_of_as_true_player_absence(self):
        f=fixture()
        f['qb_research']={'eligible':False,'features':None}
        f['tactical']={'status':'unavailable'}
        f['player_impact']={'eligible':False,'injuryArchiveLoaded':False}
        values=vector({'neutral':True},f)
        for col in ('qb_available','qb_epa_edge','tactical_available','pass_matchup',
                    'injury_archive_available','reported_absence_edge'):
            self.assertEqual(values[FEATURES.index(col)],0)
        self.assertNotIn('wind_speed',FEATURES)
        self.assertNotIn('injury_status_from_final_box_score',FEATURES)

    @unittest.skipUnless(__import__('importlib').util.find_spec('xgboost'), 'xgboost optional')
    def test_joint_prediction_contributions_reconcile_and_shadow_only(self):
        import random
        r=random.Random(18)
        rows=[]
        base=vector({'neutral':False},fixture())
        for i in range(320):
            x=[b+r.uniform(-.25,.25) for b in base]
            x[FEATURES.index('qb_available')]=1
            x[FEATURES.index('tactical_available')]=1
            x[FEATURES.index('injury_archive_available')]=0
            x[FEATURES.index('reported_absence_edge')]=0
            rows.append({'season':2024,'id':str(i),'p':.4+.18*r.random(),'features':x,
                         'y':int(r.random()<.4+.3*max(-.4,min(.4,x[0])))})
        model=_fit(rows)
        tests=[{'id':'future','season':2026,'p':.46,'features':base}]
        forecasts=_explain(model,tests)
        self.assertEqual(len(forecasts),1)
        item=forecasts[0]
        expected=_predict(model,tests)[0]
        self.assertAlmostEqual(item['homeProbability'],expected,places=5)
        self.assertTrue(item['reconciles'])
        self.assertEqual([x['key'] for x in item['layers']],
            ['calibration']+[g[0] for g in GROUPS])
        self.assertAlmostEqual(sum(x['deltaHomePP'] for x in item['layers']),
            item['impactPP'],delta=.002)
        self.assertIn('Archived pregame weather (no trained coefficient)',item['missingEvidence'])

    def test_gates_refuse_short_history_without_retroactive_score(self):
        no_future=[{'season':2026,'p':.8,'features':[0]*len(FEATURES),'y':1,'id':'s'}]
        val,pred=run(no_future,[{'id':'f','p':.5,'features':[0]*len(FEATURES)}],2026)
        self.assertFalse(pred)
        self.assertEqual(val['version'],VERSION)
        self.assertEqual(val['productionWeight'],0)
        self.assertFalse(val['researchOnly'] is False)

if __name__=='__main__': unittest.main()
