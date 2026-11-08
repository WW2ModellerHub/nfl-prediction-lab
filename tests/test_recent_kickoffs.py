"""Started fixtures are visible without inventing a new in-play forecast."""
import unittest,sys
from pathlib import Path
from datetime import datetime,timezone,timedelta
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
from recent_kickoffs import make_recent_kickoffs
NOW=datetime(2026,11,8,21,19,tzinfo=timezone.utc)
K=NOW-timedelta(hours=3,minutes=19)
def game(kick=K,id="g",away="DAL"):
    return {"id":id,"season":2026,"week":9,"home":"NYG","away":away,
        "kickoff":kick,"home_score":None,"away_score":None}
def pick(kick=K,at=None,p=.55):
    return {"gameId":"g","kickoff":kick.isoformat(),
        "home":"NYG","away":"DAL","recordedAt":(at or kick-timedelta(hours=4)).isoformat(),
        "kind":"first","homeProbability":p,"model":"pregame Elo + form"}
class StartedGamesTest(unittest.TestCase):
    def test_18_uk_game_survives_kickoff_with_only_saved_pregame_probability(self):
        rows=make_recent_kickoffs([game()],[pick()],NOW)
        self.assertEqual(len(rows),1)
        self.assertEqual(rows[0]["homeProbability"],.55)
        self.assertTrue(rows[0]["archivedPregame"])
        self.assertIsNone(rows[0]["finalScoreFromSchedule"])
        self.assertEqual(rows[0]["lastPregameRecordedAt"],pick()["recordedAt"])
    def test_second_snapshot_is_not_new_live_prediction(self):
        rows=make_recent_kickoffs([game()],[pick(p=.55),{**pick(at=K-timedelta(minutes=1),p=.60),"kind":"refresh"}],NOW)
        self.assertEqual(rows[0]["homeProbability"],.60)
        self.assertEqual(rows[0]["originalHomeProbability"],.55)
    def test_no_fabrication_if_first_saved_pick_was_after_kickoff(self):
        self.assertEqual(make_recent_kickoffs([game()],[pick(at=K+timedelta(seconds=5))],NOW),[])
    def test_no_incorrect_identity_or_kickoff_merging(self):
        self.assertEqual(make_recent_kickoffs([game(away="WAS")],[pick()],NOW),[])
        self.assertEqual(make_recent_kickoffs([game()],[pick(kick=K-timedelta(days=2))],NOW),[])
    def test_late_night_games_keep_pregame_only(self):
        later=NOW+timedelta(minutes=10)
        self.assertEqual(make_recent_kickoffs([game(kick=later)],[pick(kick=later)],NOW),[])
    def test_old_game_expires_and_invalid_probability_rejected(self):
        past=NOW-timedelta(hours=40)
        self.assertEqual(make_recent_kickoffs([game(kick=past)],[pick(kick=past)],NOW),[])
        self.assertEqual(make_recent_kickoffs([game()],[pick(p=float('nan'))],NOW),[])
    def test_schedule_final_score_is_not_labelled_live(self):
        g={**game(),"home_score":13,"away_score":27}
        result=make_recent_kickoffs([g],[pick()],NOW)[0]
        self.assertEqual(result["finalScoreFromSchedule"]["source"],"nflverse schedules — not a live score feed")
if __name__=='__main__':unittest.main()
