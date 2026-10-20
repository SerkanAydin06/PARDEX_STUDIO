import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest import mock

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'app'))
import core,brain,company,company_cli

class CompanyTests(unittest.TestCase):
 def setUp(self):
  ctx=tempfile.TemporaryDirectory();self.addCleanup(ctx.cleanup)
  self.t=Path(ctx.name)
  for o,n,v in [(core,'HOME',self.t/'home'),(core,'STATE',self.t/'state.json'),(brain,'BRAIN_HOME',self.t/'brain')]:
   patch=mock.patch.object(o,n,v);patch.start();self.addCleanup(patch.stop)
  self.h=self.t/'company'
 def test_init_conservative(self):
  a=company.settings(self.h)
  self.assertEqual(a['limits']['monthly_new_spend_usd'],0)
  self.assertTrue(a['limits']['no_paid_api_by_default'])
  self.assertFalse(a['limits']['auto_apply_core'])
 def test_init_idempotent(self):
  company.initialize(self.h)
  self.assertEqual(company.initialize(self.h),self.h)
 def test_inventory_has_only_manual_meshy_3d(self):
  d={x['name']:x for x in company.providers()}
  self.assertEqual(d['Meshy']['type'],'manual-3d')
  self.assertEqual(d['ChatGPT']['type'],'manual-2d')
 def test_no_dead_github_models(self):
  self.assertNotIn('GitHub Models',str(company.SOURCES))
 def test_multi_project_overview(self):
  a=core.create_project(self.t,'One','godot','test')
  b=core.create_project(self.t,'Two','web','test')
  summary=company.project_summary()
  self.assertEqual(summary['count'],2)
  self.assertEqual(summary['engines']['godot'],1)
 def test_agenda_readonly(self):
  a=company.agenda('Yeni oyun',self.h)
  self.assertTrue(a['no_unattended_purchases'])
  self.assertEqual(a['goal'],'Yeni oyun')
 def test_meeting_offline_no_cli(self):
  m=company.meet('Yeni uygulama',False,self.h)
  self.assertEqual(m['reviews'],[])
  self.assertEqual(len(company.meetings(self.h)),1)
  self.assertIn('AI cagrisi yapilmadi',company.export_report(m))
 def test_cli_meeting_call_budget(self):
  with mock.patch.object(company,'_call_readonly',side_effect=[{'provider':'Gemini','ok':True,'output':'G'}, {'provider':'Claude','ok':True,'output':'C'}]):
   with mock.patch.object(core,'which',return_value='/fake/cli'):
    m=company.meet('MVP',True,self.h)
  self.assertEqual(len(m['reviews']),2)
  self.assertEqual(core.usage_count(),2)
 def test_meeting_daily_limit(self):
  with mock.patch.object(company,'_call_readonly',return_value={'provider':'Gemini','ok':True,'output':'ok'}):
   with mock.patch.object(core,'which',return_value='/fake/cli'):
    company.meet('MVP',True,self.h)
    with self.assertRaises(ValueError):company.meet('Again',True,self.h)
 def test_meeting_missing_cli_no_fake_success(self):
  with mock.patch.object(core,'which',return_value=None):
   a=company.meet('MVP',True,self.h)
  self.assertEqual(core.usage_count(),0)
  self.assertFalse(any(x['ok'] for x in a['reviews']))
 def test_recommendation_no_side_effects(self):
  a=company.recommend('subscription','New model subscription','Improve model performance','https://example.org/pricing',15,'USD',self.h)
  self.assertFalse(a['effects_executed'])
  b=company.decide(a['id'],True,'Proceed later',self.h)
  self.assertEqual(b['status'],'owner-approved-action-pending')
  self.assertFalse(b['effects_executed'])
 def test_reject_not_executed(self):
  a=company.recommend('hosting','Kucuk sunucu','Ucret gerektiren sunucu','https://example.org',4,'USD',self.h)
  self.assertEqual(company.decide(a['id'],False,home=self.h)['status'],'owner-rejected')
 def test_redecide_blocked(self):
  a=company.recommend('product','Oyun denemesi','Piyasayi test icin kullan',home=self.h)
  company.decide(a['id'],True,home=self.h)
  with self.assertRaises(ValueError):company.decide(a['id'],True,home=self.h)
 def test_unknown_recommendation_blocked(self):
  with self.assertRaises(ValueError):company.decide('not-found',True,home=self.h)
 def test_no_unsafe_source_url(self):
  with self.assertRaises(ValueError):company.recommend('hosting','New instance','Long enough reason','http://bad.invalid',home=self.h)
 def test_no_fake_price(self):
  with self.assertRaises(ValueError):company.recommend('subscription','Some service','Long enough reason','https://example.org',-1,home=self.h)
 def test_unknown_type(self):
  with self.assertRaises(ValueError):company.recommend('launch-and-pay','Fake','Long enough reason',home=self.h)
 def test_cost_roi(self):
  r=company.cost_evaluation(10,5,8,2)
  self.assertEqual(r['estimated_net'],28)
  self.assertEqual(r['break_even_hours'],1.5)
 def test_roi_zero_value(self):
  self.assertIsNone(company.cost_evaluation(5,0,0)['break_even_hours'])
 def test_roi_negative_reject(self):
  with self.assertRaises(ValueError):company.cost_evaluation(-1,3,4)
 def test_server_reference_dated(self):
  r=company.suggest_infrastructure('realtime',self.h)
  self.assertEqual(r['source_url'],'https://www.digitalocean.com/pricing/droplets')
  self.assertEqual(r['price_verified_on'],'2026-10-20')
 def test_unknown_server_kind(self):
  with self.assertRaises(ValueError):company.suggest_infrastructure('spaceship',self.h)
 def test_no_api_key_in_weekly_report(self):
  out=company_cli.weekly_report()
  self.assertIn('Gündemi',out)
  self.assertNotIn('sk-or-v1-',out)
 def test_free_router_payload_and_no_secrets_in_prompt(self):
  class Dummy:
   def __enter__(self):return self
   def __exit__(self,*args):return False
   def read(self,n):return json.dumps({'model':'another/free', 'choices':[{'message':{'content':'Only test'}}]}).encode()
  def fetch(req,timeout):
   data=json.loads(req.data)
   self.assertEqual(data['model'],'openrouter/free')
   self.assertEqual(data['max_tokens'],340)
   self.assertNotIn('apikey',str(data).lower())
   self.assertIn('Bearer XXX',req.headers.get('Authorization'))
   return Dummy()
  result,model=company_cli._optional_free_review({},'XXX',fetch)
  self.assertEqual(result,'Only test')
  self.assertEqual(model,'another/free')
 def test_free_router_doesnt_retry_or_leak_secret_on_error(self):
  def fail(req,timeout):raise RuntimeError('SECRET-456 network fail')
  text,model=company_cli._optional_free_review({},'SECRET-456',fail)
  self.assertNotIn('SECRET-456',text)
  self.assertIsNone(model)
 def test_ollama_local_only(self):
  class Dummy:
   def __enter__(self):return self
   def __exit__(self,*args):return False
   def read(self,n):return b'{"response":"Fayda: once test et"}'
  with mock.patch.object(company.urllib.request,'urlopen',return_value=Dummy()) as fake:
   result=company.local_ollama_opinion('Oyun','qwen3:4b')
  self.assertTrue(result['ok'])
  self.assertFalse(result['paid_api'])
  self.assertIn('127.0.0.1',fake.call_args.args[0].full_url)
 def test_ollama_model_injection_blocked(self):
  with self.assertRaises(ValueError):company.local_ollama_opinion('Goal','model;del all')
 def test_provider_history_no_fake_claims(self):
  a=core.create_project(self.t,'One','godot','test')
  brain.record_observation(a,'Codex','Task','task',False,'Godot bulunmadi. test yapilmadi')
  s=company.provider_performance()
  self.assertEqual(s['Codex']['observed'],0)
 def test_provider_history_real_success(self):
  a=core.create_project(self.t,'One','godot','test')
  brain.record_observation(a,'Codex','Task','task',True,'Godot import: OK')
  self.assertEqual(company.provider_performance()['Codex']['confirmed_success'],1)

 def test_adaptive_route_requires_both_samples(self):
  p=core.create_project(self.t,'One','godot','test')
  for i in range(15):brain.record_observation(p,'Gemini','Yeni ozellik / Kod','new code',True,'Godot import: OK')
  self.assertIsNone(company.adaptive_route_for_engine('godot','Yeni ozellik / Kod'))
 def test_adaptive_route_only_on_strong_verified_evidence(self):
  p=core.create_project(self.t,'One','godot','test')
  for i in range(10):
   brain.record_observation(p,'Gemini','Yeni ozellik / Kod','new code',True,'Godot import: OK')
   brain.record_observation(p,'Codex','Yeni ozellik / Kod','new code',False,'Godot import: HATA\nERROR: parser sahne yanlis')
  candidate=company.adaptive_route_for_engine('godot','Yeni ozellik / Kod',installed=['Gemini','Codex'])
  self.assertEqual(candidate['provider'],'Gemini')
  self.assertIsNone(company.adaptive_route_for_engine('godot','Mimari / Plan'))
  self.assertIsNone(company.adaptive_route_for_engine('godot','Yeni ozellik / Kod',installed=['Codex']))

if __name__=='__main__':unittest.main()
