"""Sleeper depth charts as the independent QB1 cross-check."""
import sys, io, json, unittest
from datetime import datetime, timezone, timedelta
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
from sleeper_depth import team_qbs, qb1, fetch, attach, clean_name
from pregame_verification import evaluate

NOW = datetime(2026, 11, 14, 12, tzinfo=timezone.utc)
KICK = (NOW + timedelta(days=1)).isoformat()


def p(pid, name, team, order, injury=None, pos='QB', gsis=None, active=True):
    return {'player_id': pid, 'full_name': name, 'team': team, 'position': pos, 'depth_chart_position': pos,
            'depth_chart_order': order, 'injury_status': injury, 'gsis_id': gsis, 'active': active}


PLAYERS = {x['player_id']: x for x in [
    p('1', 'Jared Goff', 'DET', 1, gsis='00-1'), p('2', 'Kyle Allen', 'DET', 2),
    p('3', 'Drake Maye', 'NE', 1), p('4', 'Josh Dobbs', 'NE', 2),
    p('5', 'Matthew Stafford', 'LAR', 1, injury='Out'), p('6', 'Jimmy Garoppolo', 'LAR', 2),
    p('7', 'Tied One', 'NYG', 1), p('8', 'Tied Two', 'NYG', 1),
    p('9', 'Amon-Ra St. Brown', 'DET', 1, pos='WR'), p('10', 'Free Agent', None, None),
    p('11', 'Retired QB', 'DET', 3, active=False)]}


class Resp(io.BytesIO):
    def __enter__(self): return self
    def __exit__(self, *a): return False


def game(home_qb='Jared Goff', away_qb='Drake Maye', home='DET', away='NE'):
    q = lambda name: {'qb': name, 'basis': 'depth_chart_projection'}
    src = lambda name: {'nflverseFresh': True, 'nflverseProjectedQB': name, 'espnProjectedQB': name,
                        'sourcesAgree': True, 'nflverseAsOf': NOW.isoformat(), 'espnObservedAt': NOW.isoformat(),
                        'independentConfirmation': False}
    rows = {'isWeeklyReportAvailable': True, 'qbs': [], 'rows': [{'reportDate': NOW.isoformat()}]}
    return {'id': 'g', 'kickoff': KICK, 'home': home, 'away': away, 'homeProbability': .55,
            'qbIntelligence': {'home': q(home_qb), 'away': q(away_qb)},
            'qbSourceEvidence': {'home': src(home_qb), 'away': src(away_qb)},
            'officialInjuryEvidence': {'status': 'loaded', 'home': dict(rows), 'away': dict(rows)},
            'supplementalInjuryWatch': {'status': 'loaded', 'home': [], 'away': []}}


class SleeperParsingTest(unittest.TestCase):
    def test_groups_qbs_by_nflverse_team_in_depth_order(self):
        t = team_qbs(PLAYERS)
        self.assertEqual([r['name'] for r in t['DET']], ['Jared Goff', 'Kyle Allen'])
        self.assertIn('LA', t)
        self.assertNotIn('LAR', t)

    def test_qb1_skips_unavailable_and_rejects_ties(self):
        t = team_qbs(PLAYERS)
        starter, listed = qb1(t['LA'])
        self.assertEqual(starter['name'], 'Jimmy Garoppolo')
        self.assertEqual(listed['name'], 'Matthew Stafford')
        self.assertIsNone(qb1(t['NYG'])[0])
        self.assertEqual(qb1([]), (None, None))

    def test_name_matching_ignores_suffix_and_punctuation(self):
        self.assertEqual(clean_name('Michael Penix Jr.'), clean_name('Michael Penix'))

    def test_fetch_success_and_failure_never_raise(self):
        teams, meta = fetch(NOW, opener=lambda req, timeout: Resp(json.dumps(PLAYERS).encode()))
        self.assertEqual(meta['status'], 'loaded')
        self.assertEqual(meta['observedAt'], NOW.isoformat())
        self.assertIn('DET', teams)
        def boom(req, timeout): raise OSError('blocked')
        teams, meta = fetch(NOW, opener=boom)
        self.assertEqual((teams, meta['status']), ({}, 'unavailable'))
        self.assertTrue(meta['errors'])


class SleeperGateTest(unittest.TestCase):
    def run_gate(self, g, players=PLAYERS, observed=NOW):
        teams = team_qbs(players)
        attach(g, teams, {'status': 'loaded', 'observedAt': observed.isoformat()}, NOW)
        return evaluate(g, NOW)

    def test_independent_match_promotes_to_checked(self):
        g = game()
        v = self.run_gate(g)
        self.assertEqual(v['level'], 'checked', v['reviewReasons'])
        self.assertTrue(v['bettingEligible'])
        self.assertEqual(v['teamChecks'][0]['qbProjectionStatus'], 'independently-corroborated')
        self.assertEqual(v['teamChecks'][0]['sleeperQB'], 'Jared Goff')
        self.assertFalse(v['teamChecks'][0]['starterOfficiallyConfirmed'])
        self.assertEqual(g['homeProbability'], .55)

    def test_disagreement_stays_in_review_with_reason(self):
        v = self.run_gate(game(home_qb='Kyle Allen'))
        self.assertEqual(v['level'], 'review')
        self.assertTrue(any('Sleeper depth chart lists Jared Goff' in r for r in v['reviewReasons']))

    def test_projected_qb_reported_out_by_sleeper_is_not_checked(self):
        v = self.run_gate(game(home='LA', home_qb='Matthew Stafford'))
        self.assertEqual(v['level'], 'review')
        self.assertTrue(any('as OUT' in r for r in v['reviewReasons']))

    def test_stale_or_missing_sleeper_does_not_corroborate(self):
        v = self.run_gate(game(), observed=NOW - timedelta(hours=80))
        self.assertEqual(v['level'], 'review')
        g = game()
        attach(g, {}, {'status': 'unavailable'}, NOW)
        v = evaluate(g, NOW)
        self.assertEqual(v['level'], 'review')
        self.assertTrue(any('Sleeper depth chart unavailable' in r for r in v['reviewReasons']))

    def test_ambiguous_sleeper_chart_is_not_evidence(self):
        v = self.run_gate(game(home='NYG', home_qb='Tied One'))
        self.assertEqual(v['level'], 'review')

    def test_existing_hold_rules_still_win(self):
        g = game()
        g['qbSourceEvidence']['home']['sourceConflict'] = True
        self.assertEqual(self.run_gate(g)['level'], 'hold')


if __name__ == '__main__':
    unittest.main()
