import time
import unittest
from unittest.mock import patch

import server
from matching import assess, rank


class MatchingTests(unittest.TestCase):
    def job(self, title='German-speaking Customer Support Specialist', desc='',
            loc='Remote, North Macedonia', **extra):
        job = server.row('Test', title, 'Example', desc, loc, 'https://example.com/job')
        return assess(dict(job, **extra))

    def test_language_reference_is_not_requirement(self):
        self.assertEqual(self.job('Customer Support Specialist / German Company')['category'], 'possible')

    def test_all_profile_languages_individually(self):
        for name, code in [('German', 'de'), ('Macedonian', 'mk'), ('Serbian', 'sr'),
                           ('Croatian', 'hr'), ('Bosnian', 'bs')]:
            with self.subTest(name=name):
                job = self.job(f'Customer Support Specialist ({name})')
                self.assertEqual(job['languages'], {code: 'required'})
                self.assertEqual(job['category'], 'recommended')

    def test_english_and_other_languages_exclude(self):
        for desc in ('English B2 required', 'Fluent English and German required',
                     'French required', 'Excellent communication skills in the English language',
                     'Добро познавање на англиски јазик'):
            with self.subTest(desc=desc):
                self.assertEqual(self.job(desc=desc)['category'], 'excluded')

    def test_basic_english(self):
        self.assertEqual(self.job(desc='Basic English')['english_level'], 'basic')

    def test_professional_exclusion(self):
        self.assertTrue(self.job(title='German-speaking Customer Success Engineer')['excluded'])

    def test_country_and_worldwide(self):
        for loc in ('Remote, Germany', 'Germany / Worldwide', 'EU / EEA', 'Remote, Berlin'):
            with self.subTest(loc=loc):
                self.assertEqual(self.job(loc=loc, desc='We have 500 staff worldwide')['location_status'], 'excluded')
        worldwide = self.job(loc='Worldwide', mode_hint='remote')
        self.assertEqual(worldwide['location_status'], 'worldwide')
        self.assertEqual(worldwide['category'], 'review')
        self.assertEqual(self.job(loc='Europe', mode_hint='remote')['location_status'], 'unknown')
        self.assertEqual(self.job(loc='Remote', desc='Applications from anywhere in North Macedonia')['location_status'], 'confirmed')
        self.assertEqual(self.job(desc='Must be based in Germany')['location_status'], 'excluded')

    def test_modes_and_ranking(self):
        jobs = [self.job(loc=x) for x in ('Skopje', 'Hybrid Skopje', 'Remote Skopje freelance',
                                         'Remote Skopje', 'Homeoffice Skopje')]
        self.assertEqual([j['work_mode'] for j in sorted(jobs, key=rank, reverse=True)],
                         ['homeoffice', 'remote', 'freelance', 'hybrid', 'mk_local'])
        self.assertEqual(self.job(loc='Skopje', desc='freelance contract')['work_mode'], 'mk_local')

    def test_multiple_filters(self):
        jobs = [self.job(), self.job('Macedonian Customer Support Specialist'),
                self.job('Macedonian Project Manager', loc='Hybrid Skopje'),
                self.job('Serbian Customer Support Agent'), self.job(loc='Skopje')]
        query = {'language': ['de', 'mk'], 'industry': ['customer', 'travel'],
                 'mode': ['remote', 'hybrid'], 'location': ['confirmed']}
        self.assertEqual(server.select_jobs(jobs, query), jobs[:2])

    def test_expiry_rechecked_when_served(self):
        expires = time.time() + 20
        available = self.job(expires_at=expires)
        with patch('server.time.time', return_value=expires):
            self.assertEqual(server.select_jobs([available], {}), [])

    def test_failed_refresh_preserves_recent_snapshot(self):
        raw = server.row('Feed', 'German Recruiter', 'Example', '', 'Skopje', 'https://example.com/job')
        cache = dict(at=0, jobs=[], sources={}, refreshing=False)
        with patch.multiple(server, SOURCE_NAMES=['Feed'], SOURCE_CACHE={}, CACHE=cache):
            with patch.object(server, 'fetch_source', return_value=[raw]):
                server.refresh()
            with patch.object(server, 'fetch_source', side_effect=OSError('offline')):
                server.refresh()
            self.assertEqual(cache['sources']['Feed']['status'], 'stale')
            self.assertEqual(len(cache['jobs']), 1)
