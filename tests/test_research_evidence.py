import json
import unittest
from pathlib import Path

DATA=Path(__file__).resolve().parents[1]/'data/situational-research.json'

class HistoricalResearchEvidenceTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.r=json.loads(DATA.read_text())

    def test_research_sample_and_years_consistent(self):
        r=self.r
        self.assertEqual(sum(y['n'] for y in r['seasonResults']), r['holdoutGames'])
        self.assertEqual(r['holdoutGames'],688)
        self.assertEqual(r['selectionGames'],sum(y['n'] for y in r['seasonResults'] if y['season']<2026))

    def test_gate_off_after_failed_complete_seasons(self):
        r=self.r
        self.assertFalse(r['gate']['enabled'])
        for year in (2024,2025):
            y=next(y for y in r['seasonResults'] if y['season']==year)
            self.assertGreater(y['situationalBrier'],y['baselineBrier'])

    def test_no_claim_of_advanced_metrics(self):
        r=self.r
        self.assertEqual(len(r['strategySignals']),6)
        self.assertTrue(any('play-by-play' in s for s in r['outstanding']))
        self.assertTrue(any('production' in s for s in r['outstanding']))

    def test_ats_rates_have_consistent_denominators(self):
        for s in self.r['strategySignals']:
            for group,rate in (('train',s['trainATSPct']),('test',s['testATSPct'])):
                w,l,p=s[group]
                self.assertGreaterEqual(p,0)
                self.assertGreater(w+l,0)
                self.assertAlmostEqual(100*w/(w+l),rate,delta=.06)

if __name__=='__main__':unittest.main()
