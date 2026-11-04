"""Regression checks for nflreadpy participation and research-only challenger."""
import sys,unittest,random
from pathlib import Path
from datetime import datetime,timezone
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
from player_usage import _key,_pct,UsageHistory,enrich_upcoming
from shadow_ensemble import vector,run,FEATURES

UTC=timezone.utc
def dt(day):return datetime(2026,10,day,tzinfo=UTC)

class UsageTest(unittest.TestCase):
    def test_name_and_pct(self):
        self.assertEqual(_key('John Smith Jr.'),_key('John Smith'))
        self.assertEqual(_pct(84),.84)
        self.assertIsNone(_pct(-2))
    def test_future_snap_never_backfilled(self):
        schedule=[{'id':'a','kickoff':dt(1)},{'id':'b','kickoff':dt(8)},
                  {'id':'c','kickoff':dt(15)},{'id':'d','kickoff':dt(22)}]
        rows=[{'game_id':g,'team':'JAC','player':'John Smith Jr.','offense_pct':p,'defense_pct':0}
              for g,p in [('a',.74),('b',.82),('c',.95),('d',1.)]]
        history=UsageHistory(rows,schedule)
        self.assertEqual(history.recent('JAX','John Smith',dt(15))['offensePct'],.78)
        self.assertIsNone(history.recent('KC','John Smith',dt(15)))
        upcoming={'id':'c','kickoff':dt(15).isoformat(),'home':'JAX','away':'BUF',
                  'supplementalInjuryWatch':{'home':[{'name':'John Smith','status':'Questionable'}],'away':[]}}
        self.assertEqual(enrich_upcoming([upcoming],history,dt(14)),1)
        prior=upcoming['supplementalInjuryWatch']['home'][0]['recentUsage']
        self.assertFalse(prior['availabilityConfirmed'])
        self.assertEqual(prior['games'],2)

class EnsembleTest(unittest.TestCase):
    def test_input_schema_missing_signals(self):
        g={'neutral':False}
        p={'elo_home':1520,'elo_away':1500,'home_form':28,'away_form':20,
           'home_allowed':20,'away_allowed':24,'situation':{'home':{'fullRestDays':7},'away':{'fullRestDays':4}},
           'qb_research':{'eligible':False},'tactical':{'status':'insufficient'}}
        x=vector(g,p)
        self.assertEqual(len(x),len(FEATURES))
        self.assertEqual(x[7],0)
        self.assertEqual(x[12],0)
    def test_no_current_season_training(self):
        try:import xgboost
        except ImportError:self.skipTest('optional XGBoost unavailable')
        rng=random.Random(24)
        history=[]
        for year in range(2018,2027):
            for i in range(215):
                p=.3+.4*(i%19)/18
                history.append({'id':str(year)+'-'+str(i),'season':year,'p':p,
                    'y':int(rng.random()<p),'features':[2*p-1,rng.random()-.5,0,1,0,0,0,0,0,0,0,0,0]})
        future=[{'id':'future','p':.55,'features':[.1,0,0,1,0,0,0,0,0,0,0,0,0]}]
        report,a=run(history,future,2026)
        self.assertEqual(report['productionWeight'],0)
        self.assertTrue(report['researchOnly'])
        self.assertEqual(report['trainSeasons'][-1],2025)
        self.assertEqual([x['season'] for x in report['seasons']],[2024,2025])
        history[-1]['y']=1-history[-1]['y']
        report2,b=run(history,future,2026)
        self.assertEqual(a,b)
        self.assertEqual(report['seasons'],report2['seasons'])

if __name__=='__main__':unittest.main()
