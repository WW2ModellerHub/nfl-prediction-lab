"""Provisional QB/injury model: strictly before kickoff, no fictional status."""
from datetime import datetime, timezone, timedelta
import sys
import unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/"scripts"))
from personnel_adjustment import assess

NOW=datetime(2026,11,5,15,tzinfo=timezone.utc)
def item(name,pos,status,usage=None,at=NOW):
    return {"name":name,"position":pos,"status":status,"reportDate":at.isoformat(),
            "recentUsage":usage or {}}
def fixture():
    return {"id":"qb_test","home":"BAL","away":"JAX","kickoff":(NOW+timedelta(days=1)).isoformat(),
      "homeProbability":.55,"baselineHomeProbability":.55,
      "qbIntelligence":{"home":{"qb":"Reserve Backup","basis":"depth_chart_projection","lastGameLeader":{"name":"Starter A"}},
                         "away":{"qb":"Starter B","basis":"depth_chart_projection","lastGameLeader":{"name":"Starter B"}}},
      "personnelDepthChart":{"home":{"asOf":(NOW-timedelta(days=1)).isoformat()},
                             "away":{"asOf":(NOW-timedelta(days=1)).isoformat()}},
      "supplementalInjuryWatch":{"status":"loaded","retrievedAt":NOW.isoformat(),
                                "home":[item("Starter A","QB","Out")],"away":[]}}
class PersonnelTests(unittest.TestCase):
    def test_starter_out_and_new_qb_moves_probability_against_team(self):
        g=fixture()
        v=assess(g,NOW)
        self.assertTrue(v["affectsPrediction"])
        self.assertLess(v["homeProbability"],g["homeProbability"])
        self.assertEqual(v["homeMissingPoints"],3.5)
        self.assertEqual(v["factors"][0]["kind"],"qb")
        self.assertFalse(v["validated"])
        self.assertEqual(g["homeProbability"],.55)

    def test_uncertain_status_never_assumed_out(self):
        g=fixture();g["supplementalInjuryWatch"]["home"]=[item("Starter A","QB","Questionable")]
        g["qbIntelligence"]["home"]["qb"]="Starter A"
        v=assess(g,NOW)
        self.assertFalse(v["affectsPrediction"])
        self.assertEqual(v["homeProbability"],.55)
        self.assertTrue(v["warnings"])

    def test_stale_and_future_reports_ignored(self):
        for at in (NOW-timedelta(days=12),NOW+timedelta(minutes=10)):
            g=fixture();g["supplementalInjuryWatch"]["home"]=[item("Starter A","QB","Out",at=at)]
            g["qbIntelligence"]["home"]["qb"]="Starter A"
            v=assess(g,NOW)
            self.assertFalse(v["affectsPrediction"])

    def test_missing_cached_espn_does_not_change_probability(self):
        g=fixture();g["supplementalInjuryWatch"]["status"]="cached"
        self.assertFalse(assess(g,NOW)["affectsPrediction"])

    def test_do_not_touch_started_game(self):
        g=fixture();g["kickoff"]=(NOW-timedelta(minutes=1)).isoformat()
        self.assertFalse(assess(g,NOW)["affectsPrediction"])

    def test_high_usage_absence_adjustment_and_cap(self):
        g=fixture();g["qbIntelligence"]["home"]["qb"]="Starter A"
        g["supplementalInjuryWatch"]["home"]=[
            item(f"WR{i}","WR","Out",{"offensePct":.9}) for i in range(9)]
        s=assess(g,NOW)
        self.assertEqual(s["homeMissingPoints"],1.4)
        self.assertLess(s["homeProbability"],.55)

    def test_no_snap_data_means_no_non_qb_penalty(self):
        g=fixture();g["qbIntelligence"]["home"]["qb"]="Starter A"
        g["supplementalInjuryWatch"]["home"]=[item("Other","CB","Out")]
        self.assertEqual(assess(g,NOW)["homeProbability"],.55)

if __name__=="__main__":unittest.main()
