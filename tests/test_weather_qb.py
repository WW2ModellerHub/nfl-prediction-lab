"""Regression: weather never invents conditions and QB unverified data never alters forecasts."""
import sys,unittest
from pathlib import Path
from datetime import datetime,timezone,timedelta
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
from weather import enrich,parse_hourly
from qb_validation import snapshot,validate,predict
NOW=datetime(2026,11,4,21,tzinfo=timezone.utc)

class MatchupSourceTests(unittest.TestCase):
    def test_outdoor_forecast(self):
        t=int((NOW+timedelta(days=2)).timestamp())
        game={'stadium':'M&T Bank Stadium','stadiumId':'BAL00','roof':'outdoors','kickoff':(NOW+timedelta(days=2)).isoformat()}
        out=enrich([game],NOW,lambda *_:{'hourly':{'time':[t],'temperature_2m':[8.0],'wind_speed_10m':[23],'precipitation_probability':[65]}})
        self.assertEqual(game['weather']['status'],'forecast')
        self.assertEqual(game['weather']['windMph'],23)
        self.assertEqual(out['queriedVenues'],1)
    def test_indoor_never_queries(self):
        game={'stadium':'Caesars Superdome','stadiumId':'NOR00','roof':'dome','kickoff':(NOW+timedelta(days=2)).isoformat()}
        enrich([game],NOW,lambda *_:self.fail('Indoor forecast incorrectly requested'))
        self.assertEqual(game['weather']['status'],'indoor')
    def test_unknown_neutral_not_substituted(self):
        game={'stadium':'Unknown','stadiumId':'UNKNOWN','roof':'outdoors','kickoff':(NOW+timedelta(days=2)).isoformat()}
        enrich([game],NOW,lambda *_:self.fail('Never use designated home city for neutral venue'))
        self.assertEqual(game['weather']['status'],'venue-unmapped')
    def test_out_of_horizon_not_invented(self):
        game={'stadium':'M&T Bank Stadium','stadiumId':'BAL00','roof':'outdoors','kickoff':(NOW+timedelta(days=30)).isoformat()}
        enrich([game],NOW,lambda *_:self.fail('No requests outside horizon'))
        self.assertEqual(game['weather']['status'],'outside-forecast-range')
    def test_stale_hour_rejected(self):
        source={'hourly':{'time':[int(NOW.timestamp())],'wind_speed_10m':[20]}}
        self.assertIsNone(parse_hourly(source,NOW+timedelta(hours=4)))
    def test_unavailable_qb_never_treated_as_zero(self):
        self.assertFalse(snapshot({'home':'BAL','away':'JAX','season':2026},{'home':{},'away':{}},{},NOW)['eligible'])
        self.assertFalse(validate([],2026)['enabled'])
        self.assertEqual(predict(.6,None,[.1,.2,.3]),.6)
    def test_source_failure_is_explicit(self):
        game={'stadium':'M&T Bank Stadium','stadiumId':'BAL00','roof':'outdoors','kickoff':(NOW+timedelta(days=2)).isoformat()}
        out=enrich([game],NOW,lambda *_:(_ for _ in ()).throw(OSError('down')))
        self.assertEqual(game['weather']['status'],'unavailable')
        self.assertTrue(out['errors'])
if __name__=='__main__':unittest.main()
