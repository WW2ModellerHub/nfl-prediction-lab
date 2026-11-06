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

    def test_recover_completed_game_only_from_verified_immutable_original(self):
        with tempfile.TemporaryDirectory() as tmp:
            path=Path(tmp)/'revisions.json'
            earlier=(T-timedelta(days=3)).isoformat()
            kickoff=(T-timedelta(days=1)).isoformat()
            jag={'gameId':'2026_09_JAX_BAL','kickoff':kickoff,
                 'recordedAt':earlier,'home':'BAL','away':'JAX',
                 'homeProbability':.47021,'baselineHomeProbability':.47021,
                 'predMargin':-2.48,'model':'elo-form-archived'}
            final={'id':'2026_09_JAX_BAL','season':2026,'week':9,
                   'home':'BAL','away':'JAX','kickoff':datetime.fromisoformat(kickoff),
                   'home_score':10,'away_score':33}
            d={'nextGames':[]}
            archive=revisions(d,[jag],[final],T,path)
            self.assertEqual(len(archive),1)
            self.assertEqual(archive[0]['kind'],'first')
            self.assertEqual(archive[0]['homeProbability'],.47021)
            self.assertEqual(archive[0]['recordedAt'],earlier)
            self.assertEqual(archive[0]['importedAt'],T.isoformat())
            self.assertEqual(archive[0]['origin'],'recovered-from-immutable-original-log')
            self.assertEqual(d['forecastRevisionSummary']['completedCompared'],1)
            self.assertEqual(d['forecastRevisionSummary']['changedGames'],0)
            self.assertEqual(d['forecastRevisionSummary']['qbEvidenceGraded'],0)
            self.assertEqual(d['forecastRevisionSummary']['latestWithin24hGames'],0)
            result=d['forecastRevisionResults'][0]
            self.assertEqual(result['winner'],'JAX')
            self.assertEqual(result['firstProbability'],.47021)
            self.assertEqual(result['lastProbability'],.47021)
            self.assertEqual(result['revisionsAfterFirst'],0)
            self.assertEqual(result['firstCorrect'],1)
            self.assertEqual(result['brierGain'],0)
            prior=path.read_bytes()
            self.assertEqual(len(revisions({'nextGames':[]},[jag],[final],T,path)),1)
            self.assertEqual(path.read_bytes(),prior)

    def test_pregame_timestamp_must_precede_actual_kickoff_even_in_legacy(self):
        with tempfile.TemporaryDirectory() as tmp:
            path=Path(tmp)/'r.json'
            kickoff=(T-timedelta(days=1)).isoformat()
            late={'gameId':'bad','kickoff':kickoff,'recordedAt':T.isoformat(),
                  'homeProbability':.91,'home':'BAL','away':'JAX'}
            scored={'id':'bad','home':'BAL','away':'JAX','kickoff':datetime.fromisoformat(kickoff),
                    'home_score':21,'away_score':3}
            d={'nextGames':[]}
            self.assertEqual(revisions(d,[late],[scored],T,path),[])
            self.assertEqual(d['forecastRevisionSummary']['completedCompared'],0)

    def test_original_integrity_check_refuses_overwrite(self):
        with tempfile.TemporaryDirectory() as tmp:
            path=Path(tmp)/'r.json'
            first={'gameId':'g','recordedAt':(T-timedelta(days=2)).isoformat(),
                   'kickoff':K,'home':'BAL','away':'JAX','homeProbability':.53}
            d={'nextGames':[g(.42)]}
            revisions(d,[first],[],T,path)
            damaged=[{**first,'homeProbability':.93}]
            with self.assertRaisesRegex(ValueError,'Immutable original changed'):
                revisions({'nextGames':[g(.4)]},damaged,[],T+timedelta(hours=1),path)
            self.assertEqual(len(__import__('json').loads(path.read_text())),2)

    def test_late_window_is_real_archived_observation_only(self):
        with tempfile.TemporaryDirectory() as tmp:
            path=Path(tmp)/'r.json'
            old=(T-timedelta(days=2))
            legacy={'gameId':'g','recordedAt':old.isoformat(),
                    'kickoff':K,'home':'BAL','away':'JAX','homeProbability':.30}
            d={'nextGames':[g(.45)]}
            revisions(d,[legacy],[],T,path)
            d={'nextGames':[g(.7)]}
            late=T+timedelta(days=1,hours=3)
            revisions(d,[legacy],[],late,path)
            final={'id':'g','home':'BAL','away':'JAX','kickoff':datetime.fromisoformat(K),
                   'home_score':28,'away_score':10}
            scored={'nextGames':[]}
            revisions(scored,[legacy],[final],T+timedelta(days=3),path)
            summary=scored['forecastRevisionSummary']
            self.assertEqual(summary['latestWithin24hGames'],1)
            self.assertEqual(summary['completedCompared'],1)
            self.assertEqual(summary['changedGames'],1)
            self.assertEqual(summary['improvedGames'],1)
            self.assertAlmostEqual(summary['originalBrier'],(.30-1)**2)
            self.assertAlmostEqual(summary['latest24hBrier'],(.7-1)**2)
            self.assertEqual(scored['forecastRevisionResults'][0]['lastProbability'],.7)

    def test_tied_or_not_yet_final_game_never_scored(self):
        with tempfile.TemporaryDirectory() as tmp:
            path=Path(tmp)/'r.json'
            first={'gameId':'g','recordedAt':(T-timedelta(hours=1)).isoformat(),
                   'kickoff':(T+timedelta(hours=1)).isoformat(),
                   'home':'BAL','away':'JAX','homeProbability':.72}
            falsely_final={'id':'g','home':'BAL','away':'JAX',
                          'kickoff':T+timedelta(hours=1),'home_score':33,'away_score':7}
            d={'nextGames':[]}
            revisions(d,[first],[falsely_final],T,path)
            self.assertEqual(d['forecastRevisionSummary']['completedCompared'],0)

if __name__=='__main__':unittest.main()
