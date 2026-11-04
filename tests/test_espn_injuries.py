"""Validation of a supplementary injury watch without asserting official status."""
import sys,unittest
from pathlib import Path
from datetime import datetime,timezone
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
from espn_injuries import parse

NOW=datetime(2026,11,4,20,tzinfo=timezone.utc)
class InjuryWatchTests(unittest.TestCase):
    def test_recent_dated_player(self):
        src={'injuries':[{'team':{'abbreviation':'JAC'},'injuries':[
            {'athlete':{'id':'1','fullName':'Demo Player','position':{'abbreviation':'QB'}},
             'status':'Questionable','date':'2026-11-03T12:00:00Z','type':{'description':'Foot'}}]}]}
        found=parse(src,NOW)
        self.assertEqual(found['JAX'][0]['name'],'Demo Player')
        self.assertEqual(found['JAX'][0]['injury'],'Foot')
        self.assertFalse(found['JAX'][0]['officialGameStatus'])
    def test_stale_entries_rejected(self):
        src={'injuries':[{'team':{'abbreviation':'ATL'},'injuries':[
            {'athlete':{'fullName':'Old Player'},'status':'Out','date':'2025-11-01T00:00:00Z'}]}]}
        self.assertEqual(parse(src,NOW),{})
    def test_undated_and_future_rejected(self):
        src={'injuries':[{'team':{'abbreviation':'BAL'},'injuries':[
            {'athlete':{'fullName':'Unknown'},'status':'Out'},
            {'athlete':{'fullName':'Future'},'status':'Out','date':'2026-11-10T00:00:00Z'}]}]}
        self.assertEqual(parse(src,NOW),{})
    def test_invalid_payload_is_an_error_not_a_healthy_roster(self):
        with self.assertRaises(ValueError):parse({'injuries':{}},NOW)

if __name__=='__main__':unittest.main()
