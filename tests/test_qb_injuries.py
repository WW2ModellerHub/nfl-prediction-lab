import unittest, sys
from datetime import datetime, timedelta, timezone
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
from qb_injuries import (aggregate_qb_plays,QBEngine,dt_value,read_injuries,read_depth_rows,
                         depth_at,injury_context)
from model import generate

T=datetime(2026,11,3,16,tzinfo=timezone.utc)
def game(i,home='BUF',away='MIA',future=False):
    return {'id':f'2026_{i}_{away}_{home}','season':2026,'week':i,'type':'REG',
            'kickoff':T+timedelta(days=7*i),'home':home,'away':away,'neutral':False,
            'home_score':None if future else 21,'away_score':None if future else 17,
            'overtime':False,'closing_spread':None}
def qb_rows(g,team='BUF',qb='QB-001',name='QB Sample',n=20):
    return [{'game_id':g['id'],'posteam':team,'pass':1,'passer_player_id':qb,'passer_player_name':name,
             'pass_attempt':0 if i==n-1 else 1,'complete_pass':int(i%2==0),'passing_yards':6,
             'epa':.2,'cpoe':3,'sack':int(i==n-1),'qb_hit':int(i==n-1),
             'interception':int(i==3)} for i in range(n)]

class PlayerIntelligenceTests(unittest.TestCase):
    def test_aggregate_passer_stats(self):
        g=game(1); result=aggregate_qb_plays(qb_rows(g))
        stats=result[g['id']]['BUF']['QB-001']
        self.assertEqual(stats['dropbacks'],20)
        self.assertEqual(stats['attempts'],19)
        self.assertEqual(stats['completions'],10)
        self.assertEqual(stats['sacks'],1)
        self.assertEqual(stats['hitsOrSacks'],1)
        self.assertEqual(stats['interceptions'],1)
        self.assertAlmostEqual(stats['epaTotal'],4)
    def test_no_future_pbp_inform_current_qb(self):
        a,b=game(1),game(2,future=True)
        plays=aggregate_qb_plays(qb_rows(a))
        e=QBEngine(plays)
        before=e.matchup(a)
        self.assertIsNone(before['home']['qb'])
        e.update(a)
        mid=e.matchup(b)
        self.assertEqual(mid['home']['qb'],'QB Sample')
        self.assertEqual(mid['home']['sample']['games'],1)
        self.assertFalse(mid['home']['confirmedStarter'])
    def test_new_depth_chart_qb_is_change_watch_and_unconfirmed(self):
        a,b=game(1),game(2,future=True)
        e=QBEngine(aggregate_qb_plays(qb_rows(a)));e.update(a)
        depth={'BUF':{'qb':{'name':'Backup Example','id':'QB-002'},'starters':['QB-002']}}
        m=e.matchup(b,depth)
        self.assertTrue(m['home']['starterChangeWatch'])
        self.assertIsNone(m['home']['sample'])
        self.assertFalse(m['home']['confirmedStarter'])
        self.assertEqual(m['probabilityWeight'],0)
    def test_missing_qb_no_fake_stats(self):
        e=QBEngine()
        m=e.matchup(game(2,future=True))
        self.assertEqual(m['status'],'unavailable')
        self.assertIsNone(m['home']['sample'])
    def test_depth_rows_use_latest_prior_snapshot_only(self):
        rows=read_depth_rows([
          {'dt':'2026-11-01T08:00:00Z','team':'BUF','player_name':'Known QB','gsis_id':'P1','pos_abb':'QB','pos_rank':1},
          {'dt':'2026-11-04T08:00:00Z','team':'BUF','player_name':'Later QB','gsis_id':'P2','pos_abb':'QB','pos_rank':1},
          {'dt':'2026-11-01T08:00:00Z','team':'BUF','player_name':'Offensive Tackle','gsis_id':'T1','pos_abb':'T','pos_rank':1}
        ])
        x=depth_at(rows,T)
        self.assertEqual(x['BUF']['qb']['id'],'P1')
        self.assertIn('T1',x['BUF']['starters'])
        self.assertNotIn('P2',x['BUF']['starters'])
    def test_injury_reports_asof_avoid_future_out_status(self):
        fixture=game(2,future=True)
        rows=read_injuries('season,week,team,gsis_id,position,full_name,report_status,practice_status,date_modified,report_primary_injury\n'
           f'2026,2,BUF,P1,QB,Known QB,Questionable,LP,{(fixture["kickoff"]-timedelta(days=2)).isoformat()},Shoulder\n'
           f'2026,2,BUF,P1,QB,Known QB,Out,DNP,{(fixture["kickoff"]+timedelta(hours=2)).isoformat()},Shoulder\n')
        x=injury_context(fixture,rows,{'BUF':{'starters':['P1']}},fixture['kickoff']-timedelta(hours=3))
        self.assertEqual(x['status'],'reported')
        self.assertEqual(x['home'][0]['status'],'Questionable')
        self.assertTrue(x['home'][0]['starterOnDepthChart'])
        self.assertEqual(x['probabilityWeight'],0)
    def test_no_report_is_not_stated_healthy(self):
        x=injury_context(game(2,future=True),[],{},T)
        self.assertEqual(x['status'],'unavailable')
        self.assertIn('No timestamp-verified',x['note'])
        self.assertEqual(x['home'],[])
    def test_synthetic_injury_flags_do_not_change_probability_or_result(self):
        gs=[game(1),game(2),game(3),game(4,future=True)]
        plays={}
        for g in gs[:3]:plays.update(aggregate_qb_plays(qb_rows(g)))
        now=gs[-1]['kickoff']-timedelta(days=3)
        prev,_=generate(gs,now,[],qb_games=plays)
        reports=[{'season':2026,'week':4,'team':'BUF','id':'QB-001','name':'QB Sample','position':'QB',
                  'reportStatus':'Out','practiceStatus':'DNP','injury':'Shoulder',
                  'asOf':now-timedelta(hours=4)}]
        plus,_=generate(gs,now,[],qb_games=plays,injury_rows=reports)
        first,second=prev['nextGames'][0],plus['nextGames'][0]
        self.assertEqual(first['homeProbability'],second['homeProbability'])
        self.assertEqual(first['predHome'],second['predHome'])
        self.assertEqual(second['injuryIntelligence']['home'][0]['status'],'Out')
    def test_forward_qb_data_cannot_leak_into_past_game(self):
        gs=[game(1),game(2),game(3),game(4,future=True)]
        p={g['id']:aggregate_qb_plays(qb_rows(g))[g['id']] for g in gs[:3]}
        now=gs[-1]['kickoff']-timedelta(days=1)
        a,_=generate(gs,now,[],qb_games=p)
        p[gs[-1]['id']]=aggregate_qb_plays(qb_rows(gs[-1],qb='QB-NEW'))[gs[-1]['id']]
        b,_=generate(gs,now,[],qb_games=p)
        self.assertEqual(a['nextGames'][0]['qbIntelligence'],b['nextGames'][0]['qbIntelligence'])
    def test_date_parsing_missing_or_naive(self):
        self.assertIsNone(dt_value(''))
        self.assertEqual(dt_value('2026-11-03T12:00:00Z').tzinfo,timezone.utc)
        self.assertEqual(dt_value('2026-11-03 12:00:00').tzinfo,timezone.utc)

if __name__=='__main__':unittest.main()
