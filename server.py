#!/usr/bin/env python3
"""Meister 7.0: stdlib local web service. No authentication: do not expose publicly."""
import json, re, html, os, time, threading, urllib.request, urllib.parse, urllib.error, hashlib, xml.etree.ElementTree as ET
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
 'Greenhouse · Personio':('greenhouse','personio','Personio'),
 'Greenhouse · SumUp':('greenhouse','sumup','SumUp'),
 'Greenhouse · N26':('greenhouse','n26','N26'),
 'Greenhouse · Miro':('greenhouse','miro','Miro'),
 'Greenhouse · HelloFresh':('greenhouse','hellofresh','HelloFresh'),
 'Greenhouse · SupportYourApp':('greenhouse','supportyourapp','SupportYourApp'),
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
 'Lever · Bitpanda':('lever','bitpanda','Bitpanda'),
 'Ashby · Remote':('ashby','remote','Remote'),
 'Lever · Remote.com':('lever','remote','Remote.com'),
}
SOURCE_NAMES=['Remotive','We Work Remotely · RSS','Arbeitnow','Jobicy','Remote OK','Himalayas','The Muse · Jobs','RemoteJobs.org · Jobs','Working Nomads',*ATS_BOARDS]

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
 elif name.startswith('Remotive'):
  term={'Remotive · German':'german','Remotive · Customer Support':'customer support','Remotive · Recruiting':'recruiter','Remotive · Balkan':'macedonian','Remotive · Travel':'german travel','Remotive · Translator':'german translator','Remotive · German Support':'german customer support','Remotive · German HR':'german recruiting','Remotive · German Telecom':'german telecommunications','Remotive · German Freelance':'german freelance','Remotive · Croatian':'croatian','Remotive · Serbian':'serbian','Remotive · Bosnian':'bosnian','Remotive · Macedonian':'macedonian','Remotive · German Homeoffice':'german home office'}.get(name)
  endpoint='https://remotive.com/api/remote-jobs?limit=500'
  if term:endpoint+='&search='+urllib.parse.quote(term)
  d=get(endpoint)
  for x in d.get('jobs',[]):jobs.append(row(name,x.get('title'),x.get('company_name'),x.get('description'),x.get('candidate_required_location'),x.get('url'),x.get('salary'),x.get('publication_date'),x.get('id')))
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
   jobs.append(row(name,title,company,description,'Remote, Standortbedingungen prüfen',link,'',date,link))
 elif name=='Arbeitnow':
  url='https://www.arbeitnow.com/api/job-board-api'
  for page in range(15):
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
 elif name=='The Muse · Jobs':
  for page in range(1,6):
   d=get('https://www.themuse.com/api/public/jobs?page='+str(page))
   for x in d.get('results',[]):
    loc=', '.join(v.get('name','') for v in x.get('locations',[]) if isinstance(v,dict))
    company=(x.get('company') or {}).get('name','')
    jobs.append(row(name,x.get('name'),company,x.get('contents',''),loc,x.get('refs',{}).get('landing_page'),'',x.get('publication_date'),x.get('id')))
   if page>=d.get('page_count',page):break
 elif name=='RemoteJobs.org · Jobs':
  d=get('https://remotejobs.org/api/v1/jobs?limit=100')
  for x in d.get('data',[]) if isinstance(d,dict) else []:
   company=x.get('company',{})
   if isinstance(company,dict):company=company.get('name','')
   jobs.append(row(name,x.get('title'),company,x.get('description',''),x.get('location',''),x.get('url') or x.get('apply_url'),'',x.get('created_at'),x.get('id')))
 elif name=='Working Nomads':
  d=get('https://www.workingnomads.com/api/exposed_jobs/')
  for x in d if isinstance(d,list) else (d.get('jobs',[]) if isinstance(d,dict) else []):
   jobs.append(row(name,x.get('title'),x.get('company_name') or x.get('company'),x.get('description',''),x.get('location',''),x.get('url') or x.get('link'),x.get('salary',''),x.get('date',''),x.get('id','')))
 elif name=='Himalayas':
  # API terms: use original applicationLink and display source credit.
  cursor=None
  for _ in range(18):
   endpoint='https://himalayas.app/jobs/api?limit=20'
   if cursor:endpoint+='&cursor='+urllib.parse.quote(cursor)
   d=get(endpoint)
   for x in d.get('jobs',[]):
    company=x.get('companyName') or (x.get('company') or {}).get('name','') if isinstance(x.get('company'),dict) else x.get('companyName','')
    loc=', '.join(str(v) for v in (x.get('locationRestrictions') or [])) if isinstance(x.get('locationRestrictions'),list) else str(x.get('locationRestrictions') or '')
    if x.get('worldwide') or not x.get('locationRestrictions'):loc='Worldwide' if not loc else loc+' worldwide'
    sal=' '.join(str(x.get(k) or '') for k in ('minSalary','maxSalary','currency','salaryPeriod'))
    jobs.append(row(name,x.get('title'),company,x.get('description'),loc,x.get('applicationLink'),sal,x.get('pubDate') or x.get('publishedAt'),x.get('guid')))
   cursor=d.get('nextCursor')
   if not cursor:break
 return [j for j in jobs if j]
# Conservative classification: unknown is not an approval. Check location metadata first.
# Job suitability must come from the JOB TITLE, never a substring of a company name.
TITLE_GOOD=re.compile(r'\b(?:recruit(?:er|ing|ment)?|talent acquisition|talent sourc(?:er|ing)|personnel|personal(?:wesen|referent|betreuung|administration|management)|hr|human resources|people operations|onboarding|telecom(?:munications)?|telekommunikation|fiber|fibre|glasfaser|dsl|mobilfunk|project coordinator|project manager|projekt(?:leitung|koordination|manager|management)|rollout|customer success|customer support|customer service|kunden(?:betreuung|service|beratung)|client support|operations|team(?:lead|leiter|leitung)|training|quality assurance|qualitätsmanagement|administration|back[ -]?office|office manager|translat(?:or|ion)|interpret(?:er|ation)|dolmetscher|sprachmittler|macedonian|balkan|property manager|immobilien|touris(?:m|mus)|travel coordinator|service coordinator|support specialist|customer care|account support)\b',re.I)
TITLE_BAD=re.compile(r'\b(?:software engineer|software developer|developer|devops|data scientist|machine learning|data engineer|solutions? architect|cloud architect|customer success (?:engineer|architect)|technical support engineer|support engineer|python developer|python engineer|operations (?:engineer|expert with python)|nurse|physician|account executive|sales development representative|business development representative|sales manager|sales representative|growth marketer|graphic designer|product designer|warehouse|forklift|staplerfahrer|lagerlogistik|lagerarbeiter|fahrer|driver|mechanic|mechaniker|electrician|elektriker|koch|chef de partie|waiter|security guard)\b',re.I)
# High-skill technical requirements are a poor match even when the title is broad.
TECH_REQUIREMENT=re.compile(r'\b(?:python|javascript|typescript|kubernetes|terraform|aws|azure|sql|api integration|software development|programming|coding)\b',re.I)
# Explicitly country-scoped listings must not be mistaken for location-flexible remote work.
COUNTRY_SCOPE=re.compile(r'\b(?:greece|griechenland|serbia|serbien|croatia|kroatien|bosnia|bosnien|bulgaria|bulgarien|romania|rumänien|japan|france|frankreich|japon|japan only|paris|tokyo|poland|polen|spain|spanien|portugal|italy|italien|netherlands|niederlande|belgium|belgien|sweden|schweden|denmark|dänemark|norway|norwegen|ireland|irland|brazil|brasilien|argentina|colombia|kolumbien|south africa|südafrika)\b',re.I)

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
# Language evidence is a hard priority. Do not infer a German-speaking role from
# the employer's location or a stray country name in the description.
GERMAN_MUST=re.compile(r'(?:german[ -]speaking|german[ -]language|deutschsprachig|deutschkenntnisse|deutsche sprache|german fluency|fluent (?:in )?german|native (?:level )?german|german (?:required|mandatory|essential|speaker|c1|c2|b2)|deutsch (?:c1|c2|b2|erforderlich|fließend|muttersprache)|(?:german|deutsch).{0,30}(?:required|mandatory|essential|erforderlich|voraussetzung|c1|c2|b2))',re.I)
GERMAN_PLUS=re.compile(r'(?:german|deutsch).{0,45}(?:preferred|nice to have|plus|advantage|von vorteil|wünschenswert)|(?:preferred|nice to have|plus|advantage|von vorteil|wünschenswert).{0,45}(?:german|deutsch)',re.I)
BALKAN_LANGUAGE=re.compile(r'\b(?:macedonian|mazedonisch|serbian|serbisch|croatian|kroatisch|bosnian|bosnisch|bcs|bcs[ -]language|serbo[ -]croatian)\b',re.I)
SERVICE_TITLE=re.compile(r'(?:first[ -]?level|second[ -]?level|1st[ -]?level|2nd[ -]?level|level[ -]?[12]|l[12][ -]?support|help[ -]?desk|service[ -]?desk|it[ -]?support)|(?:customer|kunden|client|service|support|care|call[ -]?cent(?:er|re)|contact cent(?:er|re)|reise|travel|touris|booking|reserv|telecom|telekommun|mobilfunk|dsl|glasfaser|recruit|talent|personal|human resources|\bhr\b|teamlead|teamleiter|coordinator|koordinator|back[ -]?office|operations|projekt|project|interpreter|translator|dolmetsch|sprachmittl|amazon|logistics|logistik)',re.I)
SPECIFIC_BAD=re.compile(r'(?:\b(?:engineer|architect|developer|programmer|software|data scientist|machine learning|\bpython\b|\bsql\b|\bjava\b|\breact\b|\bcybersecurity\b|\bphysician\b|\bnurse\b|psycholog|psychologu|\bfrancophone\b|\(fr\)|\(jp\))\b)',re.I)
US_STATE=re.compile(r'\b(?:usa|united states|us only|u\.?s\.? residents|dallas|texas|seattle|washington|ohio|california|new york|florida|chicago|boston|japan|tokyo|france|paris|australia|singapore|canada|mexico|india|philippines)\b',re.I)
LANGUAGE_OTHER=re.compile(r'(?:french|français|japanese|japonais|spanish|italian|portuguese|dutch|polish|arabic|mandarin).{0,30}(?:required|fluent|native|mandatory|c1|c2)',re.I)

# Arbeitsmodell nur anhand ausdruecklicher Hinweise, nicht aufgrund der Branche.
FREELANCE=re.compile(r'\b(?:freelanc(?:e|er|ing)|freiberuflich|freie mitarbeit|freier mitarbeiter|selbststaendig|selbstständig|independent contractor|contractor|projektauftrag|honorarvertrag|auf honorarbasis)\b',re.I)
HOME_WORK=re.compile(r'\b(?:home[ -]?office|homeoffice|work[ -]?from[ -]?home|wfh|von zuhause|von zu hause|mobiles arbeiten|telework|telecommut|remote work|remote working|hybrid|teilweise homeoffice|homeoffice nach vereinbarung)\b',re.I)
OFFICE_ONLY=re.compile(r'\b(?:on[ -]?site only|onsite only|only office work|office[ -]?based only|no remote|kein homeoffice|keine homeoffice.möglichkeit|ausschließlich vor ort|must work on.site)\b',re.I)

def classify_work_model(title,location,description):
 evidence=title+' '+location+' '+description[:2500]
 if OFFICE_ONLY.search(evidence):return 'onsite'
 # Ein Freelance-Vertrag allein ist nicht automatisch ortsunabhaengig.
 remote_evidence=bool(REMOTE.search(evidence) or HOME_WORK.search(evidence))
 freelance=bool(FREELANCE.search(title+' '+location+' '+description[:1600]))
 if freelance and remote_evidence:return 'freelance'
 if remote_evidence:
  if re.search(r'\b(?:home[ -]?office|homeoffice|hybrid|mobiles arbeiten|von zuhause|von zu hause|work[ -]?from[ -]?home|wfh)\b',title+' '+location,re.I):return 'homeoffice'
  return 'remote'
 if freelance:return 'freelance_unconfirmed'
 return 'unknown'

# Recognize language requirements in all five languages; a country name alone is not proof.
POLISH_REQUIRED=re.compile(r'(?i)(?:polish|polski|polnisch|psycholog|psychotherapist|psychiatr|psychologe|bankberater|investment banker)')
OTHER_LANGUAGE_TITLE=re.compile(r'(?i)\\b(?:polish|polski|polnisch|french|français|italian|italiano|spanish|español|dutch|nederlands|swedish|svenska|danish|dansk|norwegian|norsk|finnish|suomi|portuguese|português|japanese|japonais|arabic|arabisch|turkish|türkisch)\\b')
MK_LOCATION=re.compile(r'\b(?:north macedonia|nordmazedonien|north macedonian|macedonia|mazedonien|skopje|skopje|ohrid|bitola|bitola|tetovo|prilep|kumanovo|struga|gostivar|shtip|stip)\b',re.I)
MK_REMOTE=re.compile(r'\\b(?:north macedonia|nordmazedonien|macedonia|mazedonien)\\b',re.I)

def assess(j):
 title=j['title'];desc=j['description'];loc=j['location'];head=desc[:6000]
 full=title+' '+head
 # Explicit German requirement > German preferred > German mentioned > no proof.
 must=bool(GERMAN_MUST.search(title+' '+head[:3500]))
 plus=bool(GERMAN_PLUS.search(full)) and not must
 mention=bool(GERMAN.search(title)) or bool(re.search(r'\b(?:german|deutsch)\b',head[:2500],re.I))
 language_tier=3 if must else (2 if plus else (1 if mention else 0))
 balkan=bool(BALKAN_LANGUAGE.search(full))
 english=bool(ENGLISH.search(full));sales=bool(NEGATIVE.search(full));scam=bool(SCAM.search(full));shift=bool(SHIFT_BAD.search(full))
 work_mode=classify_work_model(title,loc,head)
 remote=work_mode in ('remote','homeoffice','freelance')
 jobfit=not bool(TITLE_BAD.search(title) or POLISH_REQUIRED.search(title) or OTHER_LANGUAGE_TITLE.search(title)) # All sectors welcome; specialized exclusions still apply
 technical=bool(SPECIFIC_BAD.search(title)) or bool(TECH_REQUIREMENT.search(title))
 mk_local=bool(MK_LOCATION.search(loc))
 allowed=mk_local or bool(re.search(r'(?:work|remote|based|located|hire|employ|applicants from).{0,45}(?:north macedonia|nordmazedonien|macedonia|mazedonien|ohrid)',head,re.I))
 worldwide=bool(WORLD.search(loc)) or bool(re.search(r'(?:eligible|hiring|work|remote|location).{0,45}(?:worldwide|anywhere in the world|globally)',head[:1500],re.I))
 restricted=bool(EXCLUDE.search(loc)) or bool(EUROPE_ONLY.search(loc+' '+head[:1200]))
 # Location metadata is stronger than marketing text saying 'global company'.
 region=bool(REGION_LIMIT.search(loc) or COUNTRY_SCOPE.search(loc) or US_STATE.search(loc)) and not allowed and not worldwide
 excluded_location=(restricted or region) and not mk_local
 ohrid='ausgeschlossen' if excluded_location else ('Arbeitsort Nordmazedonien' if mk_local else ('Nordmazedonien erwähnt, Beschäftigung prüfen' if allowed else ('Weltweit ausgeschrieben, Beschäftigung prüfen' if worldwide else 'ungeklärt')))
 score=10+(35 if bool(TITLE_GOOD.search(title) or SERVICE_TITLE.search(title)) else 0)+(35 if must else (24 if plus else (10 if mention else 0)))+(8 if balkan else 0)+(10 if remote else 0)+(8 if allowed else (4 if worldwide else 0))
 if english:score-=16
 if sales:score-=30
 if shift:score-=15
 if not remote and not mk_local:score-=30
 if not jobfit:score-=35
 if technical:score-=40
 if excluded_location:score=min(score,10)
 if not (allowed or worldwide):score=min(score,55) # Standort ungeklärt: kein Spitzenwert
 if not (TITLE_GOOD.search(title) or SERVICE_TITLE.search(title)):score=min(score,40) # Andere Berufe nicht vor relevante Support/HR-Jobs
 if not language_tier and not balkan:score=min(score,25)
 score=max(0,min(99,score))
 excluded=excluded_location or sales or scam or shift or not jobfit or (not remote and not mk_local) or technical or (bool(LANGUAGE_OTHER.search(full)) and not mention)
 if excluded:category='excluded'
 elif must and (mk_local or allowed or worldwide):category='recommended'
 elif must or plus or mention or balkan:category='review'
 else:category='possible'
 status={'recommended':'Deutsch ausdrücklich gesucht · Arbeitsort und Vertrag prüfen',
         'review':'Deutsch in Anzeige erkannt · Arbeitsort prüfen',
         'possible':'Sprache nicht belegt · nur als Reserve prüfen',
         'excluded':'Nicht für deine normale Suche empfohlen'}[category]
 duties=next((text for pattern,text in TASK_PATTERNS if re.search(pattern,title,re.I)),
             'Die täglichen Aufgaben sind aus dem Stellentitel nicht zuverlässig ableitbar. Bitte die Originalanzeige prüfen.')
 notes=[]
 if not language_tier and not balkan:notes.append('Deutsch nicht nachgewiesen')
 elif not must:notes.append('Deutsch nicht ausdrücklich als Pflicht bestätigt')
 if english:notes.append('Gute Englischkenntnisse verlangt, bitte prüfen')
 if not allowed:notes.append('Beschäftigung aus Nordmazedonien nicht bestätigt')
 if excluded_location:notes.append('Ausgeschriebene Region passt nicht zu Ohrid')
 if sales:notes.append('Kaltakquise/aktiver Vertrieb erwähnt')
 if shift:notes.append('Nacht-/Wochenendschichten erwähnt')
 if scam:notes.append('Mögliche Vorauszahlung/Gebühren')
 if not remote:notes.append('Kein Remote/Homeoffice-Nachweis; bei Stellen in Nordmazedonien Arbeitsort vor Ort prüfen')
 if not jobfit:notes.append('Spezialberuf oder Tätigkeit außerhalb der bevorzugten Aufgaben')
 if technical:notes.append('Technische Spezialkenntnisse erforderlich oder wahrscheinlich')
 if not (TITLE_GOOD.search(title) or SERVICE_TITLE.search(title)):notes.append('Andere Branche: Aufgaben in Originalanzeige prüfen')
 categories=[]
 for label,pattern in [('recruiting',r'recruit|talent acquisition|sourc|bewerber|personalreferent|personalwesen|\bhr\b'),('customer',r'kunden|customer support|customer service|call.?center|client support|backoffice|back.office|service agent|first.?level|second.?level|1st.?level|2nd.?level|level.?[12]|help.?desk|service.?desk|it.?support'),('telecom',r'telekom|telecom|glasfaser|fiber|dsl|mobilfunk'),('travel',r'reise|travel|touris|booking|hotel|reservation'),('operations',r'operations|projekt|project|team.?lead|teamleiter|koordina|administration'),('ecommerce',r'amazon|e.?commerce|online.?handel|marketplace'),('language',r'translat|übersetz|dolmetsch|interpreter|lokalisier')]:
  if re.search(pattern,title,re.I):categories.append(label)
 # Work mode is classified above from explicit evidence.
 return dict(j,fit=score,language='Deutsch ausdrücklich gefordert' if must else ('Deutsch erwünscht' if plus else ('Deutsch erwähnt' if mention else 'Deutsch nicht nachgewiesen')),english='Englischpflicht erkannt' if english else 'Englischpflicht nicht belegt',ohrid=ohrid,scam='kritischer Warnhinweis' if scam else 'Arbeitgeber nicht unabhängig verifiziert',excluded=excluded,category=category,status=status,notes=notes,duties=duties,language_tier=language_tier,balkan_language=balkan,industries=categories,work_mode=('mk_local' if mk_local and not remote else work_mode),location_confirmed=allowed,mk_local=mk_local)


# Personalised ranking: eligibility and relevant duties are gates, not small score bonuses.
ROLE_STRONG=re.compile(r'(?i)(recruit|talent|sourc|personal|human resources|\bhr\b|customer|kunden|support|service|call.?center|help.?desk|telecom|telekommun|glasfaser|fiber|dsl|mobilfunk|project|projekt|coordinat|koordinat|operations|teamlead|teamleiter|back.?office|administration|travel|reise|touris|reserv|booking|translat|übersetz|dolmetsch|interpreter|e.?commerce|amazon|logistik|logistics|immobil|property|office manager|quality|training)')
ROLE_BLOCK=re.compile(r'(?i)(psycholog|psychiatr|therapist|bankberater|investment bank|financial advisor|software|developer|engineer|architect|nurse|physician|electrician|mechanic|driver|warehouse|forklift|sales executive|sales representative|account executive|business development|cold calling|kaltakquise)')
LANG_BLOCK=re.compile(r'(?i)\b(polish|polski|polnisch|french|français|spanish|español|italian|italiano|dutch|nederlands|portuguese|português|japanese|japonais|swedish|svenska|danish|dansk|norwegian|norsk|arabic|arabisch)\b')
HYBRID=re.compile(r'(?i)\b(hybrid|hybride|hybridarbeit|teilweise homeoffice|homeoffice.tage)\b')
HOME_EXPLICIT=re.compile(r'(?i)(home[ -]?office|homeoffice|work from home|work.from.home|von zuhause|von zu hause|100\s*%\s*homeoffice)')
REMOTE_EXPLICIT=re.compile(r'(?i)\b(remote|fully remote|work from anywhere|weltweit remote|100\s*%\s*remote)\b')
ONLY_OTHER=re.compile(r'(?i)\b(?:germany|deutschland|austria|österreich|switzerland|schweiz|poland|polen|france|frankreich|united kingdom|uk|united states|usa|canada|serbia|serbien|croatia|kroatien|bosnia|bosnien)\s*(?:only|exclusively|ausschließlich)\b')
FLEX_MK=re.compile(r'(?i)(?:remote|homeoffice|work from home|work remotely|work from anywhere).{0,65}(?:north macedonia|nordmazedonien|mazedonien|macedonia|skopje|ohrid)|(?:north macedonia|nordmazedonien|mazedonien|macedonia).{0,65}(?:remote|homeoffice|work from home)')
FIVE_LANG=re.compile(r'(?i)\b(?:german|deutsch|deutschsprachig|macedonian|mazedonisch|serbian|serbisch|croatian|kroatisch|bosnian|bosnisch)\b')
def personal_assess(j):
 j=assess(j)
 title=j['title'];loc=j['location'];desc=j['description'];head=desc[:3500]
 mk=bool(MK_LOCATION.search(loc))
 strong=bool(ROLE_STRONG.search(title))
 bad=bool(ROLE_BLOCK.search(title) or LANG_BLOCK.search(title))
 # A job written in English is not automatically an English-language requirement.
 language=bool(FIVE_LANG.search(title+' '+head[:2500]))
 # Use explicit job-location metadata. An office in Germany isn't proof of remote eligibility.
 explicit_remote=bool(REMOTE_EXPLICIT.search(title+' '+loc) or HOME_EXPLICIT.search(title+' '+loc))
 hybrid=bool(HYBRID.search(title+' '+loc))
 if hybrid:
  j['work_mode']='hybrid' if mk else 'hybrid_outside_mk'
 elif mk and not explicit_remote and j['work_mode']!='freelance':
  j['work_mode']='mk_local'
 elif mk and HOME_EXPLICIT.search(title+' '+loc):
  j['work_mode']='homeoffice'
 elif mk and REMOTE_EXPLICIT.search(title+' '+loc):
  j['work_mode']='remote'
 elif not mk and j['work_mode']=='mk_local':
  j['work_mode']='unknown'
 # If only the description says "remote", still display as potential, but no false MK confirmation.
 remote=j['work_mode'] in ('remote','homeoffice','freelance')
 location_block=bool(ONLY_OTHER.search(loc) or EXCLUDE.search(loc) or EUROPE_ONLY.search(loc))
 if location_block and not mk:
  j['ohrid']='ausgeschlossen'
  j['location_confirmed']=False
 elif mk:
  j['ohrid']='Arbeitsort Nordmazedonien'
  j['location_confirmed']=True
 elif FLEX_MK.search(title+' '+loc+' '+head[:1800]):
  j['ohrid']='Nordmazedonien ausdrücklich bei Remote genannt'
  j['location_confirmed']=True
 else:
  j['location_confirmed']=False
 # Require role relevance and a known language for the default list.
 # Local Macedonian positions without stated language remain in reserve, not rejected as impossible.
 j['excluded']=bool(bad or j['excluded'] or location_block or j['work_mode']=='hybrid_outside_mk')
 if j['excluded']:j['category']='excluded'
 elif strong and language and (remote or mk or j['work_mode']=='hybrid'):
  j['category']='recommended' if j['location_confirmed'] else 'review'
 else:j['category']='possible'
 j['relevant_role']=strong
 j['matching_language']=language
 j['location_evidence']='Bestätigt in Stellenangabe' if j['location_confirmed'] else ('Ausgeschlossen' if j['ohrid']=='ausgeschlossen' else 'Nicht bestätigt: vor Bewerbung prüfen')
 j['work_priority']={'homeoffice':6,'remote':5,'freelance':5,'hybrid':4,'mk_local':3}.get(j['work_mode'],0)
 j['fit']=max(0,min(99,j['fit']+(12 if strong else -20)+(8 if j['location_confirmed'] else 0)))
 return j

def personal_rank(j):
 mode=j.get('work_mode','unknown')
 good=not j['excluded'] and j.get('relevant_role') and j.get('matching_language')
 eligible=j.get('location_confirmed',False)
 worldwide=bool(WORLD.search(j.get('location','')))
 mk=j.get('mk_local',False)
 # Homeoffice -> remote/freelance -> hybrid in MK -> onsite MK
 # Confirmed country permission beats unknown remote; unknown remote remains visible after confirmed.
 tier=(5 if good and eligible and mode=='homeoffice' else
       4 if good and eligible and mode in ('remote','freelance') else
       3.5 if good and worldwide and mode in ('homeoffice','remote','freelance') else
       3 if good and eligible and mode=='hybrid' else
       2 if good and eligible and mode=='mk_local' else
       1 if good and mode in ('homeoffice','remote','freelance') else 0)
 return (tier,j['language_tier']>=2,j['language_tier'],j.get('balkan_language',False),j['fit'],str(j['date']))

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
  seen.add(key);unique.append(personal_assess(j))
 unique.sort(key=personal_rank,reverse=True)
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
   if show=='recommended':jobs=[j for j in jobs if not j['excluded'] and j.get('relevant_role') and j.get('matching_language') and personal_rank(j)[0]>0]
   elif show=='confirmed':jobs=[j for j in jobs if j['category']=='recommended' and j['work_mode'] in ('remote','homeoffice','freelance','mk_local')]
   elif show=='review':jobs=[j for j in jobs if j['category']=='review' and j['work_mode'] in ('remote','homeoffice','freelance','mk_local')]
   elif show=='possible':jobs=[j for j in jobs if j['category']=='possible' and j['work_mode'] in ('remote','homeoffice','freelance','mk_local')]
   elif show=='excluded':jobs=[j for j in jobs if j['category']=='excluded']
   industries=set(q.get('industry',[]))
   if industries:jobs=[j for j in jobs if industries.intersection(j.get('industries',[]))]
   modes=set(q.get('mode',[]))
   if modes:jobs=[j for j in jobs if j.get('work_mode') in modes]
   langs=set(q.get('language',[]))
   if langs:jobs=[j for j in jobs if str(j['language_tier']) in langs or (j['balkan_language'] and 'balkan' in langs)]
   if q.get('balkan',['0'])[0]=='1':jobs=[j for j in jobs if j['balkan_language']]
   if q.get('salary',['0'])[0]=='1':jobs=[j for j in jobs if j.get('salary','').strip()]
   if q.get('english',['any'])[0]=='not_required':jobs=[j for j in jobs if j['english']!='Englischpflicht erkannt']
   location=q.get('location',['any'])[0]
   if location=='confirmed':jobs=[j for j in jobs if j.get('location_confirmed') and j['ohrid']!='ausgeschlossen']
   elif location=='not_excluded':jobs=[j for j in jobs if j['ohrid']!='ausgeschlossen']
   jobs.sort(key=personal_rank,reverse=True)
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
