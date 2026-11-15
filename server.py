#!/usr/bin/env python3
"""Meister 7.0: stdlib local web service. No authentication: do not expose publicly."""
import json, re, html, os, time, threading, urllib.request, urllib.parse, urllib.error, hashlib, xml.etree.ElementTree as ET
from http.server import ThreadingHTTPServer, BaseHTTPRequestHandler
from pathlib import Path
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
from matching import assess, rank as personal_rank
from local_sources import kariera_board, local_board, support_board
from concurrent.futures import ThreadPoolExecutor, as_completed
BASE=Path(__file__).resolve().parent
CACHE={'at':0,'jobs':[],'sources':{},'refreshing':False}
SOURCE_CACHE={}
MAX_STALE=7200
REFRESH_INTERVAL=1800
LOCK=threading.Lock()
REFRESH_LOCK=threading.Lock()
UA={'User-Agent':'BalkanRemoteCareerMeister/7.0 (personal job research; contact via operator)','Accept':'application/json'}
ATS_BOARDS={
 'Greenhouse · GitLab':('greenhouse','gitlab','GitLab'),
 'Greenhouse · Automattic':('greenhouse','automattic','Automattic'),
 'Greenhouse · Remote':('greenhouse','remote','Remote'),
 'Greenhouse · Canonical':('greenhouse','canonical','Canonical'),
 'Greenhouse · Wikimedia':('greenhouse','wikimedia','Wikimedia'),
 'Ashby · Deel':('ashby','deel','Deel'),
 'Ashby · Linear':('ashby','linear','Linear'),
 'Greenhouse · Personio':('greenhouse','personio','Personio'),
 'Greenhouse · SumUp':('greenhouse','sumup','SumUp'),
 'Greenhouse · N26':('greenhouse','n26','N26'),
 'Greenhouse · Miro':('greenhouse','realtimeboardglobal','Miro'),
 'Greenhouse · HelloFresh':('greenhouse','hellofresh','HelloFresh'),
 'Greenhouse · Customer.io':('greenhouse','customerio','Customer.io'),
 'Greenhouse · Kraken':('greenhouse','kraken','Kraken'),
 'Greenhouse · Grafana Labs':('greenhouse','grafanalabs','Grafana Labs'),
 'Greenhouse · Mozilla':('greenhouse','mozilla','Mozilla'),
 'Greenhouse · Elastic':('greenhouse','elastic','Elastic'),
 'Greenhouse · Doist':('greenhouse','doist','Doist'),
 'Greenhouse · HubSpot':('greenhouse','hubspot','HubSpot'),
 'Greenhouse · Vercel':('greenhouse','vercel','Vercel'),
 'Greenhouse · Wise':('greenhouse','wise','Wise'),
 'Greenhouse · Revolut':('greenhouse','revolut','Revolut'),
 'Greenhouse · Toptal':('greenhouse','toptal','Toptal'),
 'Greenhouse · GoDaddy':('greenhouse','godaddy','GoDaddy'),
 'Lever · Aircall':('lever','aircall','Aircall'),
 'Lever · Binance':('lever','binance','Binance'),
 'Greenhouse · Bitpanda':('greenhouse','bitpanda','Bitpanda'),
 'Ashby · Remote':('ashby','remote','Remote'),
 'Lever · Remote.com':('lever','remote','Remote.com'),
}
SOURCE_NAMES=['Remotive','We Work Remotely · RSS','Arbeitnow','Jobicy','Remote OK','Himalayas','The Muse · Jobs','RemoteJobs.org · Jobs','Working Nomads',*ATS_BOARDS,'Workable · SupportYourApp','Vrabotuvanje MK','KARIERA.mk','Jobicy · Sprachsuche']

def clean(value):
    if not isinstance(value, str):
        return ''
    value = html.unescape(value)
    value = re.sub(r'<(?:style|script)\b[^>]*>.*?</(?:style|script)>', ' ', value, flags=re.I | re.S)
    value = re.sub(r'<(?:br|/p|/li|/div|/h[1-6])\b[^>]*>', '\n', value, flags=re.I)
    value = re.sub(r'<[^>]+>', ' ', value)
    return '\n'.join(' '.join(line.split()) for line in value.splitlines() if line.strip())[:20000]


def timestamp(value):
    if not value:
        return 0
    try:
        if str(value).isdigit():
            return int(value)
        try:
            date = datetime.fromisoformat(str(value).replace('Z', '+00:00'))
        except ValueError:
            date = parsedate_to_datetime(str(value))
        return (date if date.tzinfo else date.replace(tzinfo=timezone.utc)).timestamp()
    except (ValueError, TypeError, OverflowError):
        return 0


def read(url, accept='application/json'):
    req = urllib.request.Request(url, headers=dict(UA, Accept=accept))
    with urllib.request.urlopen(req, timeout=10) as response:
        return response.read(12_000_000)


def get(url):
    return json.loads(read(url))


def row(source, title, company, description, location, url, salary='', date='', raw_id=''):
    title = clean(title)
    if not title or not isinstance(url, str):
        return None
    try:
        parsed = urllib.parse.urlsplit(url)
    except ValueError:
        return None
    if parsed.scheme != 'https' or not parsed.hostname or parsed.username or parsed.password:
        return None
    if not clean(company) and not clean(description):
        return None
    return dict(source=source, title=title[:180], company=clean(company)[:150],
                description=clean(description), location=clean(location)[:240], url=url,
                salary=clean(str(salary or ''))[:200], date=str(date or '')[:32],
                published_at=timestamp(date), id=str(raw_id or ''))


def records(payload, key):
    if not isinstance(payload, dict) or not isinstance(payload.get(key), list):
        raise ValueError('Unerwartetes Antwortformat: ' + key)
    return payload[key]


def as_list(payload):
    if not isinstance(payload, list):
        raise ValueError('Unerwartetes Antwortformat: Liste erwartet')
    return payload


def fetch_source(name):
 jobs=[]
 if name=='KARIERA.mk':
  return kariera_board(read,row)
 if name=='Vrabotuvanje MK':
  return local_board(read,row,timestamp)
 if name=='Workable · SupportYourApp':
  return support_board(get,row)
 if name in ATS_BOARDS:
  kind,board,company=ATS_BOARDS[name]
  if kind=='greenhouse':
   d=get('https://boards-api.greenhouse.io/v1/boards/'+board+'/jobs?content=true')
   for x in records(d,'jobs'):
    jobs.append(row(name,x.get('title'),company,x.get('content',''),(x.get('location') or {}).get('name',''),x.get('absolute_url'),'',x.get('first_published') or x.get('updated_at'),x.get('id')))
  elif kind=='lever':
   d=get('https://api.lever.co/v0/postings/'+board+'?mode=json')
   for x in as_list(d):
    cats=x.get('categories') or {}
    job=row(name,x.get('text'),company,'\n'.join(filter(None,[x.get('descriptionPlain') or x.get('description'),*(entry.get('content') for entry in x.get('lists',[])),x.get('additionalPlain')])),', '.join(cats.get('allLocations') or [cats.get('location','')]),x.get('hostedUrl'),'', '',x.get('id'))
    if job:
     mode={'remote':'remote','hybrid':'hybrid','on-site':'onsite'}.get(x.get('workplaceType'),'unknown')
     jobs.append(dict(job,mode_hint=mode,employment=cats.get('commitment') or ''))
  elif kind=='ashby':
   d=get('https://api.ashbyhq.com/posting-api/job-board/'+board+'?includeCompensation=true')
   for x in records(d,'jobs'):
    if x.get('isListed') is False:continue
    jobs.append(row(name,x.get('title'),company,x.get('descriptionPlain') or x.get('descriptionHtml') or '',x.get('location',''),x.get('jobUrl') or x.get('applyUrl'),(x.get('compensation') or {}).get('compensationTierSummary','') if isinstance(x.get('compensation'),dict) else '',x.get('publishedAt'),x.get('id')))
 elif name.startswith('Remotive'):
  term={'Remotive · German':'german','Remotive · Customer Support':'customer support','Remotive · Recruiting':'recruiter','Remotive · Balkan':'macedonian','Remotive · Travel':'german travel','Remotive · Translator':'german translator','Remotive · German Support':'german customer support','Remotive · German HR':'german recruiting','Remotive · German Telecom':'german telecommunications','Remotive · German Freelance':'german freelance','Remotive · Croatian':'croatian','Remotive · Serbian':'serbian','Remotive · Bosnian':'bosnian','Remotive · Macedonian':'macedonian','Remotive · German Homeoffice':'german home office'}.get(name)
  endpoint='https://remotive.com/api/remote-jobs?limit=500'
  if term:endpoint+='&search='+urllib.parse.quote(term)
  d=get(endpoint)
  for x in records(d,'jobs'):jobs.append(row(name,x.get('title'),x.get('company_name'),x.get('description'),x.get('candidate_required_location'),x.get('url'),x.get('salary'),x.get('publication_date'),x.get('id')))
 elif name=='We Work Remotely · RSS':
  # Public RSS feed. RSS summaries can be brief; never infer language or work eligibility.
  url='https://weworkremotely.com/remote-jobs.rss'
  req=urllib.request.Request(url,headers={'User-Agent':UA['User-Agent'],'Accept':'application/rss+xml,application/xml,text/xml'})
  with urllib.request.urlopen(req,timeout=13) as response:xml_data=response.read(5_000_000)
  root=ET.fromstring(xml_data)
  for item in root.findall('.//item'):
   title=item.findtext('title') or ''
   link=item.findtext('link') or ''
   description=item.findtext('description') or ''
   date=item.findtext('pubDate') or ''
   company,title=(title.split(': ',1)+[''])[:2] if ': ' in title else ('',title)
   jobs.append(row(name,title,company,description,item.findtext('region') or 'Remote',link,'',date,link))
 elif name=='Arbeitnow':
  url='https://www.arbeitnow.com/api/job-board-api'
  for page in range(4):
   d=get(url)
   for x in records(d,'data'):
    job=row(name,x.get('title'),x.get('company_name'),x.get('description'),x.get('location'),x.get('url'),'',x.get('created_at'),x.get('slug'))
    if job:jobs.append(dict(job,mode_hint='remote' if x.get('remote') is True else 'unknown'))
   nxt=d.get('links',{}).get('next') or d.get('next')
   if not nxt or not str(nxt).startswith('https://www.arbeitnow.com/'):break
   url=nxt
 elif name in ('Jobicy','Jobicy · Sprachsuche'):
  endpoint='https://jobicy.com/api/v2/remote-jobs?count=50'
  terms=['german','macedonian','serbian','croatian','bosnian'] if name.endswith('Sprachsuche') else ['']
  errors=[]
  for term in terms:
   try:
    d=get(endpoint+('&tag='+term if term else ''))
    for x in records(d,'jobs'):
     job=row(name,x.get('jobTitle'),x.get('companyName'),x.get('jobDescription'),x.get('jobGeo'),x.get('url'),str(x.get('annualSalaryMin') or '')+' '+str(x.get('annualSalaryMax') or ''),x.get('pubDate'),x.get('id'))
     if job:jobs.append(dict(job,mode_hint='remote',employment=', '.join(x.get('jobType') or [])))
   except (OSError,ValueError) as error:
    errors.append(str(error))
  if len(errors)==len(terms):raise ValueError(errors[0])
  return (jobs, errors) if errors else jobs
 elif name=='Remote OK':
  d=get('https://remoteok.com/api')
  for x in as_list(d):
   if not isinstance(x,dict):continue
   jobs.append(row(name,x.get('position'),x.get('company'),x.get('description'),x.get('location') or '',x.get('url'),x.get('salary') or '',x.get('date'),x.get('id')))
 elif name=='The Muse · Jobs':
  for page in range(1,3):
   d=get('https://www.themuse.com/api/public/jobs?page='+str(page))
   for x in records(d,'results'):
    loc=', '.join(v.get('name','') for v in x.get('locations',[]) if isinstance(v,dict))
    company=(x.get('company') or {}).get('name','')
    jobs.append(row(name,x.get('name'),company,x.get('contents',''),loc,x.get('refs',{}).get('landing_page'),'',x.get('publication_date'),x.get('id')))
   if page>=d.get('page_count',page):break
 elif name=='RemoteJobs.org · Jobs':
  d=get('https://remotejobs.org/api/v1/jobs?limit=100')
  for x in records(d,'data') if isinstance(d,dict) else []:
   company=x.get('company',{})
   if isinstance(company,dict):company=company.get('name','')
   jobs.append(row(name,x.get('title'),company,x.get('description',''),x.get('location',''),x.get('url') or x.get('apply_url'),'',x.get('created_at'),x.get('id')))
 elif name=='Working Nomads':
  d=get('https://www.workingnomads.com/api/exposed_jobs/')
  for x in (as_list(d) if isinstance(d,list) else records(d,'jobs')):
   jobs.append(row(name,x.get('title'),x.get('company_name') or x.get('company'),x.get('description',''),x.get('location',''),x.get('url') or x.get('link'),x.get('salary',''),x.get('date',''),x.get('id','')))
 elif name=='Himalayas':
  # API terms: use original applicationLink and display source credit.
  cursor=None
  for _ in range(10):
   endpoint='https://himalayas.app/jobs/api?limit=20'
   if cursor:endpoint+='&cursor='+urllib.parse.quote(cursor)
   d=get(endpoint)
   for x in records(d,'jobs'):
    company=x.get('companyName') or (x.get('company') or {}).get('name','') if isinstance(x.get('company'),dict) else x.get('companyName','')
    loc=', '.join(str(v) for v in (x.get('locationRestrictions') or [])) if isinstance(x.get('locationRestrictions'),list) else str(x.get('locationRestrictions') or '')
    if x.get('worldwide') is True and not loc:loc='Worldwide'
    sal=' '.join(str(x.get(k) or '') for k in ('minSalary','maxSalary','currency','salaryPeriod'))
    job=row(name,x.get('title'),company,x.get('description'),loc,x.get('applicationLink'),sal if x.get('minSalary') or x.get('maxSalary') else '',x.get('pubDate') or x.get('publishedAt'),x.get('guid'))
    if job:jobs.append(dict(job,mode_hint='remote',expires_at=timestamp(x.get('expiryDate')),employment=x.get('employmentType') or ''))
   cursor=d.get('nextCursor')
   if not cursor:break
 result=[j for j in jobs if j]
 if name in ('Remotive','Remote OK','Working Nomads','RemoteJobs.org · Jobs'):
  for job in result:job['mode_hint']='remote'
 return result

def job_identity(job):
    url = urllib.parse.urlsplit(job['url'])
    query = [(key, value) for key, value in urllib.parse.parse_qsl(url.query, keep_blank_values=True)
             if not key.startswith('utm_') and key not in ('source', 'ref')]
    return url.hostname, url.path.rstrip('/'), tuple(sorted(query))


def publish_snapshot():
    by_url = {}
    by_listing = {}
    now = time.time()
    for name in SOURCE_NAMES:
        saved = SOURCE_CACHE.get(name)
        if not saved or now - saved[0] > MAX_STALE:
            continue
        for job in saved[1]:
            if job.get('expires_at') and job['expires_at'] <= now:
                continue
            date = job.get('published_at', 0)
            if date and date < now - 90 * 86400 and name not in ATS_BOARDS and not job.get('expires_at'):
                continue
            job = dict(job, source_checked_at=saved[0])
            url_key = job_identity(job)
            listing_key = tuple(re.sub(r'\W+', ' ', job[key].casefold()).strip()
                                for key in ('company', 'title', 'location'))
            key = by_listing.get(listing_key, url_key) if job['company'] and job['location'] else url_key
            current = by_url.get(key)
            quality = (job.get('details_checked', False), name in ATS_BOARDS or name.startswith('Workable'),
                       len(job['description']), date)
            if not current or quality > current[0]:
                by_url[key] = quality, job
            if job['company'] and job['location']:
                by_listing[listing_key] = key
    jobs = sorted((assess(job) for _, job in by_url.values()), key=personal_rank, reverse=True)
    with LOCK:
        CACHE.update(jobs=jobs)
    return len(jobs)


def refresh():
    with LOCK:
        CACHE.update(refreshing=True, sources={name: {'status': 'pending', 'loaded': 0} for name in SOURCE_NAMES})
    try:
        ordered = sorted(SOURCE_NAMES, key=lambda n: n not in ('KARIERA.mk', 'Vrabotuvanje MK', 'Workable · SupportYourApp', 'Jobicy · Sprachsuche'))
        with ThreadPoolExecutor(max_workers=12) as pool:
            futures = {pool.submit(fetch_source, name): name for name in ordered}
            for future in as_completed(futures):
                name = futures[future]
                last = SOURCE_CACHE.get(name)
                try:
                    result = future.result()
                    rows, errors = result if isinstance(result, tuple) else (result, [])
                    SOURCE_CACHE[name] = time.time(), rows
                    state = {'status': 'partial' if errors else 'ok', 'loaded': len(rows),
                             'error': f'{len(errors)} Teilabfragen fehlgeschlagen. {errors[0]}' if errors else '',
                             'checked_at': time.time()}
                except Exception as error:
                    stale = bool(last and time.time() - last[0] <= MAX_STALE)
                    state = {'status': 'stale' if stale else 'error', 'loaded': len(last[1]) if stale else 0,
                             'error': str(error)[:220], 'checked_at': time.time()}
                with LOCK:
                    CACHE['sources'][name] = state
                if name in ordered[:4] or name=='Remotive':
                    publish_snapshot()
        return publish_snapshot()
    finally:
        with LOCK:
            CACHE.update(at=time.time(), refreshing=False)


def run_refresh():
    try:
        refresh()
    finally:
        REFRESH_LOCK.release()


def start_refresh():
    if not REFRESH_LOCK.acquire(blocking=False):
        return False
    with LOCK:
        if time.time() - CACHE['at'] < REFRESH_INTERVAL:
            REFRESH_LOCK.release()
            return False
        CACHE['refreshing'] = True
    threading.Thread(target=run_refresh, daemon=True).start()
    return True


def refresh_periodically():
    while True:
        start_refresh()
        time.sleep(30)


def select_jobs(jobs, query):
    def first(key, default=''):
        return query.get(key, [default])[0]

    show = first('show', 'recommended')
    if show == 'confirmed':
        show = 'recommended'
    if show not in ('recommended', 'review', 'possible', 'excluded', 'all'):
        show = 'recommended'
    search = first('q').casefold().split()
    industries = set(query.get('industry', []))
    modes = set(query.get('mode', []))
    languages = set(query.get('language', []))
    selected = []
    now = time.time()
    for job in jobs:
        if job.get('expires_at') and job['expires_at'] <= now:
            continue
        if now - job.get('source_checked_at', now) > MAX_STALE:
            continue
        if show != 'all' and job['category'] != show:
            continue
        if industries and not industries.intersection(job['industries']):
            continue
        if modes and job['work_mode'] not in modes:
            continue
        if languages and not languages.intersection(job['languages']) and not (
                'balkan' in languages and job['balkan_language'] or str(job['language_tier']) in languages):
            continue
        if first('balkan') == '1' and not job['balkan_language']:
            continue
        if first('salary') == '1' and not job['salary']:
            continue
        english = first('english')
        if english == 'not_required' and job['english_level'] == 'advanced':
            continue
        if english == 'basic' and job['english_level'] != 'basic':
            continue
        geo = first('location')
        if geo == 'not_excluded' and job['location_status'] == 'excluded':
            continue
        if geo in ('confirmed', 'worldwide', 'unknown', 'excluded') and job['location_status'] != geo:
            continue
        if search:
            haystack = ' '.join(job[k] for k in ('title', 'company', 'description', 'location')).casefold()
            if not all(word in haystack for word in search):
                continue
        selected.append(job)
    return selected


class Handler(BaseHTTPRequestHandler):
    def send_data(self, data, content_type, status=200):
        self.send_response(status)
        self.send_header('Content-Type', content_type)
        self.send_header('Cache-Control', 'no-store')
        self.send_header('Content-Length', str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def respond(self, obj, status=200):
        self.send_data(json.dumps(obj, ensure_ascii=False).encode(), 'application/json; charset=utf-8', status)

    def do_GET(self):
        path = urllib.parse.urlsplit(self.path)
        if path.path == '/':
            self.send_data((BASE / 'index.html').read_bytes(), 'text/html; charset=utf-8')
            return
        with LOCK:
            jobs, sources, synced, running = CACHE['jobs'], dict(CACHE['sources']), CACHE['at'], CACHE['refreshing']
        state = dict(last_sync=synced, sources=sources, refreshing=running)
        if path.path == '/api/status':
            self.respond(dict(state, total=len(jobs), configured_sources=SOURCE_NAMES, version='8.0'))
        elif path.path == '/api/jobs':
            query = urllib.parse.parse_qs(path.query)
            selected = select_jobs(jobs, query)
            size = 25
            pages = max(1, (len(selected) + size - 1) // size)
            page = query.get('page', ['1'])[0]
            page = int(page) if re.fullmatch(r'[0-9]{1,6}', page) else 1
            page = max(1, min(page, pages))
            self.respond(dict(state, jobs=selected[(page-1)*size:page*size], count=len(selected),
                              page=page, pages=pages))
        else:
            self.respond({'error': 'Pfad nicht gefunden'}, 404)

    def do_POST(self):
        if self.path != '/api/refresh':
            return self.respond({'error': 'Pfad nicht gefunden'}, 404)
        started = start_refresh()
        with LOCK:
            result = dict(total=len(CACHE['jobs']), sources=dict(CACHE['sources']),
                          refreshing=CACHE['refreshing'], cached=not started)
        self.respond(result, 202 if result['refreshing'] else 200)


if __name__ == '__main__':
    port = int(os.getenv('PORT', '8765'))
    print(f'Meister 8.0: http://127.0.0.1:{port}', flush=True)
    start_refresh()
    threading.Thread(target=refresh_periodically, daemon=True).start()
    ThreadingHTTPServer(('0.0.0.0', port), Handler).serve_forever()
