import sys
import unittest
from datetime import datetime,timezone
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
from model import read_games, generate, RatingModel, simulate

HEAD='game_id,season,game_type,week,gameday,gametime,away_team,away_score,home_team,home_score,location\n'
ROWS=[
'2024_01_ATL_CAR,2024,REG,1,2024-09-08,13:00,ATL,14,CAR,28,Home',
'2024_02_CAR_ATL,2024,REG,2,2024-09-15,13:00,CAR,21,ATL,30,Home',
'2026_01_CAR_ATL,2026,REG,1,2026-09-10,20:20,CAR,24,ATL,30,Home',
'2026_02_ATL_CAR,2026,REG,2,2026-11-05,20:15,ATL,,CAR,,Home',
'2026_03_CAR_ATL,2026,REG,3,2026-11-12,20:15,CAR,,ATL,,Home'
]
NOW=datetime(2026,11,2,12,0,tzinfo=timezone.utc)

class ModelTests(unittest.TestCase):
    def setUp(self):self.games=read_games(HEAD+'\n'.join(ROWS)+'\n')
    def test_parse(self):
        self.assertEqual(len(self.games),5)
        self.assertEqual(self.games[0]['away'],'ATL')
        self.assertEqual(self.games[-1]['home_score'],None)
    def test_upcoming_from_actual_prior(self):
        d,log=generate(self.games,NOW,[])
        self.assertEqual(len(d['nextGames']),2)
        self.assertEqual(len(log),2)
        self.assertEqual(d['performance']['count'],3)
        self.assertTrue(0<d['nextGames'][0]['homeProbability']<1)
        self.assertAlmostEqual(d['nextGames'][0]['homeProbability']+d['nextGames'][0]['awayProbability'],1)
    def test_no_future_score_leak(self):
        games2=read_games(HEAD+'\n'.join(ROWS[:-2]+[
         '2026_02_ATL_CAR,2026,REG,2,2026-11-05,20:15,ATL,56,CAR,2,Home',
         '2026_03_CAR_ATL,2026,REG,3,2026-11-12,20:15,CAR,40,ATL,0,Home'])+'\n')
        d1,_=generate(self.games,NOW,[])
        d2,_=generate(games2,NOW,[])
        self.assertEqual([x['homeProbability'] for x in d1['nextGames']],[x['homeProbability'] for x in d2['nextGames']])
    def test_immutable_forward_log(self):
        d,original=generate(self.games,NOW,[])
        d2,again=generate(self.games,NOW,original)
        self.assertEqual(original,again)
        self.assertEqual(len(again),2)
    def test_samples_are_deterministic(self):
        model=RatingModel();p=model.predict(self.games[-1]);a=simulate(self.games[-1],p)
        self.assertEqual(a,simulate(self.games[-1],p))
        self.assertAlmostEqual(sum(x['share'] for x in a),100,delta=.4)
    def test_same_kickoff_does_not_use_other_final(self):
        rows=[
            '2026_01_BUF_KC,2026,REG,1,2026-10-01,13:00,BUF,45,KC,3,Home',
            '2026_01_BAL_PIT,2026,REG,1,2026-10-01,13:00,BAL,24,PIT,19,Home',
            '2026_02_KC_BAL,2026,REG,2,2026-11-05,13:00,KC,,BAL,,Home',
        ]
        swap=[
            '2026_01_BUF_KC,2026,REG,1,2026-10-01,13:00,BUF,3,KC,45,Home',
            '2026_01_BAL_PIT,2026,REG,1,2026-10-01,13:00,BAL,24,PIT,19,Home',
            '2026_02_KC_BAL,2026,REG,2,2026-11-05,13:00,KC,,BAL,,Home',
        ]
        d1,_=generate(read_games(HEAD+'\n'.join(rows)),NOW,[])
        d2,_=generate(read_games(HEAD+'\n'.join(swap)),NOW,[])
        self.assertEqual(d1['recentResults'][0]['homeProbability'],d2['recentResults'][0]['homeProbability'])
        self.assertNotEqual(d1['nextGames'][0]['awayProbability'],d2['nextGames'][0]['awayProbability'])

    def test_after_game_forward_scored_without_mutation(self):
        d,log=generate(self.games,NOW,[])
        later=read_games(HEAD+'\n'.join(ROWS[:-2]+[
        '2026_02_ATL_CAR,2026,REG,2,2026-11-05,20:15,ATL,23,CAR,20,Home',
        ROWS[-1]])+'\n')
        dd,ll=generate(later,datetime(2026,11,8,12,tzinfo=timezone.utc),log)
        self.assertEqual(dd['forwardPerformance']['count'],1)
        self.assertEqual(ll[0]['homeProbability'],log[0]['homeProbability'])
        self.assertEqual(dd['forwardResults'][0]['homeScore'],20)

if __name__=='__main__':unittest.main()
