"""Regression tests for historical QB fallback and cached player observations."""
import sys
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
from model import read_games,generate
from update import preserve_recent_player_context

NOW=datetime(2026,11,4,19,tzinfo=timezone.utc)
HEADER='game_id,season,game_type,week,gameday,gametime,away_team,away_score,home_team,home_score,location,home_qb_name,away_qb_name,home_qb_id,away_qb_id\n'
ROWS=[
'2026_07_ATL_CIN,2026,REG,7,2026-10-26,13:00,ATL,14,CIN,28,Home,Joe Burrow,Michael Penix Jr.,00-0036442,00-0039917',
'2026_08_CIN_ATL,2026,REG,8,2026-11-01,13:00,CIN,20,ATL,17,Home,Michael Penix Jr.,Joe Burrow,00-0039917,00-0036442',
'2026_09_CIN_ATL,2026,REG,9,2026-11-08,13:00,CIN,,ATL,,Home,,,,'
]

class PlayerFeedResilienceTests(unittest.TestCase):
    def test_schedule_provides_unconfirmed_last_game_starter_without_pbp(self):
        games=read_games(HEADER+'\n'.join(ROWS)+'\n')
        self.assertEqual(games[1]['home_qb_name'],'Michael Penix Jr.')
        data,_=generate(games,NOW,[])
        qb=data['nextGames'][0]['qbIntelligence']
        self.assertEqual(qb['home']['qb'],'Michael Penix Jr.')
        self.assertEqual(qb['away']['qb'],'Joe Burrow')
        self.assertEqual(qb['home']['basis'],'last_game_recorded_starter')
        self.assertFalse(qb['home']['confirmedStarter'])
        self.assertIsNone(qb['home']['sample'])

    def test_future_game_qb_fields_cannot_leak_back(self):
        original,_=generate(read_games(HEADER+'\n'.join(ROWS)+'\n'),NOW,[])
        amended=ROWS[:-1]+[ROWS[-1][:-4]+'Future Name,,,']
        changed,_=generate(read_games(HEADER+'\n'.join(amended)+'\n'),NOW,[])
        self.assertEqual(original['nextGames'][0]['qbIntelligence'],
                         changed['nextGames'][0]['qbIntelligence'])

    def test_light_refresh_caches_only_recent_same_fixture(self):
        oldtime=NOW-timedelta(hours=3)
        previous={'generatedAt':oldtime.isoformat(),
           'nextGames':[{'id':'x','kickoff':'2026-11-08T18:00:00+00:00',
              'qbIntelligence':{'status':'observed','home':{'qb':'QB A','basis':'depth_chart_projection','sample':{'games':3}},'away':{}},
              'tactical':{'status':'ready','advantages':[]},
              'injuryIntelligence':{'status':'reported','reportAsOf':oldtime.isoformat(),'home':[{'name':'Player A'}],'away':[],'note':'Reported'}}],
           'qbSource':{'status':'loaded'},'tacticalSource':{'status':'loaded'},'injurySource':{'status':'loaded'}}
        fresh={'nextGames':[{'id':'x','kickoff':'2026-11-08T18:00:00+00:00',
              'qbIntelligence':{'status':'unavailable'},'tactical':{'status':'unavailable'},'injuryIntelligence':{'status':'unavailable'}}],
              'qbSource':{'status':'schedule-history-only'},
              'tacticalSource':{'status':'unavailable'},'injurySource':{'status':'unavailable'},'dataWarnings':[]}
        result=preserve_recent_player_context(fresh,previous,NOW)
        self.assertEqual(result['nextGames'][0]['qbIntelligence']['home']['qb'],'QB A')
        self.assertEqual(result['nextGames'][0]['injuryIntelligence']['status'],'reported-cached')
        self.assertEqual(result['qbSource']['status'],'cached')
        too_old={**previous,'generatedAt':(NOW-timedelta(days=5)).isoformat()}
        fresh2={'nextGames':[{'id':'x','kickoff':'2026-11-08T18:00:00+00:00'}],
                'qbSource':{'status':'unavailable'},'tacticalSource':{'status':'unavailable'},
                'injurySource':{'status':'unavailable'},'dataWarnings':[]}
        self.assertEqual(preserve_recent_player_context(fresh2,too_old,NOW)['qbSource']['status'],'unavailable')

    def test_cache_cannot_replace_fresh_qb_source(self):
        earlier={'generatedAt':(NOW-timedelta(hours=1)).isoformat(),
           'nextGames':[{'id':'x','kickoff':'2026-11-08T18:00:00+00:00',
              'qbIntelligence':{'status':'observed','home':{'sample':{'games':2}},'away':{}}}],
           'qbSource':{'status':'loaded'}}
        fresh={'nextGames':[{'id':'x','kickoff':'2026-11-08T18:00:00+00:00',
              'qbIntelligence':{'status':'observed','home':{'qb':'New QB'},'away':{}}}],
              'qbSource':{'status':'loaded'},'tacticalSource':{'status':'loaded'},
              'injurySource':{'status':'loaded'},'dataWarnings':[]}
        self.assertEqual(preserve_recent_player_context(fresh,earlier,NOW)['nextGames'][0]['qbIntelligence']['home']['qb'],'New QB')

if __name__=='__main__':unittest.main()
