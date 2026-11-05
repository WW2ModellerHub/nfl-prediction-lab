import copy
import math
import sys
import unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
from signal_accuracy import evaluate


def example_rows(seasons=(2021,2022,2023,2024,2025,2026),games_per=180):
    rows=[]
    for year in seasons:
        for i in range(games_per):
            # Known past features, deterministic synthetic wins; no bookmaker lines.
            f=[1 if i%2 else -1, (i%7-3)/3,
               (i%5-2)/2, (i%9-4)/4]
            y=1 if (i%4 in (0,1)) else 0
            rows.append(dict(season=year,week=(i//12)+1,p=.58,
                             features=f,y=y))
    return rows


class AccuracyLabTests(unittest.TestCase):
    def test_requires_previous_seasons(self):
        data=evaluate(example_rows(seasons=(2025,),games_per=180),2026)
        self.assertEqual(data['evaluatedGames'],0)
        self.assertEqual(data['productionWeight'],0)

    def test_paired_identical_games_and_no_prediction_changes(self):
        rows=example_rows()
        snapshot=copy.deepcopy(rows)
        result=evaluate(rows,2026)
        self.assertGreater(result['evaluatedGames'],300)
        self.assertEqual(len(result['candidates']),5)
        self.assertEqual(result['baseline']['games'],result['evaluatedGames'])
        for candidate in result['candidates']:
            self.assertEqual(candidate['games'],result['evaluatedGames'])
            self.assertFalse(candidate['affectsForecast'])
            self.assertIsNotNone(candidate['brierGain95CI'])
        self.assertEqual(rows,snapshot)

    def test_current_season_scores_never_train_or_grade(self):
        older=example_rows(seasons=(2021,2022,2023,2024,2025))
        with_current=older+example_rows(seasons=(2026,2027),games_per=220)
        self.assertEqual(evaluate(with_current,2026),evaluate(older,2026))

    def test_no_future_year_can_influence_prior_evaluation(self):
        a=example_rows(seasons=(2021,2022,2023,2024,2025))
        b=copy.deepcopy(a)
        for r in b:
            if r['season']==2025:
                r['y']=1-r['y']
        x=evaluate(a,2026)
        y=evaluate(b,2026)
        for key in ('baselineBrier','candidateBrier','brierGain'):
            for candidate1,candidate2 in zip(x['candidates'],y['candidates']):
                a2024=next(r for r in candidate1['seasons'] if r['season']==2024)
                b2024=next(r for r in candidate2['seasons'] if r['season']==2024)
                self.assertEqual(a2024[key],b2024[key])
    
    def test_null_missing_or_invalid_features_excluded(self):
        rows=example_rows()
        bad=[{"season":2024,"week":1,"p":.55,"features":None,"y":1},
             {"season":2024,"week":1,"p":float('nan'),"features":[0,0,0,0],"y":0},
             {"season":2024,"week":1,"p":.5,"features":[1,2,3,4],"y":None},
             {"season":2024,"week":1,"p":.5,"features":[1,2,3,4,5],"y":1}]
        self.assertEqual(evaluate(rows+bad,2026),evaluate(rows,2026))

    def test_decision_always_research_only(self):
        report=evaluate(example_rows(),2026)
        self.assertTrue(report['researchOnly'])
        self.assertFalse(report['forecastChanged'])
        self.assertEqual(report['productionWeight'],0)
        self.assertEqual(sum(x['games'] for x in report['calibration']['baseline']),
                         report['evaluatedGames'])
        self.assertTrue(all(0 <= x['brier'] <= 1 for x in report['candidates']))


if __name__=='__main__':
    unittest.main()
