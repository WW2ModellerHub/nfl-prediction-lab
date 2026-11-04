import math
import random
import sys
import unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
from situational_validation import FEATURES, feature_vector, fit, predict, validate

class SituationalValidationTests(unittest.TestCase):
    def test_home_and_away_direction_encoding(self):
        context={'signals':[
            {'id':'empty_tank','direction':'fade','side':'away'},
            {'id':'rest_edge','direction':'back','side':'home'},
            {'id':'nuclear_bounce','direction':'back','side':'away'}]}
        v=dict(zip(FEATURES,feature_vector(context)))
        self.assertEqual(v['empty_tank'],1)
        self.assertEqual(v['rest_edge'],1)
        self.assertEqual(v['nuclear_bounce'],-1)

    def test_opposing_same_signal_cancels(self):
        ctx={'signals':[{'id':'repeat_road','direction':'fade','side':'away'},
                        {'id':'repeat_road','direction':'fade','side':'home'}]}
        self.assertEqual(feature_vector(ctx)[-1],0)

    def test_insufficient_history_never_enables_adjustment(self):
        rows=[{'season':2025,'p':0.5,'features':(1,0,0,0,0,0),'y':1}]*12
        check=validate(rows,2026)
        self.assertFalse(check['enabled'])
        self.assertTrue(all(v==0 for v in check['coefficients'].values()))

    def test_penalised_coefficients_with_no_signal_are_zero(self):
        rows=[{'season':2019,'p':0.6,'features':(0,)*6,'y':i%2} for i in range(600)]
        self.assertEqual(fit(rows),[0.]*6)
        self.assertAlmostEqual(predict(.6,(0,)*6,[0.]*6),.6)

    def test_future_season_does_not_leak_into_gate(self):
        rand=random.Random(121)
        rows=[]
        for yr in range(2016,2027):
            for i in range(120):
                direction=1 if i%2 else -1
                # Training years have an independently measurable positive effect.
                p=0.5
                raw=.80 if direction==1 else .20
                if yr==2026: raw=1-raw  # adversarial present season results
                y=int(rand.random()<raw)
                rows.append({'season':yr,'p':p,'features':(direction,0,0,0,0,0),'y':y})
        baseline=validate([r for r in rows if r['season']<2026],2026)
        with_current=validate(rows,2026)
        self.assertEqual(baseline,with_current)
        self.assertGreater(baseline['selectionSample'],350)
        self.assertTrue(baseline['enabled'])
        self.assertGreater(baseline['coefficients']['empty_tank'],0)
        self.assertGreater(baseline['selectionBrierGain'],0.001)

    def test_no_effect_does_not_activate_from_noise(self):
        # Balanced outcomes by season, conditional on each flag value.
        rows=[]
        for yr in range(2016,2026):
            for i in range(120):
                direction=1 if i%2 else -1
                y=(i//2)%2
                rows.append({'season':yr,'p':0.5,'features':(direction,0,0,0,0,0),'y':y})
        checked=validate(rows,2026)
        self.assertFalse(checked['enabled'])
        self.assertTrue(all(x==0 for x in checked['coefficients'].values()))

if __name__=='__main__':unittest.main()
