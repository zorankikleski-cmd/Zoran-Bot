#!/usr/bin/env python3
"""Meister 7.0: stdlib local web service. No authentication: do not expose publicly."""
import json, re, html, os, time, threading, urllib.request, urllib.parse, urllib.error, hashlib
from http.server import ThreadingHTTPServer, BaseHTTPRequestHandler
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor, as_completed
BASE=Path(__file__).resolve().parent
CACHE={'at':0,'jobs':[],'sources':{}}
LOCK=threading.Lock()
REFRESH_LOCK=threading.Lock()
UA={'User-Agent':'BalkanRemoteCareerMeister/7.0 (personal job research; contact via operator)','Accept':'application/json'}
ATS_BOARDS={
 'Greenhouse · GitLab':('greenhouse','gitlab','GitLab'),
 'Greenhouse · Automattic':('greenhouse','automattic','Automattic'),
 'Greenhouse · Remote':('greenhouse','remote','Remote'),
 'Lever · Canonical':('lever','canonical','Canonical'),
 'Lever · Wikimedia':('lever','wikimedia','Wikimedia'),
 'Ashby · Deel':('ashby','deel','Deel'),
 'Ashby · Linear':('ashby','linear','Linear'),
}
SOURCE_NAMES=['Remotive','Arbeitnow','Jobicy','Remote OK','Himalayas',*ATS_BOARDS]
KEYWORDS=['recruit','talent acquisition','hr','human resources','personal','customer success','customer support','kundenservice','project coordinator','projekt','telecom','fiber','glasfaser','operations','team lead','teamleiter','quality','training','onboarding','account management','dolmetscher','interpreter','translator','german','deutsch','balkan','macedonian','administration','office','property','tourism','logistics','insurance','fintech']
NEGATIVE=re.compile(r'cold.call|cold.calling|kaltakquise|door.to.door|outbound sales|telemarketing|commission.only|provision.only|doorstep sales',re.I)
SCAM=re.compile(r'(?:pay|send|transfer|deposit|überweis|bezahlen|zahlung|gebühr).{0,70}(?:application fee|registration fee|training fee|equipment fee|bewerbungsgebühr|einstellungsgebühr|vorab|before (?:you )?start)|(?:application fee|registration fee|training fee|equipment fee|bewerbungsgebühr|einstellungsgebühr).{0,70}(?:pay|transfer|deposit|überweis|bezahlen|zahlung)',re.I)
ENGLISH=re.compile(r'english\s*(?:b2|c1|c2|fluency|fluent|proficien|mandatory|required|essential)|(?:fluent|proficient|strong|excellent)\s+(?:written\s+and\s+spoken\s+)?english|englisch\s*(?:b2|c1|c2|pflicht|erforderlich|fließend|verhandlungssicher)',re.I)
GERMAN=re.compile(r'\b(?:german|deutsch|deutschsprachig|german.speaking)\b',re.I)
EXCLUDE=re.compile(r'\b(?:eu residents only|eu only|european union only|eea only|germany only|must reside in germany|based in germany|within germany only|us only|usa only|united states only|uk only|must be located in the uk|dach only|eu/eea only)\b',re.I)
ALLOW=re.compile(r'\b(?:north macedonia|nordmazedonien|macedonia|ohrid)\b',re.I)
WORLD=re.compile(r'\b(?:worldwide|anywhere in the world|globally remote|work from anywhere|global remote)\b',re.I)
REMOTE=re.compile(r'\b(?:remote|home[ -]?office|homeoffice|work[ -]?from[ -]?home|wfh|fully distributed|telework|telecommut|100\s*%\s*(?:remote|homeoffice)|ortsunabhängig|von zuhause|von zu hause|mobiles arbeiten|distributed team|anywhere)\b',re.I)
TITLES={'recruit':'Bewerber finden, Lebensläufe prüfen, Gespräche führen und Einstellungen begleiten.','talent':'Bewerber suchen, Gespräche organisieren und Personalentscheidungen unterstützen.','hr':'Personalunterlagen pflegen, Mitarbeitende betreuen und HR-Prozesse koordinieren.','customer support':'Kundenfragen beantworten, Probleme lösen und Vorgänge dokumentieren.','customer success':'Bestandskunden betreuen, Probleme koordinieren und die Nutzung von Dienstleistungen verbessern.','project':'Aufgaben, Termine und beteiligte Teams koordinieren und den Projektfortschritt verfolgen.','operations':'Abläufe organisieren, Kennzahlen prüfen und Teams bei der täglichen Arbeit unterstützen.','telecom':'Telekommunikationsprojekte, Kunden oder Partner koordinieren.','fiber':'Glasfaserprojekte und beteiligte Dienstleister koordinieren.','translator':'Gespräche oder Texte zwischen Sprachen übertragen.','interpreter':'Gespräche und Meetings mündlich übersetzen.','training':'Mitarbeitende einarbeiten, Schulungen durchführen und Lernfortschritte begleiten.'}
def clean(x):
 if not isinstance(x,str):return ''
 return re.sub(r'\s+',' ',html.unescape(re.sub(r'<[^>]+>',' ',x))).strip()[:14000]
def get(url):
 req=urllib.request.Request(url,headers=UA)
 with urllib.request.urlopen(req,timeout=13) as r:
  if r.status!=200:raise ValueError('HTTP '+str(r.status))
  data=r.read(9_000_000)
  return json.loads(data)
def row(source,title,company,description,location,url,salary='',date='',raw_id=''):
 if not title or not url or not str(url).startswith('https://'):return None
 return {'source':source,'title':clean(str(title))[:180],'company':clean(str(company))[:150],'description':clean(str(description)),'location':clean(str(location))[:240],'url':str(url),'salary':clean(str(salary))[:200],'date':str(date)[:32],'id':str(raw_id)}
def fetch_source(name):
 jobs=[]
 if name in ATS_BOARDS:
  kind,board,company=ATS_BOARDS[name]
  if kind=='greenhouse':
   d=get('https://boards-api.greenhouse.io/v1/boards/'+board+'/jobs?content=true')
   for x in d.get('jobs',[]):jobs.append(row(name,x.get('title'),company,x.get('content',''),(x.get('location') or {}).get('name',''),x.get('absolute_url'),'',x.get('updated_at'),x.get('id')))
  elif kind=='lever':
   d=get('https://api.lever.co/v0/postings/'+board+'?mode=json')
   for x in d if isinstance(d,list) else []:
    cats=x.get('categories') or {}
    jobs.append(row(name,x.get('text'),company,x.get('descriptionPlain') or x.get('description') or '',cats.get('location',''),x.get('hostedUrl'),'', '',x.get('id')))
  elif kind=='ashby':
   d=get('https://api.ashbyhq.com/posting-api/job-board/'+board+'?includeCompensation=true')
   for x in d.get('jobs',[]):
    if x.get('isListed') is False:continue
    jobs.append(row(name,x.get('title'),company,x.get('descriptionPlain') or x.get('descriptionHtml') or '',x.get('location',''),x.get('jobUrl') or x.get('applyUrl'),(x.get('compensation') or {}).get('compensationTierSummary','') if isinstance(x.get('compensation'),dict) else '',x.get('publishedAt'),x.get('id')))
 elif name=='Remotive':
  d=get('https://remotive.com/api/remote-jobs?limit=500')
  for x in d.get('jobs',[]):jobs.append(row(name,x.get('title'),x.get('company_name'),x.get('description'),x.get('candidate_required_location'),x.get('url'),x.get('salary'),x.get('publication_date'),x.get('id')))
 elif name=='Arbeitnow':
  url='https://www.arbeitnow.com/api/job-board-api'
  for page in range(3):
   d=get(url)
   for x in d.get('data',[]):jobs.append(row(name,x.get('title'),x.get('company_name'),x.get('description'),x.get('location'),x.get('url'),'',x.get('created_at'),x.get('slug')))
   nxt=d.get('links',{}).get('next') or d.get('next')
   if not nxt or not str(nxt).startswith('https://www.arbeitnow.com/'):break
   url=nxt
 elif name=='Jobicy':
  d=get('https://jobicy.com/api/v2/remote-jobs?count=100')
  for x in d.get('jobs',[]):jobs.append(row(name,x.get('jobTitle'),x.get('companyName'),x.get('jobDescription'),x.get('jobGeo'),x.get('url'),str(x.get('annualSalaryMin') or '')+' '+str(x.get('annualSalaryMax') or ''),x.get('pubDate'),x.get('id')))
 elif name=='Remote OK':
  d=get('https://remoteok.com/api')
  for x in d if isinstance(d,list) else []:
   if not isinstance(x,dict):continue
   jobs.append(row(name,x.get('position'),x.get('company'),x.get('description'),x.get('location') or ', '.join(x.get('tags',[])[:5]),x.get('url'),x.get('salary') or '',x.get('date'),x.get('id')))
 elif name=='Himalayas':
  # API terms: use original applicationLink and display source credit.
  for offset in (0,20,40,60,80):
   d=get('https://himalayas.app/jobs/api?limit=20&offset='+str(offset))
   for x in d.get('jobs',[]):
    company=x.get('companyName') or (x.get('company') or {}).get('name','') if isinstance(x.get('company'),dict) else x.get('companyName','')
    loc=', '.join(str(v) for v in (x.get('locationRestrictions') or [])) if isinstance(x.get('locationRestrictions'),list) else str(x.get('locationRestrictions') or '')
    if x.get('worldwide'):loc+=' worldwide'
    sal=' '.join(str(x.get(k) or '') for k in ('minSalary','maxSalary','currency','salaryPeriod'))
    jobs.append(row(name,x.get('title'),company,x.get('description'),loc,x.get('applicationLink'),sal,x.get('pubDate') or x.get('publishedAt'),x.get('guid')))
 return [j for j in jobs if j]
# Conservative classification: unknown is not an approval. Check location metadata first.
# Job suitability must come from the JOB TITLE, never a substring of a company name.
TITLE_GOOD=re.compile(r'\b(?:recruit(?:er|ing|ment)?|talent acquisition|talent sourc(?:er|ing)|personnel|personal(?:wesen|referent|betreuung|administration|management)|hr|human resources|people operations|onboarding|telecom(?:munications)?|telekommunikation|fiber|fibre|glasfaser|dsl|mobilfunk|project coordinator|project manager|projekt(?:leitung|koordination|manager|management)|rollout|customer success|customer support|customer service|kunden(?:betreuung|service|beratung)|client support|operations|team(?:lead|leiter|leitung)|training|quality assurance|qualitätsmanagement|administration|back[ -]?office|office manager|translat(?:or|ion)|interpret(?:er|ation)|dolmetscher|sprachmittler|macedonian|balkan|property manager|immobilien|touris(?:m|mus)|travel coordinator|service coordinator|support specialist|customer care|account support)\b',re.I)
TITLE_BAD=re.compile(r'\b(?:software engineer|software developer|developer|devops|data scientist|machine learning|data engineer|solutions? architect|cloud architect|customer success (?:engineer|architect)|technical support engineer|support engineer|python developer|python engineer|operations (?:engineer|expert with python)|nurse|physician|account executive|sales development representative|business development representative|sales manager|sales representative|growth marketer|graphic designer|product designer|warehouse|forklift|staplerfahrer|lagerlogistik|lagerarbeiter|fahrer|driver|mechanic|mechaniker|electrician|elektriker|koch|chef de partie|waiter|security guard)\b',re.I)
# High-skill technical requirements are a poor match even when the title is broad.
TECH_REQUIREMENT=re.compile(r'\b(?:python|javascript|typescript|kubernetes|terraform|aws|azure|sql|api integration|software development|programming|coding)\b',re.I)
# Explicitly country-scoped listings must not be mistaken for location-flexible remote work.
COUNTRY_SCOPE=re.compile(r'\b(?:japan|france|frankreich|japon|japan only|paris|tokyo|poland|polen|spain|spanien|portugal|italy|italien|netherlands|niederlande|belgium|belgien|sweden|schweden|denmark|dänemark|norway|norwegen|ireland|irland|brazil|brasilien|argentina|colombia|kolumbien|south africa|südafrika)\b',re.I)

# Geographic exclusions apply to advertised work locations, not to incidental country names in the description.
REGION_LIMIT=re.compile(r'\b(?:apj|apac|latam|north america|south america|australia|singapore|mexico|united states|usa|canada|india|philippines|germany|deutschland|austria|österreich|switzerland|schweiz|uk|united kingdom)\b',re.I)
EUROPE_ONLY=re.compile(r'\b(?:eu only|eu residents only|europe only|european union only|eea only|must be (?:based|located|resident) in (?:the )?(?:eu|europe|germany|uk|us)|(?:us|uk|germany|australia|singapore|mexico) only)\b',re.I)
GERMAN_REQUIRED=re.compile(r'(?:fluent|native|proficient|excellent|business.level|c1|c2|b2|must speak|required|mandatory).{0,35}\bgerman\b|\bgerman\b.{0,35}(?:required|mandatory|fluent|native|c1|c2|b2)|\bdeutsch\b.{0,35}(?:erforderlich|pflicht|muttersprache|fließend|c1|c2|b2)|(?:deutschsprachig|german.speaking)',re.I)
SHIFT_BAD=re.compile(r'\b(?:night shifts?|overnight shifts?|weekend shifts?|rotating shifts?|nachtschicht|wochenendschicht)\b',re.I)
TASK_PATTERNS=[
 (r'recruit|talent|sourc|personal|\bhr\b|human resources|people operations', 'Bewerber suchen und ansprechen, Lebensläufe sichten, Interviews koordinieren und die Einstellung begleiten.'),
 (r'glasfaser|fiber|fibre|telecom|telekommun|dsl|mobilfunk|rollout','Kunden, Techniker und Dienstleister koordinieren, Aufträge nachverfolgen und technische Vorgänge dokumentieren.'),
 (r'projekt|project|coordinator|operations','Termine und Aufgaben abstimmen, Teams koordinieren, Fortschritte dokumentieren und Probleme lösen.'),
 (r'customer|kunden|support|service|client|account support','Kundenanfragen bearbeiten, Lösungen erklären und Vorgänge im System dokumentieren. Die benötigte Sprache bitte in der Anzeige prüfen.'),
 (r'team lead|teamleiter|teamleitung|management','Mitarbeitende unterstützen, Aufgaben verteilen, Qualität prüfen und Arbeitsabläufe verbessern.'),
 (r'translat|interpret|dolmetsch|sprachmittl','Gespräche oder Dokumente zwischen den geforderten Sprachen übersetzen.'),
 (r'immobil|property','Kunden und Objekte betreuen, Termine organisieren und Anfragen bearbeiten.'),
 (r'touris|travel','Reiseanfragen bearbeiten, Buchungen und Abläufe koordinieren und Kunden betreuen.'),
]
def assess(j):
 title=j['title'];desc=j['description'];loc=j['location'];head=desc[:5000]
 full=title+' '+head
 german=bool(GERMAN.search(full));german_required=bool(GERMAN_REQUIRED.search(full))
 english=bool(ENGLISH.search(full));sales=bool(NEGATIVE.search(full));scam=bool(SCAM.search(full));shift=bool(SHIFT_BAD.search(full))
 # A remote job board alone is not evidence that every job is remote.
 remote=bool(REMOTE.search(title+' '+loc+' '+head[:1200]))
 jobfit=bool(TITLE_GOOD.search(title)) and not bool(TITLE_BAD.search(title))
 technical=bool(TECH_REQUIREMENT.search(title)) or (bool(re.search(r'\b(?:engineer|architect|developer|data|technical)\b',title,re.I)) and bool(TECH_REQUIREMENT.search(head)))
 allowed=bool(ALLOW.search(loc)) or bool(re.search(r'(?:work|remote|based|located|hire|employ).{0,45}(?:north macedonia|nordmazedonien|ohrid)',head,re.I))
 worldwide=bool(WORLD.search(loc)) or bool(re.search(r'(?:eligible|hiring|work|remote|location).{0,45}(?:worldwide|anywhere in the world|globally)',head[:1500],re.I))
 restricted=bool(EXCLUDE.search(loc+' '+head[:1500])) or bool(EUROPE_ONLY.search(loc+' '+head[:1500]))
 region=bool(REGION_LIMIT.search(loc) or COUNTRY_SCOPE.search(loc)) and not allowed and not worldwide
 excluded_location=restricted or region
 ohrid='ausgeschlossen' if excluded_location else ('Nordmazedonien genannt, Freigabe prüfen' if allowed else ('Weltweit ausgeschrieben, Freigabe prüfen' if worldwide else 'ungeklärt'))
 # Evidence-based ranking, not an application-success probability.
 score=10+(27 if jobfit else 0)+(23 if german_required else (14 if german else 0))+(15 if remote else 0)+(15 if allowed else (9 if worldwide else 0))
 if english:score-=14
 if sales:score-=28
 if shift:score-=12
 if not remote:score-=22
 if not jobfit:score-=35
 if technical:score-=28
 if excluded_location:score=min(score,10)
 if not german:score=min(score,35)
 if technical:score=min(score,15)
 score=max(0,min(95,score))
 excluded=excluded_location or sales or scam or shift or not jobfit or not remote or technical
 # Three useful groups: confirmed geography, strong potential, and language still to check.
 if excluded:category='excluded'
 elif german and (allowed or worldwide):category='recommended'
 elif german:category='review'
 else:category='possible'
 status={'recommended':'Fachlich passend · Standortfreigabe vor Bewerbung bestätigen',
         'review':'Interessant · Homeoffice aus Ohrid beim Arbeitgeber klären',
         'possible':'Nur zur weiteren Prüfung · Deutsch und Ohrid nicht bestätigt',
         'excluded':'Nicht für deine normale Suche empfohlen'}[category]
 duties=next((text for pattern,text in TASK_PATTERNS if re.search(pattern,title,re.I)),
             'Die täglichen Aufgaben sind aus dem Stellentitel nicht zuverlässig ableitbar. Bitte die Originalanzeige prüfen.')
 notes=[]
 if not german:notes.append('Deutsch nicht nachgewiesen')
 if english:notes.append('Gute Englischkenntnisse verlangt, bitte prüfen')
 if not allowed:notes.append('Beschäftigung aus Nordmazedonien nicht bestätigt')
 if excluded_location:notes.append('Ausgeschriebene Region passt nicht zu Ohrid')
 if sales:notes.append('Kaltakquise/aktiver Vertrieb erwähnt')
 if shift:notes.append('Nacht-/Wochenendschichten erwähnt')
 if scam:notes.append('Mögliche Vorauszahlung/Gebühren')
 if not remote:notes.append('Homeoffice/Remote nicht nachgewiesen')
 if not jobfit:notes.append('Berufsprofil passt nicht')
 if technical:notes.append('Technische Spezialkenntnisse erforderlich oder wahrscheinlich')
 return dict(j,fit=score,language='Deutsch gefordert' if german_required else ('Deutsch erwähnt' if german else 'Deutsch nicht nachgewiesen'),english='Englischpflicht erkannt' if english else 'Englischpflicht nicht belegt',ohrid=ohrid,scam='kritischer Warnhinweis' if scam else 'Arbeitgeber nicht unabhängig verifiziert',excluded=excluded,category=category,status=status,notes=notes,duties=duties)

def refresh():
 sources={};alljobs=[]
 with ThreadPoolExecutor(max_workers=6) as pool:
  futures={pool.submit(fetch_source,n):n for n in SOURCE_NAMES}
  for f in as_completed(futures):
   n=futures[f]
   try:
    rows=f.result();sources[n]={'status':'ok','loaded':len(rows),'error':''};alljobs.extend(rows)
   except Exception as e:sources[n]={'status':'error','loaded':0,'error':str(e)[:180]}
 seen=set();unique=[]
 for j in alljobs:
  key=(j['company'].lower().strip(),j['title'].lower().strip(),j['location'].lower().strip())
  if key in seen:continue
  seen.add(key);unique.append(assess(j))
 unique.sort(key=lambda j:({'recommended':3,'review':2,'possible':1,'excluded':0}[j['category']],j['fit']),reverse=True)
 with LOCK:CACHE.update(at=time.time(),jobs=unique,sources=sources)
 return len(unique)
class Handler(BaseHTTPRequestHandler):
 def respond(self,obj,status=200):
  data=json.dumps(obj,ensure_ascii=False).encode();self.send_response(status);self.send_header('Content-Type','application/json; charset=utf-8');self.send_header('Cache-Control','no-store');self.send_header('Content-Length',str(len(data)));self.end_headers();self.wfile.write(data)
 def do_GET(self):
  p=urllib.parse.urlsplit(self.path);q=urllib.parse.parse_qs(p.query)
  if p.path=='/':
   b=(BASE/'index.html').read_bytes();self.send_response(200);self.send_header('Content-Type','text/html; charset=utf-8');self.send_header('Cache-Control','no-store, max-age=0');self.send_header('Content-Length',str(len(b)));self.end_headers();self.wfile.write(b);return
  if p.path=='/api/status':
   with LOCK:self.respond({'last_sync':CACHE['at'],'sources':CACHE['sources'],'total':len(CACHE['jobs']),'configured_sources':SOURCE_NAMES});return
  if p.path=='/api/jobs':
   with LOCK:jobs=list(CACHE['jobs']);sources=dict(CACHE['sources']);at=CACHE['at']
   query=(q.get('q',[''])[0] or '').lower().strip();show=q.get('show',['recommended'])[0]
   if query:jobs=[j for j in jobs if query in (' '.join((j['title'],j['company'],j['description']))).lower()]
   if show=='recommended':jobs=[j for j in jobs if j['category']!='excluded']
   elif show=='confirmed':jobs=[j for j in jobs if j['category']=='recommended']
   elif show=='review':jobs=[j for j in jobs if j['category']=='review']
   elif show=='possible':jobs=[j for j in jobs if j['category']=='possible']
   elif show=='excluded':jobs=[j for j in jobs if j['category']=='excluded']
   page=max(1,min(10000,int(q.get('page',['1'])[0]) if q.get('page',['1'])[0].isdigit() else 1));size=25
   self.respond({'jobs':jobs[(page-1)*size:page*size],'count':len(jobs),'page':page,'pages':max(1,(len(jobs)+size-1)//size),'sources':sources,'last_sync':at});return
  self.respond({'error':'not found'},404)
 def do_POST(self):
  if self.path!='/api/refresh':return self.respond({'error':'not found'},404)
  # Prevent unbounded public API requests. Cached results remain available.
  with LOCK:
   age=time.time()-CACHE['at']
  if age < 900:
   return self.respond({'total':len(CACHE['jobs']),'sources':CACHE['sources'],'cached':True})
  if not REFRESH_LOCK.acquire(blocking=False):
   return self.respond({'error':'Eine Suche läuft bereits. Bitte kurz warten.'},429)
  try:
   count=refresh();self.respond({'total':count,'sources':CACHE['sources'],'cached':False})
  finally:REFRESH_LOCK.release()
if __name__=='__main__':
 port=int(os.getenv('PORT','8765'))
 print('Meister 7.0: http://127.0.0.1:'+str(port),flush=True)
 ThreadingHTTPServer(('0.0.0.0',port),Handler).serve_forever()
