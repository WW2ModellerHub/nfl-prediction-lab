"""Regression checks for model registry presentation and honest model statuses."""
import unittest
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
APP=(ROOT/'assets/app.js').read_text(encoding='utf-8')

class RegistryContractTests(unittest.TestCase):
    def test_known_models_are_visible(self):
        for text in ('M01','M08','M10','M15','M20','XGBoost multi-factor challenger',
                     'Player snap participation','Stadium-area weather',
                     'Closing-market benchmark','Immutable forward-test tracker'):
            with self.subTest(text=text): self.assertIn(text,APP)

    def test_filters_are_wired(self):
        self.assertIn('data-model-filter',APP)
        self.assertIn('store.modelFilter=btn.dataset.modelFilter;render();return;',APP)
        self.assertIn("const shown=filter==='all'?models:",APP)

    def test_challenger_is_shadow_only(self):
        self.assertIn("name:'XGBoost multi-factor challenger',category:'forecast',state:'SHADOW'",APP)
        self.assertIn('0% live weighting.',APP)
        self.assertIn('Only ACTIVE components are allowed to change displayed probabilities',APP)

    def test_registry_uses_real_pipeline_fields(self):
        for field in ('d.qbValidation','d.challengerValidation','d.shadowForwardPerformance',
                      'd.playerUsageSource','d.weatherSource','d.tacticalValidation',
                      'd.injurySource','d.additionalInjurySource'):
            with self.subTest(field=field): self.assertIn(field,APP)

    def test_fixture_dossier_renderer_is_preserved(self):
        self.assertIn('function fullMatchupReport(g)',APP)
        self.assertIn('function openGame(id)',APP)

if __name__=='__main__':
    unittest.main()
