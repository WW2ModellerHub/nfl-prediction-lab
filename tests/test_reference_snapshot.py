"""Checks that the frozen real-data research snapshot is honestly labelled."""
import json
import unittest
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]

class ReferenceSnapshotTests(unittest.TestCase):
    def setUp(self):
        self.audit=json.loads((ROOT/'data/audit-reference.json').read_text())
        self.games=json.loads((ROOT/'data/reference-slate.json').read_text())
    def test_pinned_snapshot_is_not_live_or_prospective(self):
        self.assertTrue(self.audit['reference'])
        self.assertFalse(self.audit['clvAvailable'])
        self.assertFalse(self.audit['marketIsPregameSnapshot'])
        self.assertFalse(self.audit['ukBookmakersCovered'])
    def test_counts_reconcile_and_no_ties_as_winners(self):
        years=self.audit['seasons'];overall=self.audit['overall']
        self.assertEqual(sum(r['completedGames'] for r in years),overall['completedGames'])
        self.assertEqual(sum(r['ties'] for r in years),overall['ties'])
        self.assertEqual(sum(r['baseline']['games'] for r in years),overall['baseline']['games'])
        self.assertEqual(overall['marketCoverage'],overall['market']['games'])
    def test_reference_market_calibration_has_no_profit_claim(self):
        overall=self.audit['overall']
        self.assertAlmostEqual(overall['modelMinusMarketBrier'],overall['baseline']['brier']-overall['market']['brier'],places=3)
        self.assertGreater(overall['modelMinusMarketBrier'],0)
    def test_research_fixture_sample_is_real_schedule_format_only(self):
        self.assertEqual(len(self.games),15)
        self.assertEqual(len(set(g['id'] for g in self.games)),len(self.games))
        self.assertTrue(all(g['day'].startswith('2026-11-') for g in self.games))
        self.assertTrue(all(0<g['p']<1 for g in self.games))
        self.assertTrue(all(g['away']!=g['home'] for g in self.games))
    def test_refresh_code_never_injects_reference_as_live_data(self):
        src=(ROOT/'scripts/update.py').read_text()
        self.assertNotIn('reference-slate.json',src)
        self.assertNotIn('audit-reference.json',src)

if __name__=='__main__':unittest.main()
