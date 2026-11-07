import json, tempfile, sys, unittest
from datetime import datetime,timedelta,timezone
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/"scripts"))
from forecast_revisions import revisions
from prediction_record import summarize
from forecast_revisions import dt,valid

NOW=datetime(2026,11,9,14,tzinfo=timezone.utc)
def scored(id="game-1",season=2026,week=9,kickoff=None,
           first=.7,last=.3,result=0):
    kick=kickoff or (NOW-timedelta(days=1)).isoformat()
    return {"gameId":id,"season":season,"week":week,
      "kickoff":kick,"home":"BAL","away":"JAX","homeScore":10 if result==0 else 28,
      "awayScore":33 if result==0 else 7,"outcomeHome":result,
      "winner":"JAX" if result==0 else "BAL",
      "firstProbability":first,"lastProbability":last,
      "firstRecordedAt":(NOW-timedelta(days=4)).isoformat(),
      "lastRecordedAt":(NOW-timedelta(days=2)).isoformat(),
      "lastAgeHours":24.,"revisionsAfterFirst":1,
      "changed":first!=last,
      "firstCorrect":int((first>=.5)==bool(result)),
      "lastCorrect":int((last>=.5)==bool(result)),
      "brierGain":(first-result)**2-(last-result)**2,
      "lastQBEvidence":False,"lastPersonnelStatus":"provisional"}

def orig(gameId,at,kick,p=.53):
    return {"gameId":gameId,"recordedAt":at.isoformat(),
      "kickoff":kick.isoformat(),"kind":"first","home":"BAL","away":"JAX",
      "homeProbability":p}

class PredictionRecordTests(unittest.TestCase):
    def test_first_and_latest_win_loss_are_separate_from_revisions(self):
        row=scored()
        finishedAt=dt(row["kickoff"])
        h={"game-1":[orig("game-1",NOW-timedelta(days=4),finishedAt,.7),
                    orig("game-1",NOW-timedelta(days=2),finishedAt,.3)]}
        result=summarize([row],h,NOW,dt,valid)
        self.assertEqual(result["completed"]["games"],1)
        self.assertEqual(result["completed"]["original"]["wins"],0)
        self.assertEqual(result["completed"]["original"]["losses"],1)
        self.assertEqual(result["completed"]["latest"]["wins"],1)
        self.assertEqual(result["completed"]["latest"]["losses"],0)
        self.assertEqual(result["completed"]["latest"]["accuracy"],1)
        self.assertEqual(result["latestResults"][0]["originalPick"],"BAL")
        self.assertEqual(result["latestResults"][0]["latestPick"],"JAX")
        self.assertEqual(result["latestResults"][0]["winner"],"JAX")
        self.assertEqual(result["byWeek"][0]["week"],9)
        self.assertTrue(result["smallSample"])

    def test_duplicate_completed_games_never_inflate_accuracy(self):
        row=scored()
        with self.assertRaisesRegex(ValueError,"Duplicate graded prediction"):
            summarize([row,row],{},NOW,dt,valid)

    def test_many_refreshes_count_one_pending_game(self):
        kick=NOW+timedelta(days=2)
        snaps=[orig("g",NOW-timedelta(days=1),kick,.4)]
        snaps += [dict(orig("g",NOW+timedelta(minutes=i),kick,.55),kind="refresh")
                  for i in range(18)]
        result=summarize([],{"g":snaps},NOW,dt,valid)
        self.assertEqual(result["trackedGames"],1)
        self.assertEqual(result["upcomingCount"],1)
        self.assertEqual(result["upcoming"][0]["originalPick"],"JAX")
        self.assertEqual(result["upcoming"][0]["latestPick"],"BAL")
        self.assertEqual(result["completed"]["games"],0)
        self.assertIsNone(result["completed"]["latest"]["accuracy"])

    def test_awaiting_final_is_not_counted_as_a_loss(self):
        past=NOW-timedelta(days=2)
        pending=NOW+timedelta(days=2)
        g1=orig("no-final",NOW-timedelta(days=3),past)
        g2=orig("upcoming",NOW-timedelta(hours=1),pending)
        result=summarize([],{"no-final":[g1],"upcoming":[g2]},NOW,dt,valid)
        self.assertEqual(result["awaitingFinalCount"],1)
        self.assertEqual(result["upcomingCount"],1)
        self.assertEqual(result["completed"]["games"],0)
        self.assertEqual(result["completed"]["latest"]["losses"],0)

    def test_after_kickoff_snapshots_never_qualify_for_record(self):
        past=NOW-timedelta(days=1)
        item=orig("g",NOW,past)
        result=summarize([],{"g":[item]},NOW,dt,valid)
        self.assertEqual(result["trackedGames"],0)
        self.assertEqual(result["upcomingCount"],0)
        self.assertEqual(result["awaitingFinalCount"],0)

    def test_weekly_and_seasonal_results_only_use_actual_completed_games(self):
        rows=[scored(id=f"g{i}",week=9+i%2,season=2026,
                     first=.8 if i%2 else .3,last=.9 if i%2 else .2,result=i%2)
              for i in range(5)]
        rows+=[scored("g5",season=2025,week=1,first=.2,last=.3,result=0)]
        out=summarize(rows,{},NOW,dt,valid)
        self.assertEqual(out["completed"]["games"],6)
        self.assertEqual(out["completed"]["latest"]["wins"],6)
        self.assertEqual(out["completed"]["original"]["wins"],6)
        self.assertEqual(out["bySeason"][0]["season"],2026)
        self.assertEqual(out["bySeason"][0]["games"],5)
        self.assertEqual(len(out["byWeek"]),3)
        self.assertEqual(out["recent10"]["games"],6)

    def test_archive_integration_writes_one_row_per_game_and_preserves_immutable_first(self):
        with tempfile.TemporaryDirectory() as t:
            path=Path(t)/"forecast-revisions.json"
            gameId="2026_09_JAX_BAL"
            kickoff=NOW-timedelta(days=1)
            first=orig(gameId,NOW-timedelta(days=4),kickoff,.47021)
            final={"id":gameId,"season":2026,"week":9,"kickoff":kickoff,
                   "home":"BAL","away":"JAX","home_score":10,"away_score":33}
            dash={"nextGames":[]}
            initial=revisions(dash,[first],[final],NOW,path)
            self.assertEqual(len(initial),1)
            doc=Path(t)/"prediction-results.json"
            self.assertTrue(doc.exists())
            saved=json.loads(doc.read_text())
            self.assertEqual(saved["completed"]["latest"]["wins"],1)
            self.assertEqual(saved["completed"]["latest"]["losses"],0)
            self.assertEqual(saved["latestResults"][0]["originalPick"],"JAX")
            self.assertEqual(saved["latestResults"][0]["originalWinProbability"],.52979)
            self.assertEqual(dash["predictionRecord"]["completed"]["games"],1)
            self.assertNotIn("allResults",dash["predictionRecord"])
            old=path.read_bytes()
            revisions({"nextGames":[]},[first],[final],NOW+timedelta(hours=1),path)
            self.assertEqual(path.read_bytes(),old)
            self.assertEqual(json.loads(doc.read_text())["completed"]["latest"]["wins"],1)

if __name__=="__main__":unittest.main()
