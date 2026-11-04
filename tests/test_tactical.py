import unittest,sys
from datetime import datetime,timedelta,timezone
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
from tactical import aggregate_plays,TacticalEngine
from tactical_validation import fit,validate,predict
from model import generate

START=datetime(2025,9,1,tzinfo=timezone.utc)
def game(index,home='BUF',away='MIA',season=2025):
    return {'id':f'{season}_{index}_{away}_{home}','season':season,'week':index,'type':'REG',
            'kickoff':START+timedelta(days=7*index),'home':home,'away':away,
            'home_score':21,'away_score':14,'neutral':False,'overtime':False,'closing_spread':None}
def stats(epa=.2):
    return {'pass_count':35,'pass_epa':35*epa,'pass_hit':2,'pass_explosive':4,
            'rush_count':25,'rush_epa':25*epa,'allowed_pass_count':35,
            'allowed_pass_epa':35*epa,'pass_hits_forced':3,'explosive_allowed':2,
            'allowed_rush_count':25,'allowed_rush_epa':25*epa}

class TacticalTests(unittest.TestCase):
    def test_pbp_aggregate_metrics_and_hit_sack_no_double_count(self):
        rows=[{'game_id':'g1','posteam':'BUF','defteam':'MIA','pass':1,'epa':.5,'sack':1,'qb_hit':1,'yards_gained':0},
              {'game_id':'g1','posteam':'BUF','defteam':'MIA','pass':1,'epa':1,'sack':0,'qb_hit':0,'yards_gained':24},
              {'game_id':'g1','posteam':'BUF','defteam':'MIA','rush':1,'epa':-.4,'yards_gained':-2},
              {'game_id':'g1','posteam':'MIA','defteam':'BUF','pass':1,'epa':None},
              {'game_id':'g1','posteam':None,'defteam':'BUF','pass':1,'epa':.2}]
        result=aggregate_plays(rows)['g1']
        self.assertEqual(result['BUF']['pass_count'],2)
        self.assertEqual(result['BUF']['pass_hit'],1)
        self.assertEqual(result['MIA']['pass_hits_forced'],1)
        self.assertEqual(result['BUF']['pass_explosive'],1)
        self.assertEqual(result['BUF']['rush_epa'],-.4)
        self.assertNotIn('pass_count',result['MIA'])
    def test_no_stats_never_makes_fictional_matchup(self):
        engine=TacticalEngine()
        self.assertEqual(engine.matchup(game(5))['status'],'unavailable')
    def test_one_previous_game_insufficient(self):
        g=game(1);engine=TacticalEngine({g['id']:{'BUF':stats(),'MIA':stats()}})
        engine.update(g)
        self.assertEqual(engine.matchup(game(2))['status'],'insufficient')
    def test_matchup_sign_and_rolling_records(self):
        games=[game(i) for i in range(1,6)]
        pbp={g['id']:{'BUF':stats(.35),'MIA':stats(-.3)} for g in games}
        e=TacticalEngine(pbp)
        for g in games:e.update(g)
        m=e.matchup(game(6))
        self.assertEqual(m['status'],'ready')
        self.assertEqual(len(m['features']),4)
        self.assertEqual(m['advantages'][0]['favors'],'BUF')
        self.assertEqual(m['probabilityWeight'],0)
    def test_missing_future_result_never_inserted(self):
        gs=[game(i) for i in range(1,6)]
        pbp={g['id']:{'BUF':stats(),'MIA':stats()} for g in gs}
        e=TacticalEngine(pbp)
        e.update(gs[-1]) # latest data only, intentionally insufficient
        self.assertEqual(e.matchup(gs[0])['status'],'unavailable')
    def test_tactical_overlay_no_history_means_no_adjustment(self):
        gs=[game(i) for i in range(1,7)]
        for g in gs[:-1]:g['home_score']=24;g['away_score']=20
        gs[-1]['home_score']=gs[-1]['away_score']=None
        pbp={g['id']:{'BUF':stats(.3),'MIA':stats(-.2)} for g in gs[:-1]}
        d,_=generate(gs,gs[-1]['kickoff']-timedelta(days=1),[],pbp)
        x=d['nextGames'][0]
        self.assertEqual(x['tactical']['status'],'ready')
        self.assertEqual(d['overlaySelection'],'none')
        self.assertEqual(x['baselineHomeProbability'],x['homeProbability'])
    def test_strength_of_schedule_only_uses_opponent_prior_known_games(self):
        ids=[game(i) for i in range(1,8)]
        e=TacticalEngine({g['id']:{'BUF':stats(.25),'MIA':stats(-.15)} for g in ids})
        for g in ids[:6]:e.update(g)
        context=e.matchup(ids[6])
        self.assertEqual(context['status'],'ready')
        self.assertTrue(context['sosAdjustmentApplied'])
        self.assertIsNotNone(context['home']['adjustedPassEPA'])
        self.assertNotEqual(context['home']['adjustedPassEPA'],context['home']['passEPA'])
    def test_same_kickoff_games_do_not_leak_pbp(self):
        games=[game(i) for i in range(1,7)]
        for g in games: g['home_score']=22;g['away_score']=13
        current=game(7);current['home_score']=current['away_score']=None
        games.append(current)
        pbp={g['id']:{'BUF':stats(.12),'MIA':stats(.02)} for g in games[:-1]}
        now=current['kickoff']-timedelta(hours=3)
        before,_=generate(games,now,[],pbp)
        pbp[current['id']]={'BUF':stats(5000),'MIA':stats(-5000)}
        after,_=generate(games,now,[],pbp)
        self.assertEqual(before['nextGames'][0]['tactical'],after['nextGames'][0]['tactical'])
    def test_future_pbp_does_not_change_past_forecasts(self):
        gs=[game(i) for i in range(1,7)];gs[-1]['home_score']=gs[-1]['away_score']=None
        pbp={g['id']:{'BUF':stats(.1),'MIA':stats(.1)} for g in gs[:-1]}
        now=gs[-1]['kickoff']-timedelta(days=1)
        one,_=generate(gs,now,[],pbp)
        pbp[gs[-1]['id']]={'BUF':stats(100),'MIA':stats(-100)}
        two,_=generate(gs,now,[],pbp)
        self.assertEqual(one['nextGames'][0]['tactical'],two['nextGames'][0]['tactical'])
    def test_future_season_not_used_for_tactical_training(self):
        rows=[]
        for season in range(2021,2027):
            for i in range(220):
                rows.append({'season':season,'p':.5,'features':[1,-1,.2,.3],'y':i%2})
        x=validate(rows,2026)
        y=validate([r for r in rows if r['season']!=2026],2026)
        self.assertEqual(x,y)
        self.assertEqual(x['trainedThroughSeason'],2025)
    def test_no_rows_cannot_activate(self):
        v=validate([],2026)
        self.assertFalse(v['enabled'])
        self.assertEqual(sum(abs(x) for x in v['coefficients'].values()),0)
    def test_prediction_stable_zero_weights(self):
        self.assertAlmostEqual(predict(.67,[1,2,-1,.5],[0,0,0,0]),.67)

if __name__=='__main__':unittest.main()
