"""No after-kickoff feature backfilling or false weather availability."""
import sys,tempfile,json,unittest
from pathlib import Path
from datetime import datetime,timezone,timedelta
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
from prospective_features import record
NOW=datetime(2026,11,9,18,tzinfo=timezone.utc)
class FeatureCaptureTests(unittest.TestCase):
    def fixture(self,kick):
        return {'id':'game-1','home':'MIN','away':'BUF','season':2026,'week':9,
                'kickoff':kick.isoformat(),'homeProbability':.53,'baselineHomeProbability':.5,
                'weather':{'status':'forecast','retrievedAt':NOW.isoformat(),'wind_speed_10m':21,
                           'wind_gusts_10m':31,'temperature_2m':4,'source':'Open-Meteo'},
                'qbIntelligence':{'home':{'playerId':'qbH','sample':{'dropbacks':100,'epaPerDropback':.12}},
                    'away':{'playerId':'qbA','sample':{'dropbacks':200,'epaPerDropback':.2}}},
                'injuryIntelligence':{'status':'snapshot-only','home':[{'status':'OUT'}],'away':[]},
                'shadowEnsemble':{'version':'joint-xgb-v2-2026-11-09','researchOnly':True,
                                  'homeProbability':.54,'missingEvidence':['weather model untrained']}}
    def test_persists_two_snapshots_and_never_rewrites_pre_game_observation(self):
        kick=NOW+timedelta(hours=8)
        with tempfile.TemporaryDirectory() as t:
            p=Path(t)/'archive.json'
            row=self.fixture(kick)
            result=record({'nextGames':[row]},NOW,p)
            self.assertEqual(result['added'],1)
            row['homeProbability']=.99
            self.assertEqual(record({'nextGames':[row]},NOW+timedelta(minutes=5),p)['added'],0)
            with p.open() as fh:
                existing=json.load(fh)['observations']
            self.assertEqual(existing[0]['publishedHomeProbability'],.53)
            self.assertFalse(existing[0]['trainingEligible'])
            self.assertEqual(existing[0]['weather']['values']['wind_speed_10m'],21)
            self.assertFalse(existing[0]['injuries']['verifiedActiveRoster'])
            self.assertEqual(record({'nextGames':[row]},NOW+timedelta(hours=4),p)['added'],1)
            self.assertEqual(record({'nextGames':[row]},kick+timedelta(minutes=2),p)['added'],0)
            records=json.loads(p.read_text())['observations']
            self.assertEqual([r['window'] for r in records],['early','late'])
            self.assertEqual(records[0]['recordedAt'],NOW.isoformat())
    def test_unverified_weather_not_interpreted_as_calm(self):
        with tempfile.TemporaryDirectory() as t:
            g=self.fixture(NOW+timedelta(hours=1))
            g['weather']['retrievedAt']=(NOW+timedelta(minutes=5)).isoformat()
            p=Path(t)/'archive.json'
            record({'nextGames':[g]},NOW,p)
            entry=json.loads(p.read_text())['observations'][0]
            self.assertEqual(entry['weather']['values'],{})
            self.assertIsNone(entry['weather']['source'])
    def test_not_recorded_after_kickoff_or_from_invalid_timestamp(self):
        with tempfile.TemporaryDirectory() as t:
            p=Path(t)/'a.json'
            self.assertEqual(record({'nextGames':[self.fixture(NOW)]},NOW,p)['added'],0)
            self.assertEqual(record({'nextGames':[self.fixture(NOW-timedelta(days=2))]},NOW,p)['added'],0)
            with self.assertRaises(ValueError):record({},datetime(2026,11,9),p)
if __name__=='__main__':unittest.main()
