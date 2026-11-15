import unittest,unittest.mock as mock
import server
class AdditionalTests(unittest.TestCase):
 def test_unique_source_names(self):self.assertEqual(len(set(server.SOURCE_NAMES)),len(server.SOURCE_NAMES))
 def test_ats_adapters(self):
  fixture={'greenhouse':{'jobs':[{'title':'German Recruiter','location':{'name':'Remote'},'absolute_url':'https://example.org/job'}]},'lever':[{'text':'German Recruiter','categories':{'location':'Remote'},'hostedUrl':'https://example.org/job'}],'ashby':{'jobs':[{'title':'German Recruiter','location':'Remote','jobUrl':'https://example.org/job'}]}}
  for name,(kind,_,_) in server.ATS_BOARDS.items():
   with self.subTest(name=name),mock.patch.object(server,'get',return_value=fixture[kind]):
    jobs=server.fetch_source(name)
    self.assertEqual(len(jobs),1)
 def test_english_unconfirmed_not_claimed(self):
  j=server.row('Test','German Recruiter','Test','Remote','Worldwide','https://example.org/job')
  self.assertEqual(server.assess(j)['english'],'Englischpflicht nicht belegt')
 def test_no_macedonia_claim(self):
  j=server.row('Test','German Recruiter','Test','Remote','Remote','https://example.org/job')
  self.assertEqual(server.assess(j)['ohrid'],'ungeklärt')
