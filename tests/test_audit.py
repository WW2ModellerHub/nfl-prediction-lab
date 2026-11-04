"""Historical closing-market audit and no-betting-leakage regression tests."""
import unittest,sys
from datetime import datetime,timezone
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
from audit import american_probability,no_vig_home_probability,build_audit
from model import read_games,generate
from update import get_schedule
from tempfile import TemporaryDirectory

class HistoricalAuditTests(unittest.TestCase):
    def test_american_probabilities(self):
        self.assertAlmostEqual(american_probability(-150),.6)
        self.assertAlmostEqual(american_probability(200),1/3)
        self.assertIsNone(american_probability(None))
        self.assertIsNone(american_probability(0))
    def test_no_vig_removes_both_sides_margin(self):
        self.assertAlmostEqual(no_vig_home_probability(-110,-110),.5)
        self.assertGreater(no_vig_home_probability(-150,130),.5)
        self.assertIsNone(no_vig_home_probability(-120,None))
    def sample(self,season,p,y,home_odds=-110,away_odds=-110,week=1):
        return {'season':season,'week':week,'homeProbability':p,'outcome':y,
                'closingHomeMoneyline':home_odds,'closingAwayMoneyline':away_odds}
    def test_brier_compares_on_same_eligible_games(self):
        a=build_audit([self.sample(2024,.6,1),self.sample(2024,.4,0,home_odds=None)],'2026-11-03')
        x=a['overall'];self.assertEqual(x['baseline']['games'],2)
        self.assertEqual(x['market']['games'],1)
        self.assertEqual(x['baselineOnMarketMatchedGames']['games'],1)
        self.assertAlmostEqual(x['modelMinusMarketBrier'],.16-.25,places=4)
    def test_ties_cannot_fabricate_market_winners(self):
        x=build_audit([self.sample(2025,.6,.5)],'2026-11-03')['overall']
        self.assertEqual(x['ties'],1)
        self.assertEqual(x['marketCoverage'],0)
        self.assertIsNone(x['modelMinusMarketBrier'])
    def test_week_bootstrap_deterministic(self):
        rows=[self.sample(2025,.1+(i%5)*.15,i%2,week=i+1) for i in range(14)]
        x=build_audit(rows)['overall']['modelMinusMarketBrier95CI']
        self.assertEqual(x,build_audit(rows)['overall']['modelMinusMarketBrier95CI'])
        self.assertEqual(len(x),2)
    def test_closing_odds_never_change_predicted_probabilities(self):
        head='game_id,season,game_type,week,gameday,gametime,away_team,away_score,home_team,home_score,location,home_moneyline,away_moneyline\n'
        g1='2026_01_BUF_KC,2026,REG,1,2026-10-01,13:00,BUF,21,KC,31,Home,-160,140\n'
        g2='2026_02_KC_BAL,2026,REG,2,2026-11-08,13:00,KC,,BAL,,Home,,\n'
        d,_=generate(read_games(head+g1+g2),datetime(2026,11,3,tzinfo=timezone.utc),[])
        alternate=g1.replace('-160,140','+900,-2000')
        dd,_=generate(read_games(head+alternate+g2),datetime(2026,11,3,tzinfo=timezone.utc),[])
        self.assertEqual(d['nextGames'][0]['homeProbability'],dd['nextGames'][0]['homeProbability'])
        self.assertNotEqual(d['historicalAudit']['overall']['market']['brier'],dd['historicalAudit']['overall']['market']['brier'])
    def test_bad_local_source_is_rejected(self):
        with TemporaryDirectory() as temp:
            path=Path(temp)/'games.csv';path.write_text('bad,source\n')
            with self.assertRaises(RuntimeError):get_schedule(str(path))

if __name__=='__main__':unittest.main()

class MissingLiveFeedTests(unittest.TestCase):
    def test_unscored_started_game_is_not_advertised_as_pregame(self):
        head='game_id,season,game_type,week,gameday,gametime,away_team,away_score,home_team,home_score,location\n'
        rows='2026_03_BUF_KC,2026,REG,3,2026-11-03,15:00,BUF,,KC,,Home\n'
        games=read_games(head+rows)
        data,log=generate(games,datetime(2026,11,3,21,tzinfo=timezone.utc),[])
        self.assertEqual(data['nextGames'],[])
        self.assertEqual(log,[])
