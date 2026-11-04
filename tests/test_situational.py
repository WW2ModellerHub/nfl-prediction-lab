import sys
import unittest
from datetime import datetime, timezone
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
from model import read_games, generate, grade_ats, full_rest_days, situational_context

HEADER='game_id,season,game_type,week,gameday,gametime,away_team,away_score,home_team,home_score,location,overtime,spread_line\n'
NOW=datetime(2026,10,20,12,tzinfo=timezone.utc)

class SituationalTests(unittest.TestCase):
    def games(self,*rows):return read_games(HEADER+'\n'.join(rows)+'\n')
    def test_sunday_ot_to_sunday_six_full_days(self):
        games=self.games(
            '2026_01_BUF_KC,2026,REG,1,2026-10-18,13:00,BUF,31,KC,28,Home,1,3.5',
            '2026_01_MIA_NE,2026,REG,1,2026-10-18,13:00,MIA,14,NE,21,Home,0,7.5',
            '2026_02_BUF_NE,2026,REG,2,2026-10-25,13:00,BUF,,NE,,Home,,')
        d,log=generate(games,NOW,[])
        c=d['nextGames'][0]['situation']
        self.assertEqual(c['away']['fullRestDays'],6)
        self.assertEqual(c['home']['fullRestDays'],6)
        self.assertTrue(any(x['id']=='empty_tank' and x['team']=='BUF' for x in c['signals']))
        self.assertFalse(any(x['id']=='empty_tank' and x['team']=='NE' for x in c['signals']))
        self.assertIn('empty_tank',log[0]['situationalSignals'])
    def test_thursday_road_overtime(self):
        games=self.games(
            '2026_01_BUF_KC,2026,REG,1,2026-10-18,13:00,BUF,31,KC,28,Home,1,3.5',
            '2026_01_MIA_NE,2026,REG,1,2026-10-18,13:00,MIA,14,NE,21,Home,0,7.5',
            '2026_02_KC_NE,2026,REG,2,2026-10-22,20:15,KC,,NE,,Home,,')
        c=generate(games,NOW,[])[0]['nextGames'][0]['situation']
        self.assertEqual(c['away']['fullRestDays'],3)
        self.assertTrue(any(s['id']=='thursday_road_ot' and s['team']=='KC' for s in c['signals']))
        self.assertTrue(any(s['id']=='empty_tank' and s['team']=='KC' for s in c['signals']))
    def test_unknown_overtime_never_assumed_regulation(self):
        games=self.games(
            '2026_01_BUF_KC,2026,REG,1,2026-10-18,13:00,BUF,31,KC,28,Home,1,3.5',
            '2026_01_MIA_NE,2026,REG,1,2026-10-18,13:00,MIA,14,NE,21,Home,,7.5',
            '2026_02_BUF_NE,2026,REG,2,2026-10-25,13:00,BUF,,NE,,Home,,')
        flags=generate(games,NOW,[])[0]['nextGames'][0]['situation']['signals']
        self.assertFalse(any(x['id']=='empty_tank' for x in flags))
    def test_blowout_thresholds(self):
        games=self.games(
            '2026_01_KC_BUF,2026,REG,1,2026-10-18,13:00,KC,0,BUF,28,Home,0,2.5',
            '2026_01_MIA_NE,2026,REG,1,2026-10-18,13:00,MIA,3,NE,40,Home,0,7.5',
            '2026_02_KC_MIA,2026,REG,2,2026-10-25,13:00,KC,,MIA,,Home,,')
        flags=generate(games,NOW,[])[0]['nextGames'][0]['situation']['signals']
        self.assertTrue(any(x['id']=='blowout_bounce' and x['team']=='KC' for x in flags))
        self.assertTrue(any(x['id']=='nuclear_bounce' and x['team']=='MIA' for x in flags))
    def test_closing_line_used_for_grading_only(self):
        g=self.games('2026_02_KC_BUF,2026,REG,2,2026-10-25,13:00,KC,21,BUF,25,Home,0,3.5')[0]
        self.assertEqual(grade_ats(g,'home'),1)
        self.assertEqual(grade_ats(g,'away'),0)
        g['closing_spread']=4
        self.assertEqual(grade_ats(g,'away'),'push')
    def test_situational_does_not_change_win_probability(self):
        ot=self.games(
            '2026_01_BUF_KC,2026,REG,1,2026-10-18,13:00,BUF,31,KC,28,Home,1,3.5',
            '2026_01_MIA_NE,2026,REG,1,2026-10-18,13:00,MIA,14,NE,21,Home,0,7.5',
            '2026_02_BUF_NE,2026,REG,2,2026-10-25,13:00,BUF,,NE,,Home,,')
        regulation=self.games(
            '2026_01_BUF_KC,2026,REG,1,2026-10-18,13:00,BUF,31,KC,28,Home,0,3.5',
            '2026_01_MIA_NE,2026,REG,1,2026-10-18,13:00,MIA,14,NE,21,Home,0,7.5',
            '2026_02_BUF_NE,2026,REG,2,2026-10-25,13:00,BUF,,NE,,Home,,')
        d1,_=generate(ot,NOW,[]);d2,_=generate(regulation,NOW,[])
        self.assertEqual(d1['nextGames'][0]['homeProbability'],d2['nextGames'][0]['homeProbability'])
        self.assertNotEqual(d1['nextGames'][0]['situation']['signals'],d2['nextGames'][0]['situation']['signals'])
    def test_missing_prior_is_not_inferred(self):
        g=self.games('2026_01_KC_BUF,2026,REG,1,2026-10-25,13:00,KC,,BUF,,Home,,')[0]
        c=situational_context(g,{})
        self.assertIsNone(c['home']['fullRestDays'])
        self.assertEqual(c['signals'],[])

if __name__=='__main__':unittest.main()
