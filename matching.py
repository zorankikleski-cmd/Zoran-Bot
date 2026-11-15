"""Evidence-based matching for the owner's job profile."""
import re
import time

LANGUAGES = {
    'de': r'german|deutsch(?:sprachig|kenntnisse)?|германски(?: јазик)?',
    'mk': r'macedonian|mazedonisch|македонски',
    'sr': r'serbian|serbisch|српски|srpski',
    'hr': r'croatian|kroatisch|хрватски|hrvatski',
    'bs': r'bosnian|bosnisch|босански|bosanski',
}
LANGUAGE_NAMES = dict(zip(LANGUAGES, ('Deutsch', 'Mazedonisch', 'Serbisch', 'Kroatisch', 'Bosnisch')))
ROLES = {
    'recruiting': r'recruit\w*|talent acquisition|talent sourc\w*|\bhr\b|human resources|people operations|personal(?:wesen|betreuung|referent\w*|administration|management)|човечки ресурси',
    'customer': r'customer (?:support|service|care|success)|client (?:support|service|success)|kunden(?:service|betreuung|support|berater\w*)|call.?cent(?:er|re)|contact cent(?:er|re)|(?:technical|it) support (?:specialist|consultant|agent)|support (?:agent|specialist|consultant)|help.?desk|service.?desk|корисничка поддршка|поддршка на корисници',
    'telecom': r'telecom\w*|telekom\w*|glasfaser|fi[bh]re rollout|mobilfunk|телекомуникац\w*',
    'travel': r'travel (?:agent|advisor|consultant|coordinator)|touris\w*|reise(?:berater\w*|büro|verkehr\w*)|reservations? (?:agent|coordinator)|rezeption\w*|front desk|туриз\w*|туристич\w*|рецепционер\w*|резервац\w*|агент за резервации',
    'operations': r'project (?:manager|coordinator|assistant)|projekt(?:leit\w*|koordin\w*|manag\w*)|operations (?:manager|coordinator|assistant|specialist|lead)|team[ -]?(?:lead\w*|leit\w*)|office (?:manager|assistant|administrator)|administrati(?:ve|on) (?:assistant|officer|coordinator)|back[ -]?office|sachbearbeit\w*|bürokauf\w*|quality (?:manager|supervisor)|procurement (?:coordinator|supervisor|assistant)|account manager|финансиски администратор|административ\w+\s+(?:службен\w+|асистент\w+|работник\w+)|teamassisten\w*|büroassisten\w*|секретар\w*|деловен асистент|проект\w* координатор|раководител на тим|раководител на терен',
    'ecommerce': r'e.?commerce (?:manager|specialist|assistant|coordinator|category manager)|marketplace (?:manager|specialist|coordinator)',
    'language': r'translator|interpreter|dolmetsch\w*|übersetz\w*|sprachmittl\w*|преведувач\w*',
}
BAD_ROLE = re.compile(r'\b(?:engineer\w*|ingenieur\w*|developer\w*|entwickler\w*|architect\w*|designer\w*|physician|nurse|psycholog\w*|sales (?:executive|representative|manager|development)|account executive|business development|kaltakquise|cold calling|продажба|продажен|инженер\w*)\b', re.I)
MK = r'north macedonia|nordmazedonien|macedonia|mazedonien|северна македонија|македонија|skopje|ohrid|bitola|tetovo|prilep|kumanovo|struga|gostivar|shtip|скопје|охрид|битола|тетово|прилеп|куманово|струга|гостивар|штип|велес|кочани|карпош|кичево|струмица|гевгелија|дебар|радовиш'
FOREIGN = r'germany|deutschland|austria|österreich|switzerland|schweiz|dach|uk|united kingdom|united states|usa|canada|australia|serbia|croatia|bosnia|albania|france|poland|spain|italy|netherlands|india|philippines|romania|bulgaria|greece|portugal|latam|apac|north america|mexico|ireland|japan|singapore|berlin|munich|münchen|hamburg|london|paris|vienna|wien|new york|california'
WORLD = r'worldwide|anywhere in the world|world[- ]?wide|weltweit|global(?:ly)? remote|work from anywhere(?!\s+in\b)'
EU = r'eu(?:\s*/\s*eea)?|eea|european union|europäische union|ewr'
MODES = {'homeoffice': 'Homeoffice', 'remote': 'Remote', 'freelance': 'Freelance',
         'hybrid': 'Hybrid', 'mk_local': 'Vor Ort', 'onsite': 'Vor Ort', 'unknown': 'Ungeklärt'}
HOME = r'home[ -]?office|work[ -]from[ -]home|von zu ?hause|работа од дома'
HYBRID = r'hybrid\w*|teilweise homeoffice|хибрид\w*'
REMOTE = r'remote|ortsunabhängig|работа од далечина|дистанцион\w*'
CONTRACT = r'freelanc\w*|freiberuf\w*|independent contractor|auf honorarbasis|selbstständig'

def find(pattern, value):
    return re.search(r'(?<!\w)(?:' + pattern + r')(?!\w)', value, re.I)

def language_requirement(pattern, text, level):
    # Keep evidence inside one sentence or list item.
    skill = level + r'|native|fluent|fluency|proficien\w*|excellent|strong|advanced|verhandlungssicher|fließend|muttersprache|течно|одлично'
    return find(r'(?:' + skill + r')\s*(?:knowledge of |skills in |command of |in |written and spoken )?(?:the )?(?:' + pattern + r')'
                r'|(?:' + pattern + r')\s*(?:language\s*)?(?:\(\s*)?(?:' + skill + r'|required|mandatory|essential|erforderlich|voraussetzung|задолжително)'
                r'|(?:required|mandatory|knowledge of|kenntnisse in|познавање на)\s+(?:говорен и пишан |пишан и говорен |the )?(?:' + pattern + r')', text)

def language_title(pattern, title):
    return find(r'(?:' + pattern + r')(?:[ -]speaking| speaker|[ -]language|sprachig)|[\[(]\s*(?:' + pattern + r')(?=\s*(?:[ABC][12]|[\]),/]))|^(?:' + pattern + r')(?=\s+(?!company|market|team|office|unternehmen|marketplace))|(?:[-–:/]\s*|\bwith\s+|\bmit\s+)(?:' + pattern + r')$', title)

def assess(job):
    title, desc, loc = (job[k] for k in ('title', 'description', 'location'))
    industries = [key for key, pattern in ROLES.items() if re.search(pattern, title, re.I)]
    languages = {}
    evidence = []
    for code, pattern in LANGUAGES.items():
        hit = language_title(pattern, title) or language_requirement(pattern, title + '\n' + desc, r'[ABC][12]')
        if hit:
            languages[code] = 'required'
            evidence.append(LANGUAGE_NAMES[code] + ' · „' + hit[0] + '“')
        elif (hit := find(r'(?:' + pattern + r')[^.!?;]{0,24}(?:preferred|advantage|nice to have|von vorteil|wünschenswert|предност)', desc)):
            languages[code] = 'preferred'
            evidence.append(LANGUAGE_NAMES[code] + ' erwünscht · „' + hit[0] + '“')
    if not languages and job.get('mk_board') and re.search(r'[А-Яа-яЃѓЌќЅѕЈјЉљЊњЏџ]{3}', title) and len(re.findall(r'[А-Яа-яЃѓЌќЅѕЈјЉљЊњЏџ]{3,}', desc)) >= 12:
        languages['mk'] = 'listing'
        evidence.append('Anzeige auf Mazedonisch')
    english = r'english|englisch|англиски'
    english_hit = (language_requirement(english, title + '\n' + desc, r'[BC][12]|intermediate')
                   or find(r'(?:written and spoken|spoken and written|business|professional|good|gute|добро|активно)\s+(?:command of |knowledge of |kenntnisse in |познавање на )?(?:the )?(?:' + english + r')'
                           r'|(?:excellent|strong|good)[^.!?;]{0,40}(?:skills|proficiency)[^.!?;]{0,25}(?:' + english + r')', desc)
                   or language_title(english, title))
    if english_hit and find(r'preferred|advantage|nice to have|von vorteil|предност', english_hit.string[english_hit.end():english_hit.end()+45].split('\n')[0]):
        english_hit = None
    foreign_language = r'french|français|französisch|japanese|spanish|spanisch|italian|italienisch|dutch|niederländisch|polish|polnisch|portuguese|danish|swedish|arabic|mandarin|turkish|bulgarian|bulgarisch|бугарски|албански|француски|шпански|италијански'
    other_hit = language_title(foreign_language, title) or language_requirement(foreign_language, title + '\n' + desc, r'[ABC][12]')
    basic = find(r'(?:basic|grundkenntnisse in|основно познавање на)\s*(?:' + english + r')|(?:' + english + r')\s*(?:A[12]|basic|grundkenntnisse)', desc)

    model_text = title + ' · ' + loc
    mode = job.get('mode_hint', 'unknown')
    if find(HYBRID, model_text) or find(r'hybrid work|хибридно|teilweise homeoffice', desc):
        mode = 'hybrid'
    elif find(r'no remote|kein homeoffice|on[ -]?site only', model_text + ' ' + desc):
        mode = 'onsite'
    elif find(HOME, model_text) or find(HOME, desc):
        mode = 'homeoffice'
    elif find(REMOTE, model_text) or find(r'fully remote|100\s*%\s*remote|remote position|remote work|this role is remote', desc):
        mode = 'remote'
    freelance = bool(find(CONTRACT, model_text + ' ' + job.get('employment', '')) or find(r'independent contractor|freelance (?:contract|position|role)|auf honorarbasis', desc))
    if freelance and mode in ('homeoffice', 'remote'):
        mode = 'freelance'

    mk_location = find(MK, loc)
    explicit = find(r'(?:work(?:ing)? (?:remotely )?from|applications? from|candidates? (?:based|located|residing) in|remote (?:in|from)|bewerbungen aus)\s+(?:anywhere in |anywhere within )?(?:' + MK + r')', desc)
    restrict = find(r'(?:only|exclusively|ausschließlich)\s*(?:in |from |within )?(?:the )?(?:' + EU + '|' + FOREIGN + r')|(?:' + EU + '|' + FOREIGN + r')\s*(?:only|residents only)|(?:must (?:live|reside|be based|be located) in|required to (?:reside|be based) in)\s*(?:the )?(?:' + EU + '|' + FOREIGN + r')', desc)
    hybrid_offsite = mode == 'hybrid' and not mk_location
    loc_foreign = find(FOREIGN + '|' + EU + r'|baden|schweizerisch|дубаи', loc)
    title_scope = find(r'\((?:' + FOREIGN + r')\)|remote (?:in|from) (?:' + FOREIGN + r')', title)
    world = find(WORLD, loc) or find(r'(?:remote|hiring|work|candidates?)\s+(?:from )?(?:' + WORLD + r')', desc)
    flexible = mode in ('remote', 'homeoffice', 'freelance')
    if restrict or hybrid_offsite or title_scope or (loc_foreign and not mk_location):
        geo = 'excluded'
        geo_evidence = 'Ortsvorgabe · ' + ((restrict or title_scope)[0] if restrict or title_scope else loc or 'Hybrid ohne Arbeitsort in Nordmazedonien')
    elif mk_location or (explicit and flexible):
        geo = 'confirmed'
        geo_evidence = 'Nordmazedonien laut Anzeige · ' + (loc if mk_location else explicit[0])
    elif world and flexible:
        geo = 'worldwide'
        geo_evidence = 'Weltweit ausgeschrieben · Vertrag für Nordmazedonien offen'
    else:
        geo = 'unknown'
        geo_evidence = 'Beschäftigung aus Nordmazedonien offen' + (' · ' + loc if loc else '')
    if mk_location and mode in ('unknown', 'onsite'):
        mode = 'mk_local'

    blocked = []
    if BAD_ROLE.search(title) or find(r'дипломиран правник|лиценца за работа како|bar admission required', desc):
        blocked.append('Tätigkeit außerhalb des Profils')
    if english_hit and basic and not find(r'(?:' + english + r')\s*(?:[BC][12]|fluent|advanced)', title + '\n' + desc):
        if find(r'познавање на англиски|knowledge of english', english_hit[0]):
            english_hit = None
    if english_hit:
        blocked.append('Englisch über Grundniveau · „' + english_hit[0] + '“')
    if other_hit:
        blocked.append('Weitere Sprache verlangt · „' + other_hit[0] + '“')
    if geo == 'excluded':
        blocked.append(geo_evidence)
    if find(r'cold calling required|kaltakquise|commission.only|outbound sales|излезни повици|телефонска продажба', title + ' ' + desc):
        blocked.append('Aktive Akquise oder reine Provision')
    scam = bool(find(r'(?:pay|transfer|deposit)\s+(?:an? |the )?(?:application|registration|training|equipment) fee|bewerbungsgebühr', desc))
    if scam:
        blocked.append('Mögliche Vorauszahlung')
    if find(r'државјанин на република северна македонија|north macedonian citizenship required', desc):
        blocked.append('Nordmazedonische Staatsbürgerschaft verlangt')
    if job.get('expires_at', 0) and job['expires_at'] <= time.time():
        blocked.append('Bewerbungsfrist abgelaufen')
    strength = max(({'required': 3, 'listing': 2, 'preferred': 1}[item] for item in languages.values()), default=0)
    suitable = bool(industries and strength)
    category = ('excluded' if blocked else 'recommended' if suitable and geo == 'confirmed' else
                'review' if suitable and flexible else 'possible')
    priority = {'homeoffice': 5, 'remote': 4, 'freelance': 3, 'hybrid': 2, 'mk_local': 1}.get(mode, 0)
    role_points = 35 if industries else 0
    lang_points = {3: 35, 2: 28, 1: 18, 0: 0}[strength]
    geo_points = {'confirmed': 20, 'worldwide': 8}.get(geo, 0)
    points = dict(Tätigkeit=role_points, Sprache=lang_points, Arbeitsort=geo_points, Arbeitsmodell=priority * 2)
    notes = blocked + ([] if industries else ['Tätigkeit aus dem Titel nicht eindeutig zugeordnet'])
    if 'customer' in industries and find(r'call.?cent(?:er|re)', title) and not find(r'customer support|kundenservice|корисничка поддршка|inbound|влезни повици', title + ' ' + desc):
        notes.append('Callcenter · Aufgaben und mögliche Akquise in der Anzeige klären')
    statuses = {'recommended': 'Passend laut Anzeige', 'review': 'Sprachlich und fachlich passend · Arbeitsort klären',
                'possible': 'Weitere Hinweise zur Passung fehlen', 'excluded': 'Außerhalb der Profilsuche'}
    return dict(job, fit=0 if blocked else sum(points.values()), score_parts=points, languages=languages,
                language_evidence=evidence, language=' · '.join(evidence) or 'Passende Sprache unbelegt',
                language_tier=3 if languages.get('de') == 'required' else 2 if 'de' in languages else 0,
                balkan_language=any(k != 'de' for k in languages), matching_language=bool(languages),
                english='Englischpflicht erkannt' if english_hit else 'Grundkenntnisse laut Anzeige' if basic else 'Englischpflicht nicht belegt',
                english_level='advanced' if english_hit else 'basic' if basic else 'unknown',
                excluded=bool(blocked), relevant_role=bool(industries), industries=industries,
                category=category, status=statuses[category], notes=notes, location_status=geo,
                location_evidence=geo_evidence, location_confirmed=geo == 'confirmed', mk_local=bool(mk_location),
                ohrid={'excluded': 'ausgeschlossen', 'confirmed': 'Arbeitsort Nordmazedonien',
                       'worldwide': 'Weltweit ausgeschrieben'}.get(geo, 'ungeklärt'),
                work_mode=mode, work_label=MODES[mode], work_priority=priority, language_strength=strength,
                scam='kritischer Warnhinweis' if scam else 'Keine unabhängige Arbeitgeberprüfung')

def rank(job):
    return (job['category'] == 'recommended', job['language_strength'], job['relevant_role'],
            job['location_status'] in ('confirmed', 'worldwide'), job['work_priority'],
            job.get('published_at', 0), job['url'])
