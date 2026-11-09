import unittest,sys,tempfile,json
from datetime import datetime,timedelta,timezone
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
from primary_forecast import publish,PRIMARY_VERSION
UTC=timezone.utc
NOW=datetime(2026,11,9,18,tzinfo=UTC)
def fixture(id='g',kick=None):
  return {'id':id,'home':'MIN','away':'BUF','season':2026,'week':10,
   'kickoff':(kick or NOW+timedelta(days=3)).isoformat(),
   'homeProbability':.56,'model':'elo-form-v1',
   'forecastQuality':{'level':'hold'},
   'shadowEnsemble':{'version':'joint-xgb-v2-2026-11-09','homeProbability':.68,
    'researchOnly':True,'reconciles':True,'productionWeight':0,
    'layers':[{'key':'team','deltaHomePP':10}]}}
def dash(g):
  return {'nextGames':[g],'challengerValidation':{
    'status':'historical-research-candidate','candidateQualifiedForFurtherResearch':True,
    'evaluationGames':569}}
class PrimaryTests(unittest.TestCase):
  def test_headline_can_change_without_mutating_official_pick(self):
    with tempfile.TemporaryDirectory() as t:
      game=fixture();d=dash(game);p=Path(t)/'primary.json'
      summary=publish(d,[],NOW,p)
      self.assertEqual(game['homeProbability'],.56)
      self.assertEqual(game['primaryForecast']['homeProbability'],.68)
      self.assertEqual(game['primaryForecast']['originalHomeProbability'],.56)
      self.assertTrue(game['primaryForecast']['needsReview'])
      self.assertFalse(game['primaryForecast']['eligibleForBetting'])
      self.assertEqual(summary['firstRecordedPicks'],1)
      records=json.loads(p.read_text())
      self.assertEqual(records[0]['modelVersion'],PRIMARY_VERSION)
      game['shadowEnsemble']['homeProbability']=.88
      publish(d,[],NOW+timedelta(hours=1),p)
      self.assertEqual(len(json.loads(p.read_text())),1)
      self.assertEqual(json.loads(p.read_text())[0]['homeProbability'],.68)
  def test_independent_prospective_scoring(self):
    with tempfile.TemporaryDirectory() as t:
      g=fixture();d=dash(g);p=Path(t)/'primary.json'
      publish(d,[],NOW,p)
      final={'id':'g','home':'MIN','away':'BUF','kickoff':g['kickoff'],
             'home_score':21,'away_score':17}
      data=publish(d,[final],NOW+timedelta(days=5),p)
      self.assertEqual(data['gradedGames'],1)
      self.assertAlmostEqual(data['provisionalBrier'],(.68-1)**2,6)
      self.assertAlmostEqual(data['matchedOriginalBrier'],(.56-1)**2,6)
      self.assertEqual(len(json.loads(p.read_text())),1)
  def test_fail_closed_if_model_missing_or_research_gate_fails(self):
    with tempfile.TemporaryDirectory() as t:
      g=fixture();d=dash(g);p=Path(t)/'primary.json'
      d['challengerValidation']['candidateQualifiedForFurtherResearch']=False
      res=publish(d,[],NOW,p)
      self.assertEqual(res['upcomingProvisional'],0)
      self.assertEqual(g['primaryForecast']['homeProbability'],.56)
      self.assertEqual(res['firstRecordedPicks'],0)
      d['challengerValidation']['candidateQualifiedForFurtherResearch']=True
      g['shadowEnsemble']['reconciles']=False
      self.assertEqual(publish(d,[],NOW,p)['firstRecordedPicks'],0)
  def test_material_qb_replacement_is_not_overwritten_by_joint_model(self):
    with tempfile.TemporaryDirectory() as t:
      g=fixture();g['personnelScenario']={'affectsPrediction':True,'homeDelta':-.07,
        'qbReplacementHomeDelta':-.07,'status':'reported QB replacement — PROVISIONAL'}
      d=dash(g)
      result=publish(d,[],NOW,Path(t)/'primary.json')
      self.assertEqual(result['upcomingProvisional'],0)
      self.assertEqual(g['primaryForecast']['homeProbability'],g['homeProbability'])
      self.assertIn('QB/injury',g['primaryForecast']['reason'])
      g['personnelScenario']={'affectsPrediction':True,'homeDelta':-.0003}
      self.assertEqual(publish(d,[],NOW,Path(t)/'primary.json')['upcomingProvisional'],1)

  def test_never_backfill_after_kickoff(self):
    with tempfile.TemporaryDirectory() as t:
      g=fixture(kick=NOW-timedelta(hours=1));d=dash(g)
      self.assertEqual(publish(d,[],NOW,Path(t)/'primary.json')['firstRecordedPicks'],0)
      self.assertEqual(g['primaryForecast']['status'],'original-fallback')
if __name__=='__main__':unittest.main()
