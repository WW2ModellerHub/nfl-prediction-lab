"""Undated injury releases are prospective observations, never retroactive facts."""
import sys
import unittest
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
from qb_injuries import read_injuries, injury_context
from model import read_games, generate

OBSERVED=datetime(2026,11,4,20,tzinfo=timezone.utc)
CSV=("season,week,team,gsis_id,position,full_name,report_status,practice_status,report_primary_injury\n"
     "2026,9,ATL,AAAA,QB,Sample Player,Out,DNP,Knee\n")
SCHEDULE=("game_id,season,game_type,week,gameday,gametime,away_team,away_score,home_team,home_score,location\n"
          "2026_08_CIN_ATL,2026,REG,8,2026-11-01,13:00,CIN,20,ATL,17,Home\n"
          "2026_09_CIN_ATL,2026,REG,9,2026-11-08,13:00,CIN,,ATL,,Home\n")

class InjurySnapshotTests(unittest.TestCase):
    def test_default_rejects_undated_rows(self):
        self.assertEqual(read_injuries(CSV),[])

    def test_snapshot_is_labelled_and_observed_only_now(self):
        rows=read_injuries(CSV,observation_time=OBSERVED,snapshot_mode=True)
        self.assertEqual(rows[0]['asOf'],OBSERVED)
        self.assertEqual(rows[0]['timestampBasis'],'download-observation')
        game=read_games(SCHEDULE)[1]
        report=injury_context(game,rows,{},OBSERVED)
        self.assertEqual(report['status'],'snapshot-only')
        self.assertEqual(report['home'][0]['name'],'Sample Player')
        self.assertEqual(report['probabilityWeight'],0)

    def test_never_backdates_to_previous_game(self):
        rows=read_injuries(CSV,observation_time=OBSERVED,snapshot_mode=True)
        game=read_games(SCHEDULE)[0]
        old=injury_context(game,rows,{},OBSERVED)
        self.assertEqual(old['status'],'unavailable')
        self.assertFalse(old['home'])

    def test_player_validation_remains_off(self):
        rows=read_injuries(CSV,observation_time=OBSERVED,snapshot_mode=True)
        meta={'injuries':{'loadedSeasons':[],'snapshotSeasons':[2026]},
              'depth':{'loadedSeasons':[]}}
        result,_=generate(read_games(SCHEDULE),OBSERVED,[],injury_rows=rows,player_meta=meta)
        self.assertEqual(result['nextGames'][0]['injuryIntelligence']['status'],'snapshot-only')
        self.assertFalse(result['playerValidation']['enabled'])

if __name__=="__main__":unittest.main()
