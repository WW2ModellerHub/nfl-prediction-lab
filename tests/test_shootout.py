"""Shootout Heat: highest-scoring-game ranking, pregame archive and grading."""
import json, sys, tempfile, unittest
from datetime import datetime, timezone, timedelta
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
from shootout import rate_games, record, summarize, weather_adjustment, tier

NOW = datetime(2026, 11, 21, 12, tzinfo=timezone.utc)


def tac(pass_epa, allowed, expl=.08, expl_allowed=.08):
    side = {'passEPA': pass_epa, 'allowedPassEPA': allowed, 'explosivePass': expl, 'explosiveAllowed': expl_allowed}
    return {'status': 'ready', 'home': dict(side), 'away': dict(side)}


def game(gid, total, pass_epa=.05, allowed=.05, weather=None, week=12, kick=NOW + timedelta(days=1)):
    return {'id': gid, 'season': 2026, 'week': week, 'home': 'H' + gid, 'away': 'A' + gid, 'kickoff': kick.isoformat(),
            'predTotal': total, 'tactical': tac(pass_epa, allowed), 'weather': weather or {'status': 'indoor'}}


class RatingTest(unittest.TestCase):
    def test_projected_total_drives_rating_and_rank(self):
        gs = [game('a', 40), game('b', 50), game('c', 45)]
        self.assertEqual(rate_games(gs), 3)
        self.assertEqual([g['shootout']['weekRank'] for g in gs], [3, 1, 2])
        self.assertGreater(gs[1]['shootout']['rating'], gs[2]['shootout']['rating'])
        for g in gs:
            self.assertTrue(0 <= g['shootout']['rating'] <= 100)
            self.assertNotIn('homeProbability', g)

    def test_passing_matchup_moves_total_relative_to_slate(self):
        gs = [game('a', 45, .20, .20), game('b', 45, -.05, -.05)]
        rate_games(gs)
        self.assertGreater(gs[0]['shootout']['components']['passingMatchup'], 0)
        self.assertLess(gs[1]['shootout']['components']['passingMatchup'], 0)
        self.assertEqual(gs[0]['shootout']['weekRank'], 1)

    def test_weather_penalties_and_indoor_exemption(self):
        pts, why = weather_adjustment({'status': 'forecast', 'windMph': 22, 'precipitationChancePct': 80,
                                       'snowfallCm': 2, 'temperatureC': -8})
        self.assertLess(pts, -8)
        self.assertEqual(len(why), 4)
        self.assertEqual(weather_adjustment({'status': 'indoor', 'windMph': 40}), (0.0, []))
        half, _ = weather_adjustment({'status': 'roof-unconfirmed', 'windMph': 20})
        full, _ = weather_adjustment({'status': 'forecast', 'windMph': 20})
        self.assertAlmostEqual(half, full / 2)
        self.assertEqual(weather_adjustment({'status': 'forecast', 'windMph': 6}), (0.0, []))

    def test_missing_tactical_data_falls_back_to_projected_total(self):
        g = game('a', 47)
        g['tactical'] = {'status': 'insufficient'}
        rate_games([g, game('b', 44)])
        self.assertEqual(g['shootout']['components']['passingMatchup'], 0.0)
        self.assertFalse(g['shootout']['tacticalAvailable'])

    def test_tiers(self):
        self.assertEqual([tier(x) for x in (95, 70, 50, 10)], ['Shootout', 'High', 'Average', 'Low'])


class RecordTest(unittest.TestCase):
    def setUp(self):
        self.dir = tempfile.TemporaryDirectory()
        self.path = Path(self.dir.name) / 'log.json'

    def tearDown(self):
        self.dir.cleanup()

    def test_records_pregame_only_and_keeps_first_timestamp(self):
        gs = [game(x, 40 + i) for i, x in enumerate('abcd')]
        rate_games(gs)
        record(gs, [], NOW, self.path)
        record(gs, [], NOW + timedelta(hours=6), self.path)
        e = json.loads(self.path.read_text())['entries']['a']
        self.assertEqual(e['firstRecordedAt'], NOW.isoformat())
        self.assertEqual(e['recordedAt'], (NOW + timedelta(hours=6)).isoformat())
        # After kickoff the archived pregame rating is frozen.
        gs[0]['shootout']['shootoutTotal'] = 99
        record(gs, [], NOW + timedelta(days=2), self.path)
        self.assertNotEqual(json.loads(self.path.read_text())['entries']['a']['shootoutTotal'], 99)

    def test_grades_finals_against_ranking(self):
        gs = [game(x, 40 + i * 2) for i, x in enumerate('abcde')]
        rate_games(gs)
        record(gs, [], NOW, self.path)
        finals = [{'id': g['id'], 'home_score': 20 + i * 3, 'away_score': 17} for i, g in enumerate(gs)]
        summary = record([], finals, NOW + timedelta(days=3), self.path)
        self.assertEqual(summary['gradedWeeks'], 1)
        self.assertEqual(summary['gradedGames'], 5)
        self.assertEqual(summary['top3HitRate'], 1.0)
        self.assertEqual(summary['meanRankCorrelation'], 1.0)
        self.assertEqual(summary['weeks'][0]['hottest']['game'], 'Ae @ He')
        self.assertEqual(summary['pendingGames'], 0)

    def test_small_weeks_are_not_graded_and_bad_log_is_not_overwritten(self):
        self.assertEqual(summarize({'x': {'week': 1, 'season': 2026, 'actualTotal': 40, 'shootoutTotal': 44,
                                          'projectedTotal': 44, 'rating': 40, 'home': 'H', 'away': 'A'}})['gradedWeeks'], 0)
        self.path.write_text('{"schemaVersion": 99}')
        with self.assertRaises(ValueError):
            record([], [], NOW, self.path)


if __name__ == '__main__':
    unittest.main()
