import unittest,tempfile
from pathlib import Path
from datetime import datetime,timedelta,timezone
import sys
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
from forecast_revisions import revisions
T=datetime(2026,11,6,12,tzinfo=timezone.utc)
K=(T+timedelta(days=2)).isoformat()
def g(p=.5):
    return {'id':'g','home':'BAL','away':'JAX','kickoff':K,'homeProbability':p,
            'baselineHomeProbability':.5,'predMargin':1,'model':'Research'}
class RevisionsTest(unittest.TestCase):
    def test_archive_original_and_each_distinct_refresh(self):
        with tempfile.TemporaryDirectory() as t:
            path=Path(t)/'r.json'
            first={'gameId':'g','recordedAt':(T-timedelta(days=2)).isoformat(),
                   'kickoff':K,'home':'BAL','away':'JAX','homeProbability':.53}
            d={'nextGames':[g(.45)]}
            rows=revisions(d,[first],[],T,path)
            self.assertEqual(len(rows),2)
            self.assertEqual(rows[0]['homeProbability'],.53)
            self.assertEqual(rows[1]['homeProbability'],.45)
            self.assertEqual(len(revisions(d,[first],[],T,path)),2)
            d['nextGames']=[g(.4)]
            rows=revisions(d,[first],[],T+timedelta(hours=1),path)
            self.assertEqual([x['homeProbability'] for x in rows],[.53,.45,.4])
            self.assertEqual(d['nextGames'][0]['forecastHistoryCount'],3)
            saved=path.read_text()
            revisions({'nextGames':[g(.1)]},[first],[],T+timedelta(days=3),path)
            self.assertEqual(path.read_text(),saved)
    def test_grade_earliest_and_last_before_kickoff(self):
        with tempfile.TemporaryDirectory() as t:
            path=Path(t)/'r.json'
            revisions({'nextGames':[g(.4)]},[],[],T,path)
            revisions({'nextGames':[g(.7)]},[],[],T+timedelta(hours=1),path)
            finished={'id':'g','kickoff':datetime.fromisoformat(K),'home_score':28,'away_score':20}
            d={'nextGames':[]}
            revisions(d,[],[finished],T+timedelta(days=3),path)
            self.assertEqual(d['forecastRevisionSummary']['completedCompared'],1)
            self.assertAlmostEqual(d['forecastRevisionSummary']['originalBrier'],(.4-1)**2)
            self.assertAlmostEqual(d['forecastRevisionSummary']['latestBrier'],(.7-1)**2)
if __name__=='__main__':unittest.main()
