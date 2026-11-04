"""No-data, cutoff and player model research-gate invariants."""
import sys,unittest
from pathlib import Path
from datetime import datetime,timezone,timedelta
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
from player_validation import snapshot, validate, predict, fit, FEATURES
from qb_injuries import depth_at,read_depth_rows,read_injuries,injury_context
from model import generate
T=datetime(2026,11,14,18,tzinfo=timezone.utc)

def game(week=12,future=True,season=2026):
    return {'id':f'{season}_{week}_MIA_BUF','season':season,'week':week,'type':'REG',
            'kickoff':T+timedelta(days=week-12),'home':'BUF','away':'MIA','neutral':False,
            'home_score':None if future else 24,'away_score':None if future else 14,
            'overtime':False,'closing_spread':None}

def qb_info(home_epa=.23,away_epa=.1,home_change=False,away_change=False):
    def side(pid,epa,change):return {'playerId':pid,'starterChangeWatch':change,
        'sample':{'dropbacks':130,'epaPerDropback':epa,'sackRate':.055}}
    return {'home':side('BQB',home_epa,home_change),'away':side('MQB',away_epa,away_change)}

def depth(cutoff=T-timedelta(days=2)):
    return {'BUF':{'asOf':cutoff.isoformat(),'qb':{'id':'BQB','name':'BUF QB'},'starters':['BQB','BWR']},
            'MIA':{'asOf':cutoff.isoformat(),'qb':{'id':'MQB','name':'MIA QB'},'starters':['MQB','MWR']}}

def injuries(both=True):
    return {'status':'reported','home':[{'position':'WR','id':'BWR','status':'OUT','starterOnDepthChart':True}],
            'away':[{'position':'WR','id':'MWR','status':'DOUBTFUL','starterOnDepthChart':True}] if both else []}

class PlayerValidationTests(unittest.TestCase):
    def test_no_depth_never_claims_impact(self):
        result=snapshot(game(),qb_info(),injuries(),{},T,[2026])
        self.assertFalse(result['eligible'])
        self.assertIsNone(result['features'])
        self.assertEqual(result['probabilityWeight'],0)
    def test_missing_injury_archive_blocks_model(self):
        result=snapshot(game(),qb_info(),injuries(),depth(),T,[])
        self.assertFalse(result['eligible'])
        self.assertIn('archive',result['reason'])
    def test_eligible_feature_signs(self):
        result=snapshot(game(),qb_info(away_change=True),injuries(),depth(),T,[2026])
        self.assertTrue(result['eligible'])
        self.assertAlmostEqual(result['features'][0],.13)
        self.assertEqual(result['features'][1],1)
        self.assertAlmostEqual(result['features'][3],-0.55) # away 0.45, home 1.0
    def test_insufficient_qb_dropbacks_no_features(self):
        q=qb_info();q['away']['sample']['dropbacks']=20
        result=snapshot(game(),q,injuries(),depth(),T,[2026])
        self.assertFalse(result['eligible'])
        self.assertIn('≥80',result['reason'])
    def test_stale_depth_and_future_depth_rejected(self):
        a=depth(T-timedelta(days=40));b=depth(T+timedelta(hours=1))
        self.assertFalse(snapshot(game(),qb_info(),injuries(),a,T,[2026])['eligible'])
        self.assertFalse(snapshot(game(),qb_info(),injuries(),b,T,[2026])['eligible'])
    def test_future_chart_does_not_change_old_qb(self):
        rows=read_depth_rows([{'dt':'2026-11-10T12:00:00Z','team':'BUF','player_name':'BUF QB',
                               'gsis_id':'BQB','pos_abb':'QB','pos_rank':1},
                              {'dt':'2026-11-15T12:00:00Z','team':'BUF','player_name':'Replacement',
                               'gsis_id':'BQB-NEW','pos_abb':'QB','pos_rank':1}])
        chart=depth_at(rows,T)
        self.assertEqual(chart['BUF']['qb']['id'],'BQB')
    def test_injury_out_only_if_pre_kickoff(self):
        csv='season,week,team,gsis_id,position,full_name,report_status,practice_status,date_modified,report_primary_injury\n'
        csv+='2026,12,BUF,BWR,WR,Player A,Questionable,LP,2026-11-13T12:00:00Z,Knee\n'
        csv+='2026,12,BUF,BWR,WR,Player A,Out,DNP,2026-11-15T12:00:00Z,Knee\n'
        rows=read_injuries(csv)
        status=injury_context(game(),rows,depth(),T)
        self.assertEqual(status['home'][0]['status'],'Questionable')
        impact=snapshot(game(),qb_info(),status,depth(),T,[2026])
        self.assertEqual(impact['features'][3],0)
    def test_unvalidated_gates_never_change_probability(self):
        # No supplied injury/depth archives -> no player adjustment and no
        # implicit healthy-roster assumptions.
        gs=[game(week=1,future=False),game(week=2,future=True)]
        now=gs[1]['kickoff']-timedelta(days=1)
        base,_=generate(gs,now,[])
        added,_=generate(gs,now,[],injury_rows=[{'season':2026,'week':2,'team':'BUF',
               'id':'BWR','name':'Player A','position':'WR','reportStatus':'OUT',
               'practiceStatus':'DNP','injury':'Knee','asOf':now-timedelta(days=1)}])
        self.assertEqual(base['nextGames'][0]['homeProbability'],added['nextGames'][0]['homeProbability'])
        self.assertEqual(added['overlaySelection'],'none')
    def test_current_season_results_excluded_from_validation(self):
        rows=[{'season':2025,'p':.5,'y':i%2,'features':[.2,0,.1,1]} for i in range(170)]
        self.assertEqual(validate(rows,2026)['trainedThroughSeason'],2025)
        rows.extend({'season':2026,'p':.5,'y':1,'features':[.5,1,0,3]} for _ in range(500))
        current=validate(rows,2026)
        self.assertFalse(current['enabled'])
        self.assertEqual(current['sampleSize'],170)
        self.assertEqual(current['trainedThroughSeason'],2025)
        self.assertEqual(current['coefficients'],dict.fromkeys(FEATURES,0.0))
    def test_fit_no_features_or_insufficient_is_exact_zero(self):
        rows=[{'p':.5,'y':1,'features':[0,0,0,0]} for _ in range(500)]
        self.assertEqual(fit(rows),[0,0,0,0])
        self.assertEqual(predict(.63,None,[.1]*4),.63)
    def test_forward_log_reuses_published_original_probability(self):
        gs=[game(week=10,future=False),game(week=11,future=True)]
        now=gs[1]['kickoff']-timedelta(days=1)
        first,log=generate(gs,now,[])
        self.assertEqual(len(log),1)
        recorded=log[0]['homeProbability']
        later=now+timedelta(hours=1)
        second,log2=generate(gs,later,log)
        self.assertEqual(log2[0]['homeProbability'],recorded)
        self.assertEqual(len(log2),1)

if __name__=='__main__': unittest.main()

# Additional archive-index invariants (kept separate to avoid changing the
# fixtures used by the prior suite).
from unittest.mock import patch
from qb_injuries import DepthTimeline,load_historical_reports

class ArchiveTimelineTests(unittest.TestCase):
    def test_indexed_lookup_never_sees_future_chart(self):
        raw=read_depth_rows([
            {'dt':'2026-11-12T09:00:00Z','team':'BUF','player_name':'Earlier QB','gsis_id':'P1','pos_abb':'QB','pos_rank':1},
            {'dt':'2026-11-16T09:00:00Z','team':'BUF','player_name':'Future QB','gsis_id':'P2','pos_abb':'QB','pos_rank':1},
            {'dt':'2026-11-12T09:00:00Z','team':'MIA','player_name':'MIA QB','gsis_id':'M1','pos_abb':'QB','pos_rank':1}])
        timeline=DepthTimeline(raw)
        cutoff=datetime(2026,11,14,12,tzinfo=timezone.utc)
        before=timeline.at(cutoff,('BUF','MIA'))
        after=timeline.at(datetime(2026,11,17,12,tzinfo=timezone.utc),('BUF',))
        self.assertEqual(before['BUF']['qb']['id'],'P1')
        self.assertEqual(before['MIA']['qb']['id'],'M1')
        self.assertEqual(after['BUF']['qb']['id'],'P2')
    def test_history_loader_marks_missing_season_partial_not_loaded(self):
        fake_row={'season':2025,'week':1,'team':'BUF','id':'P1','name':'Test', 'position':'QB',
                  'reportStatus':'OUT','practiceStatus':'DNP','injury':'Hand','asOf':T}
        fake_depth={'asOf':T,'team':'BUF','id':'P1','name':'Test','position':'QB','rank':1}
        def stub(season):
            if season==2025:
                return [fake_row],[fake_depth],{'injuries':{'status':'loaded','errors':[]},'depth':{'status':'loaded','errors':[]}}
            return [],[],{'injuries':{'status':'unavailable','errors':['404']},'depth':{'status':'unavailable','errors':['404']}}
        with patch('qb_injuries.load_current_reports',side_effect=stub):
            reports,charts,meta=load_historical_reports(2026)
        self.assertEqual(len(reports),1)
        self.assertEqual(len(charts),1)
        self.assertEqual(meta['injuries']['status'],'partial')
        self.assertEqual(meta['injuries']['loadedSeasons'],[2025])
        self.assertEqual(meta['depth']['loadedSeasons'],[2025])
