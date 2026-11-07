"""The displayed one-number forecast must reconcile to its actual weighted layers."""
import math
import sys
import unittest
from pathlib import Path

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/"scripts"))
from forecast_layers import explain

def fixture(**changes):
    g={"home":"BAL","away":"JAX","homeProbability":.55,
       "baselineHomeProbability":.55,"prePersonnelProbability":.55,
       "eloModelProbability":.65,"formModelProbability":.40,
       "overlayType":"none","adjustmentActive":False,
       "personnelScenario":{"qbStatisticalHomeDelta":0.,
                            "qbReplacementHomeDelta":0.,
                            "injuryHomeDelta":0.}}
    g.update(changes)
    return g

def layer(e,key):
    return next(x for x in e["layers"] if x["key"]==key)

class ForecastAttributionTests(unittest.TestCase):
    def test_elo_and_form_account_for_actual_weighted_probability(self):
        e=explain(fixture())
        self.assertTrue(e["reconciles"])
        self.assertEqual(e["status"],"model-derived")
        self.assertEqual(e["homeProbability"],.55)
        self.assertAlmostEqual(layer(e,"elo")["deltaHome"],.09)
        self.assertAlmostEqual(layer(e,"form")["deltaHome"],-.04)
        self.assertAlmostEqual(layer(e,"form")["afterHome"],.55)
        self.assertFalse(layer(e,"tactical")["applied"])
        self.assertIsNone(layer(e,"tactical")["deltaHome"])
        self.assertFalse(layer(e,"qb-replacement")["applied"])
        self.assertFalse(layer(e,"weather")["applied"])
        self.assertIsNone(layer(e,"weather")["deltaHome"])
        self.assertEqual(e["winner"],"BAL")
        self.assertEqual(e["winnerProbability"],.55)

    def test_chronological_all_active_layer_math_and_provisional_label(self):
        g=fixture(homeProbability=.45,prePersonnelProbability=.57,
            overlayType="situational",adjustmentActive=True,
            personnelScenario={"qbStatisticalHomeDelta":-.03,
                               "qbReplacementHomeDelta":-.07,
                               "injuryHomeDelta":-.02})
        e=explain(g)
        self.assertTrue(e["reconciles"])
        self.assertEqual(e["winner"],"JAX")
        self.assertEqual(e["winnerProbability"],.55)
        self.assertEqual(e["selectedOverlay"],"situational")
        self.assertAlmostEqual(layer(e,"situational")["deltaHome"],.02)
        self.assertAlmostEqual(layer(e,"qb-statistical")["deltaHome"],-.03)
        self.assertAlmostEqual(layer(e,"qb-replacement")["deltaHome"],-.07)
        self.assertAlmostEqual(layer(e,"other-injuries")["deltaHome"],-.02)
        self.assertEqual(e["status"],"provisional")
        self.assertFalse(any(x["key"]=="unattributed" for x in e["layers"]))
        self.assertAlmostEqual(.5+sum(x["deltaHome"] for x in e["layers"] if x["applied"]),.45,places=6)

    def test_historically_selected_layer_without_provisional_players(self):
        g=fixture(homeProbability=.59,prePersonnelProbability=.59,
            overlayType="tactical",adjustmentActive=True)
        e=explain(g)
        self.assertEqual(e["status"],"model-derived")
        self.assertAlmostEqual(layer(e,"tactical")["deltaHome"],.04)
        self.assertEqual(layer(e,"tactical")["kind"],"validated")
        self.assertEqual(e["homeProbability"],.59)
        self.assertFalse(layer(e,"situational")["applied"])

    def test_absent_components_never_become_fabricated_zero(self):
        g=fixture(homeProbability=.50,baselineHomeProbability=.55,
                  prePersonnelProbability=.55,personnelScenario={})
        e=explain(g)
        self.assertTrue(e["reconciles"])
        self.assertEqual(e["status"],"partially-unverified")
        self.assertAlmostEqual(layer(e,"unattributed")["deltaHome"],-.05)
        self.assertEqual(layer(e,"unattributed")["kind"],"unverified")
        self.assertIsNone(layer(e,"qb-replacement")["deltaHome"])
        self.assertFalse(layer(e,"qb-replacement")["applied"])
        self.assertTrue(e["warnings"])

    def test_no_individual_elo_and_form_vote_is_falsified(self):
        g=fixture(eloModelProbability=None,formModelProbability=None)
        e=explain(g)
        self.assertAlmostEqual(layer(e,"core")["deltaHome"],.05)
        self.assertFalse(any(x["key"]=="elo" for x in e["layers"]))
        self.assertTrue(e["reconciles"])
        self.assertIn("Elo/form",e["warnings"][0])

    def test_probability_bound_is_separate_from_elo_and_form(self):
        g=fixture(homeProbability=.95,baselineHomeProbability=.95,
                  prePersonnelProbability=.95,eloModelProbability=.99,
                  formModelProbability=.99)
        e=explain(g)
        self.assertAlmostEqual(layer(e,"bounds")["deltaHome"],-.04)
        self.assertEqual(e["homeProbability"],.95)
        self.assertTrue(e["reconciles"])

    def test_almost_invisible_transport_rounding_not_fake_adjustment(self):
        g=fixture(homeProbability=.55,baselineHomeProbability=.55,
                  eloModelProbability=.65003,formModelProbability=.4)
        e=explain(g)
        self.assertTrue(e["reconciles"])
        self.assertNotIn("unattributed",[x["key"] for x in e["layers"]])
        self.assertAlmostEqual(layer(e,"form")["afterHome"],.55,places=6)

    def test_unselected_overlay_is_not_claimed_to_move_percentage(self):
        g=fixture(overlayType="situational",adjustmentActive=False)
        e=explain(g)
        self.assertEqual(e["selectedOverlay"],"none")
        self.assertIsNone(layer(e,"situational")["deltaHome"])
        self.assertFalse(layer(e,"situational")["applied"])

    def test_invalid_input_fails_closed(self):
        e=explain({"home":"BAL","away":"JAX","homeProbability":float('nan')})
        self.assertEqual(e["status"],"unavailable")
        self.assertFalse(e["reconciles"])
        self.assertEqual(e["layers"],[])

    def test_named_absences_with_no_adjustment_not_presented_as_evaluated_zero(self):
        g=fixture(personnelScenario={"status":"no-documented-replacement",
                                     "qbStatisticalHomeDelta":0,
                                     "qbReplacementHomeDelta":0,
                                     "injuryHomeDelta":0})
        e=explain(g)
        self.assertFalse(layer(e,"qb-replacement")["applied"])
        self.assertIsNone(layer(e,"qb-replacement")["deltaHome"])
        self.assertTrue(e["reconciles"])

if __name__=="__main__":
    unittest.main()
