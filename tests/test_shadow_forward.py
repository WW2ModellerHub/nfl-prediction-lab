"""Prospective shadow predictions must be recorded before kickoff only."""
import tempfile,sys,unittest
from pathlib import Path
from datetime import datetime,timezone,timedelta
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
from update import record_shadow_predictions

class ShadowForwardTest(unittest.TestCase):
    def test_no_retroactive_or_overwritten_forecasts(self):
        now=datetime(2026,11,4,22,tzinfo=timezone.utc)
        kickoff=now+timedelta(days=1)
        old=now-timedelta(days=1)
        games=[{'id':'future','home_score':None,'away_score':None,'kickoff':kickoff},
               {'id':'old','home_score':31,'away_score':10,'kickoff':old}]
        data={'nextGames':[
            {'id':'future','kickoff':kickoff.isoformat(),'homeProbability':.55,
             'shadowEnsemble':{'researchOnly':True,'homeProbability':.63}},
            {'id':'old','kickoff':old.isoformat(),'homeProbability':.75,
             'shadowEnsemble':{'researchOnly':True,'homeProbability':.75}}]}
        with tempfile.TemporaryDirectory() as folder:
            path=Path(folder)/'shadow.json'
            entries=record_shadow_predictions(data,games,now,path)
            self.assertEqual(len(entries),1)
            self.assertEqual(entries[0]['gameId'],'future')
            self.assertIsNone(data['shadowForwardPerformance']['brier'])
            data['nextGames'][0]['shadowEnsemble']['homeProbability']=.9
            again=record_shadow_predictions(data,games,now+timedelta(hours=1),path)
            self.assertEqual(again[0]['homeProbability'],.63)
            games[0]['home_score']=35;games[0]['away_score']=17
            scored=record_shadow_predictions(data,games,kickoff+timedelta(days=1),path)
            self.assertEqual(len(scored),1)
            self.assertEqual(data['shadowForwardPerformance']['gradedGames'],1)
            self.assertAlmostEqual(data['shadowForwardPerformance']['brier'],(.63-1)**2,5)
if __name__=='__main__':unittest.main()
