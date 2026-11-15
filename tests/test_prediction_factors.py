"""Started games keep the full pregame factor set behind their frozen pick."""
import json, sys, unittest
from pathlib import Path
from datetime import datetime, timezone, timedelta
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
from prediction_factors import factor_snapshot, attach_pregame_factors

KICK = datetime(2026, 11, 15, 18, tzinfo=timezone.utc)
ROW = {'id': 'g', 'home': 'NYJ', 'away': 'BUF', 'kickoff': KICK.isoformat(),
       'stadium': 'MetLife Stadium', 'roof': 'outdoors', 'neutral': False, 'homeAdvantageElo': 55,
       'eloHome': 1344, 'eloAway': 1666, 'formHome': 20.4, 'formAway': 26.9, 'allowedHome': 25.7, 'allowedAway': 21.2,
       'qbIntelligence': {'status': 'observed', 'home': {'qb': 'Geno Smith', 'basis': 'depth_chart_projection',
           'sample': {'epaPerDropback': 0.044, 'games': 8, 'cpoe': 2.4}, 'primaryStarter': {'big': 'x'}}},
       'injuryIntelligence': {'status': 'reported', 'home': [{'name': f'P{i}', 'status': 'Out', 'position': 'LB',
           'practice': 'DNP', 'id': i} for i in range(30)], 'away': []},
       'supplementalInjuryWatch': {'status': 'loaded', 'away': [{'name': 'Spencer Brown', 'status': 'Doubtful',
           'position': 'OFFENSIVE TACKLE', 'recentUsage': {'offensePct': .74, 'games': 3}}]},
       'situation': {'home': {'fullRestDays': 6}, 'away': {'fullRestDays': 5}, 'signals': []},
       'tactical': {'status': 'ready', 'advantages': [], 'home': {'passEPA': .05, 'rushEPA': -.1, 'lastGameDate': 'x'}},
       'weather': {'status': 'forecast', 'temperatureC': 8.2, 'windMph': 10.5},
       'forecastExplanation': {'layers': [{'key': 'elo', 'applied': True, 'deltaHome': -.19, 'explanation': 'long'}]},
       'forecastQuality': {'level': 'review', 'teamChecks': [1, 2]}}


def recent():
    return [{'id': 'g', 'home': 'NYJ', 'away': 'BUF', 'kickoff': KICK.isoformat(), 'archivedPregame': True}]


class PredictionFactorsTest(unittest.TestCase):
    def test_snapshot_keeps_every_factor_and_trims_bulk(self):
        s = factor_snapshot(ROW)
        for key in ('stadium', 'neutral', 'eloHome', 'formAway', 'qbIntelligence', 'injuryIntelligence',
                    'supplementalInjuryWatch', 'situation', 'tactical', 'weather', 'forecastExplanation'):
            self.assertIn(key, s)
        self.assertEqual(s['qbIntelligence']['home']['qb'], 'Geno Smith')
        self.assertNotIn('primaryStarter', s['qbIntelligence']['home'])
        self.assertNotIn('cpoe', s['qbIntelligence']['home']['sample'])
        self.assertLessEqual(len(s['injuryIntelligence']['home']), 14)
        self.assertNotIn('practice', s['injuryIntelligence']['home'][0])
        self.assertEqual(s['supplementalInjuryWatch']['away'][0]['recentUsage'], {'offensePct': .74})
        self.assertEqual(s['forecastExplanation']['layers'][0], {'key': 'elo', 'applied': True, 'deltaHome': -.19})
        self.assertEqual(s['forecastQuality'], {'level': 'review'})
        json.dumps(s)

    def test_attaches_only_from_dashboard_generated_before_kickoff(self):
        rows = recent()
        old = {'generatedAt': (KICK - timedelta(hours=2)).isoformat(), 'nextGames': [ROW]}
        self.assertEqual(attach_pregame_factors(rows, old), 1)
        self.assertEqual(rows[0]['pregame']['eloAway'], 1666)
        self.assertEqual(rows[0]['pregame']['capturedAt'], old['generatedAt'])
        late = recent()
        self.assertEqual(attach_pregame_factors(late, {'generatedAt': (KICK + timedelta(minutes=1)).isoformat(),
                                                      'nextGames': [ROW]}), 0)
        self.assertNotIn('pregame', late[0])

    def test_mismatched_fixture_is_ignored(self):
        rows = recent()
        old = {'generatedAt': (KICK - timedelta(hours=2)).isoformat(), 'nextGames': [{**ROW, 'away': 'MIA'}]}
        self.assertEqual(attach_pregame_factors(rows, old), 0)
        moved = recent()
        old = {'generatedAt': (KICK - timedelta(hours=2)).isoformat(),
               'nextGames': [{**ROW, 'kickoff': (KICK + timedelta(days=1)).isoformat()}]}
        self.assertEqual(attach_pregame_factors(moved, old), 0)

    def test_snapshot_carries_forward_across_later_refreshes(self):
        carried = {'eloAway': 1666, 'capturedAt': 'before'}
        rows = recent()
        old = {'generatedAt': (KICK + timedelta(hours=3)).isoformat(), 'nextGames': [],
               'recentKickoffs': [{'id': 'g', 'pregame': carried}]}
        self.assertEqual(attach_pregame_factors(rows, old), 1)
        self.assertEqual(rows[0]['pregame'], carried)

    def test_missing_previous_dashboard_is_safe(self):
        rows = recent()
        self.assertEqual(attach_pregame_factors(rows, None), 0)
        self.assertEqual(attach_pregame_factors(rows, {}), 0)


if __name__ == '__main__':
    unittest.main()
