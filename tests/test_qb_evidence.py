"""Source provenance: ESPN projected QB depth charts and dated team injuries."""
import io,json,sys,unittest
from datetime import datetime,timezone,timedelta
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/"scripts"))
from qb_evidence import (parse_depth,parse_injuries,parse_roster,gather,attach,TEAM_IDS,BASE)

NOW=datetime(2026,11,6,17,tzinfo=timezone.utc)
def depth(name="Backup B",person="410"):
    return {"depthCharts":[{"name":"Offense","positions":{
      "quarterback":{"position":{"abbreviation":"QB"},
         "athletes":[{"rank":2,"athlete":{"id":"23","displayName":"Reserve"}},
                     {"rank":1,"athlete":{"id":person,"displayName":name}}]}}}]}
def roster():
    return {"athletes":[{"position":"Quarterback",
      "items":[{"id":"410","displayName":"Backup B",
                "position":{"abbreviation":"QB"},"status":{"name":"Active"}},
               {"id":"999","displayName":"Reserve C",
                "position":{"abbreviation":"QB"}}]}]}

def injuries(date=True):
    return {"injuries":[{"athlete":{"displayName":"Veteran A",
           "position":{"abbreviation":"QB"}},"status":{"description":"Out"},
           **({"date":NOW.isoformat()} if date else {})}]}
def fixture():
    return {"id":"test","home":"BAL","away":"JAX","season":2026,
      "kickoff":(NOW+timedelta(days=2)).isoformat(),"homeProbability":.55,
      "qbIntelligence":{"status":"observed","home":{
        "qb":"Veteran A","basis":"last_game_recorded_starter",
        "lastGameLeader":{"name":"Veteran A","id":"gsis-333",
                          "season":2026,"date":(NOW-timedelta(days=5)).isoformat()},
        "previousQBsample":{"dropbacks":290,"games":7,"epaPerDropback":.21}},
        "away":{"qb":"Away QB","basis":"depth_chart_projection"}},
      "qbResearch":{"eligible":True,"features":[.1,0,0]},
      "personnelDepthChart":{"home":{"asOf":None},
                              "away":{"asOf":(NOW-timedelta(days=2)).isoformat()}},
      "supplementalInjuryWatch":{"status":"empty","home":[],"away":[]}}
class ESPNSourceTests(unittest.TestCase):
    def test_espn_team_codes_match_nflverse(self):
        self.assertEqual(TEAM_IDS["LA"],14)
        self.assertEqual(TEAM_IDS["WAS"],28)
        self.assertEqual(TEAM_IDS["BAL"],33)
        self.assertEqual(TEAM_IDS["JAX"],30)

    def test_read_rank_one_from_espn_depthchart(self):
        x=parse_depth(depth(),NOW)
        self.assertEqual(x["name"],"Backup B")
        self.assertEqual(x["rank"],1)
        self.assertEqual(x["timestampBasis"],"download-observation")
        self.assertEqual(x["observedAt"],NOW.isoformat())

    def test_invalid_or_conflicting_depth_fails_closed(self):
        with self.assertRaises(ValueError):parse_depth({"depthCharts":[]},NOW)
        with self.assertRaises(ValueError):
            parse_depth({"depthCharts":[{"positions":{"quarterback":{
               "athletes":[{"rank":1,"athlete":{"displayName":"A"}},
                           {"rank":1,"athlete":{"displayName":"B"}}]}}}]},NOW)


    def test_roster_is_not_a_starting_qb_projection(self):
        qbs=parse_roster(roster(),NOW)
        self.assertEqual(len(qbs),2)
        self.assertTrue(all(x["role"]=="roster QB, not verified starter" for x in qbs))
        with self.assertRaises(ValueError):parse_roster({"athletes":[]},NOW)
        flat={"athletes":[{"id":"9","displayName":"Flat QB",
                         "position":{"abbreviation":"QB"}}]}
        self.assertEqual(parse_roster(flat,NOW)[0]["name"],"Flat QB")

    def test_dated_injury_only(self):
        self.assertEqual(parse_injuries(injuries(),NOW)[0]["status"],"OUT")
        self.assertEqual(parse_injuries(injuries(False),NOW),[])
        past=NOW-timedelta(days=90)
        stale=inju=injuries()
        stale["injuries"][0]["date"]=past.isoformat()
        self.assertEqual(parse_injuries(stale,NOW),[])

    def test_historical_first_pick_not_inferred_from_rank_one(self):
        g=fixture()
        g["supplementalInjuryWatch"]["home"]=parse_injuries(injuries(),NOW)
        record={"BAL":{"depth":parse_depth(depth(),NOW),"depthStatus":"loaded",
                       "rosterQBs":parse_roster(roster(),NOW),"rosterStatus":"loaded"},
                "JAX":{"depth":None,"depthStatus":"unavailable","rosterQBs":[],
                       "rosterStatus":"unavailable"}}
        attach(g,record,{"status":"loaded","observationTime":NOW.isoformat()},NOW)
        h=g["qbIntelligence"]["home"]
        self.assertEqual(h["qb"],"Backup B")
        self.assertIsNone(h["playerId"],"ESPN athlete ID cannot be assigned to GSIS")
        self.assertIsNone(h["sample"])
        self.assertFalse(g["qbResearch"]["eligible"])
        self.assertFalse(h["confirmedStarter"])
        self.assertEqual(g["personnelDepthChart"]["home"]["timestampBasis"],"download-observation")
        self.assertEqual(g["supplementalInjuryWatch"]["home"][0]["reportDate"],NOW.isoformat())
        self.assertEqual(g["qbSourceEvidence"]["home"]["projectionUsed"],"ESPN rank-1 fallback")

    def test_fresh_nflverse_disagreement_is_not_silently_overwritten(self):
        g=fixture()
        g["qbIntelligence"]["home"].update(qb="Veteran A",basis="depth_chart_projection")
        g["personnelDepthChart"]["home"]["asOf"]=(NOW-timedelta(days=1)).isoformat()
        attach(g,{"BAL":{"depth":parse_depth(depth(),NOW),"depthStatus":"loaded",
                         "rosterQBs":parse_roster(roster(),NOW),"rosterStatus":"loaded"}},
               {"status":"loaded","observationTime":NOW.isoformat()},NOW)
        self.assertEqual(g["qbIntelligence"]["home"]["qb"],"Veteran A")
        self.assertTrue(g["qbSourceEvidence"]["home"]["sourceConflict"])
        self.assertNotEqual(g["qbSourceEvidence"]["home"]["projectionUsed"],"ESPN rank-1 fallback")

    def test_source_disagreement_also_blocks_qb_efficiency_preview(self):
        g=fixture()
        g["qbIntelligence"]["home"].update(qb="Veteran A",basis="depth_chart_projection")
        g["personnelDepthChart"]["home"]["asOf"]=(NOW-timedelta(days=1)).isoformat()
        attach(g,{"BAL":{"depth":parse_depth(depth(),NOW),"depthStatus":"loaded",
                         "injuries":[],"injuryStatus":"no-dated-records"}},
               {"status":"loaded","observationTime":NOW.isoformat()},NOW)
        self.assertFalse(g["qbResearch"]["eligible"])
        self.assertTrue(g["qbSourceEvidence"]["home"]["sourceConflict"])

    def test_matching_depth_is_independent_corrob_not_confirmed_starter(self):
        g=fixture()
        g["qbIntelligence"]["home"].update(qb="Backup B",basis="depth_chart_projection")
        g["personnelDepthChart"]["home"]["asOf"]=(NOW-timedelta(days=1)).isoformat()
        attach(g,{"BAL":{"depth":parse_depth(depth(),NOW),"depthStatus":"loaded",
                         "injuries":[],"injuryStatus":"no-dated-records"}},
               {"status":"loaded","observationTime":NOW.isoformat()},NOW)
        self.assertTrue(g["qbSourceEvidence"]["home"]["sourcesAgree"])
        self.assertFalse(g["qbIntelligence"]["home"].get("confirmedStarter",False))

    def test_undated_injuries_never_get_a_fake_report_time(self):
        g=fixture()
        attach(g,{"BAL":{"depth":None,"depthStatus":"unavailable",
                         "rosterQBs":[],"rosterStatus":"unavailable"}},
               {"status":"unavailable","observationTime":NOW.isoformat()},NOW)
        self.assertEqual(g["supplementalInjuryWatch"]["home"],[])
        self.assertEqual(g["supplementalInjuryWatch"]["status"],"empty")

    def test_only_near_term_teams_fetched_and_failures_are_reported(self):
        calls=[]
        class Response:
            def __init__(self,data):self.d=json.dumps(data).encode()
            def __enter__(self):return self
            def __exit__(self,*a):return False
            def read(self,n):return self.d[:n]
        def opener(req,timeout):
            calls.append(req.full_url)
            if "/depthcharts" in req.full_url:return Response(depth())
            return Response(roster())
        near=fixture()
        far={**fixture(),"id":"far","home":"MIA",
             "kickoff":(NOW+timedelta(days=11)).isoformat()}
        fetched,meta=gather([near,far],NOW,opener,max_workers=2)
        self.assertEqual(set(fetched),{"BAL","JAX"})
        self.assertEqual(len(calls),4)
        self.assertEqual(meta["depthChartsLoaded"],2)
        self.assertEqual(meta["qbRostersLoaded"],2)
        self.assertNotIn("MIA",meta["selectedTeams"])
        self.assertTrue(all(c.startswith(BASE) for c in calls))
    def test_cached_qb_history_has_fixed_expiry_and_never_reuses_old_probabilities(self):
        from update import prime_cached_qb_history
        previous=fixture()
        previous["qbHistoryAsOf"]=(NOW-timedelta(hours=8)).isoformat()
        previous["homeProbability"]=.91
        g=fixture()
        d={"nextGames":[g],"qbValidation":{}}
        count=prime_cached_qb_history(d,{"nextGames":[previous],
               "qbValidation":{"sampleSize":101}},NOW)
        self.assertEqual(count,1)
        self.assertEqual(g["homeProbability"],.55)
        self.assertEqual(d["qbValidation"]["sampleSize"],101)
        self.assertEqual(g["qbHistoryAsOf"],previous["qbHistoryAsOf"])
        d2={"nextGames":[fixture()]}
        self.assertEqual(prime_cached_qb_history(d2,{"nextGames":[previous]},
                         NOW+timedelta(hours=39)),0)
        self.assertNotIn("qbHistoryAsOf",d2["nextGames"][0])

if __name__=="__main__":unittest.main()
