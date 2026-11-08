"""Only timestamped paired pregame player impacts may be graded."""
import sys
import tempfile
import unittest
from datetime import datetime,timedelta,timezone
from pathlib import Path

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/"scripts"))
from forecast_revisions import revisions,dt,valid,snapshot
from player_effect_scorecard import summarize

T=datetime(2026,11,8,12,tzinfo=timezone.utc)
K=T+timedelta(days=1)

def original(p=.55,base=.60,qb=-.05,injury=0,at=T,source="fresh"):
    return {"gameId":"g","home":"BAL","away":"JAX","kickoff":K.isoformat(),
        "recordedAt":at.isoformat(),"kind":"refresh","origin":"test-live-pick",
        "homeProbability":p,"prePersonnelProbability":base,
        "provisionalPlayerApplied":True,"personnelSourceMode":source,
        "personnelSourceObservedAt":at.isoformat(),
        "verificationLevel":"review",
        "playerEffectDeltas":{"qb-statistical":qb,
                              "qb-replacement":0,"other-injuries":injury}}
def final():
    return {"gameId":"g","kickoff":K.isoformat(),"season":2026,"week":10,
        "home":"BAL","away":"JAX","outcomeHome":0}
class PlayerEffectScorecardTests(unittest.TestCase):
    def test_positive_gain_same_time_control_and_one_game(self):
        a=original(p=.55,base=.6)
        a2=original(p=.51,base=.6,qb=-.09,at=T+timedelta(hours=1))
        out=summarize([final()],{"g":[a,a2]},dt,valid)
        self.assertEqual(out["games"],1)
        self.assertAlmostEqual(out["withPlayerBrier"],.51**2)
        self.assertAlmostEqual(out["withoutPlayerBrier"],.6**2)
        self.assertAlmostEqual(out["brierGain"],.6**2-.51**2)
        self.assertEqual(out["qbEffects"]["games"],1)
        self.assertEqual(out["otherInjuries"]["games"],0)
        self.assertEqual(out["improved"],1)
        self.assertFalse(out["calibratedOrApproved"])
    def test_future_and_postkickoff_timestamps_rejected(self):
        later=original(at=K+timedelta(minutes=1))
        future_evidence=original()
        future_evidence["personnelSourceObservedAt"]=(T+timedelta(hours=2)).isoformat()
        self.assertEqual(summarize([final()],{"g":[later,future_evidence]},dt,valid)["games"],0)
    def test_cached_and_old_legacy_snapshots_not_backfilled(self):
        cached=original(source="cached")
        legacy=original()
        del legacy["prePersonnelProbability"]
        self.assertEqual(summarize([final()],{"g":[cached,legacy]},dt,valid)["games"],0)
    def test_layer_reconciliation_required_and_dual_components(self):
        wrong=original(p=.2,base=.6,qb=-.05)
        good=original(p=.50,base=.6,qb=-.08,injury=-.02)
        out=summarize([final()],{"g":[wrong,good]},dt,valid)
        self.assertEqual(out["games"],1)
        self.assertEqual(out["qbEffects"]["games"],1)
        self.assertEqual(out["otherInjuries"]["games"],1)
        self.assertEqual(out["recentResults"][0]["type"],"both")
    def test_no_invention_when_no_applied_player_adjustment(self):
        a=original(p=.6,base=.6,qb=0)
        a["provisionalPlayerApplied"]=False
        self.assertEqual(summarize([final()],{"g":[a]},dt,valid)["games"],0)
    def test_real_snapshot_persists_paired_reference_and_deltas(self):
        g={"id":"g","home":"BAL","away":"JAX","kickoff":K.isoformat(),
            "homeProbability":.55,"prePersonnelProbability":.6,
            "personnelScenario":{"affectsPrediction":True,"status":"statistical QB — PROVISIONAL",
                "sourceObservedAt":T.isoformat(),"qbStatisticalHomeDelta":-.05,
                "qbReplacementHomeDelta":0,"injuryHomeDelta":0}}
        record=snapshot(g,T,"refresh","automated")
        self.assertTrue(record["provisionalPlayerApplied"])
        self.assertEqual(record["personnelSourceMode"],"fresh")
        self.assertEqual(record["prePersonnelProbability"],.6)
        self.assertAlmostEqual(record["playerEffectDeltas"]["qb-statistical"],-.05)
    def test_revision_pipeline_emits_scorecard_after_real_final_only(self):
        with tempfile.TemporaryDirectory() as tmp:
            path=Path(tmp)/"forecast-revisions.json"
            entry=original()
            import json
            path.write_text(json.dumps([entry]))
            d={"nextGames":[]}
            ended={"id":"g","home":"BAL","away":"JAX","season":2026,"week":10,
                   "kickoff":K,"home_score":10,"away_score":22}
            revisions(d,[],[ended],K+timedelta(hours=1),path)
            self.assertEqual(d["playerEffectScorecard"]["games"],1)
            self.assertGreater(d["playerEffectScorecard"]["brierGain"],0)
            self.assertFalse(d["playerEffectScorecard"]["calibratedOrApproved"])
if __name__=="__main__":
    unittest.main()
