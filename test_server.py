import unittest,unittest.mock as mock,json,threading,urllib.request,sys
import server
class Tests(unittest.TestCase):
 def base(self,**kw):
  return server.row('Test',kw.get('title','German Recruiter'),'Example',kw.get('description','Remote worldwide German required'),kw.get('location','Worldwide'),'https://example.com/job')
 def test_profile_recruit(self):self.assertGreaterEqual(server.assess(self.base())['fit'],70)
 def test_profile_fiber(self):self.assertGreaterEqual(server.assess(self.base(title='Fiber Rollout Project Coordinator'))['fit'],60)
 def test_sales(self):self.assertTrue(server.assess(self.base(title='Outbound Sales Representative',description='Remote worldwide cold calling required'))['excluded'])
 def test_fee(self):self.assertIn('kritischer',server.assess(self.base(description='Remote worldwide pay application fee before start'))['scam'])
 def test_english(self):self.assertIn('erkannt',server.assess(self.base(description='Remote worldwide English B2 required'))['english'])
 def test_germany(self):self.assertEqual(server.assess(self.base(location='Germany',description='Must reside in Germany. Remote'))['ohrid'],'ausgeschlossen')
 def test_eu(self):self.assertTrue(server.assess(self.base(description='EU residents only. Remote'))['excluded'])
 def test_unknown(self):self.assertEqual(server.assess(self.base(description='Remote',location='Remote'))['ohrid'],'ungeklärt')
 def test_no_salary(self):self.assertEqual(server.assess(self.base())['salary'],'')
 def test_non_https(self):self.assertIsNone(server.row('Test','Recruiter','X','Remote','World','http://x.com'))
 def test_sources(self):
  fixtures={
   'Remotive':{'jobs':[{'title':'Recruiter','company_name':'A','description':'Remote','candidate_required_location':'Worldwide','url':'https://a.com','id':1}]},
   'Arbeitnow':{'data':[{'title':'Recruiter','company_name':'A','description':'Remote','location':'Worldwide','url':'https://a.com','slug':'a'}]},
   'Jobicy':{'jobs':[{'jobTitle':'Recruiter','companyName':'A','jobDescription':'Remote','jobGeo':'Worldwide','url':'https://a.com'}]},
   'Remote OK':[{'position':'Recruiter','company':'A','description':'Remote','location':'Worldwide','url':'https://a.com'}],
   'Himalayas':{'jobs':[{'title':'Recruiter','companyName':'A','description':'Remote','worldwide':True,'applicationLink':'https://a.com'}]}
  }
  for name,fixture in fixtures.items():
   with self.subTest(source=name),mock.patch.object(server,'get',return_value=fixture):
    jobs=server.fetch_source(name);self.assertTrue(jobs);self.assertEqual(jobs[0]['source'],name)
 def test_dedupe_and_failures(self):
  def fake(name):
   if name=='Jobicy':raise OSError('test offline')
   return [self.base()]
  with mock.patch.object(server,'fetch_source',side_effect=fake):
   self.assertEqual(server.refresh(),1)
   self.assertEqual(server.CACHE['sources']['Jobicy']['status'],'error')
   self.assertEqual(len(server.CACHE['jobs']),1)
 def test_api(self):
  http=server.ThreadingHTTPServer(('127.0.0.1',0),server.Handler);t=threading.Thread(target=http.serve_forever,daemon=True);t.start()
  try:
   for path in ('/','/api/status','/api/jobs?page=1','/api/jobs?show=all'):
    with urllib.request.urlopen('http://127.0.0.1:'+str(http.server_port)+path,timeout=3) as r:self.assertEqual(r.status,200)
  finally:http.shutdown();http.server_close()
if __name__=='__main__':unittest.main(verbosity=2)
