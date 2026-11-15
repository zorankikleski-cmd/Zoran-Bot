"""Public sources with Nordmazedonien coverage."""
import json
import re
import time
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo
from html import unescape
from urllib.parse import urlencode

from matching import BAD_ROLE, LANGUAGES, ROLES, language_title

MK_BOARD = 'https://www.vrabotuvanje.com.mk'
PAYLOAD = re.compile(r'<script[^>]*id="__NUXT_DATA__"[^>]*>(.*?)</script>', re.S)


def local_board(read, row, timestamp):
    # The public site uses a flat Nuxt payload. Follow only its published job links.
    last_request = 0

    def load(url):
        nonlocal last_request
        time.sleep(max(0, 1 - (time.monotonic() - last_request)))
        last_request = time.monotonic()
        page = read(url, 'text/html').decode()
        match = PAYLOAD.search(page)
        if not match:
            raise ValueError('Stellendaten auf der Portalseite fehlen')
        return page, json.loads(match[1])

    def field(data, item, name, default=None):
        index = item.get(name, -1)
        return data[index] if isinstance(index, int) and 0 <= index < len(data) else default

    candidates = {}
    errors = []
    filters = ({'query': 'Deutsch'}, {'query': 'German'}, {'query': 'германски'}, {'locations': 'Охрид'}, {'positions': 'Administrative professions'},
               {'positions': 'Tourism and hospitality'}, {'positions': 'Management'})
    for path in ['/'] + ['/en/job-search?' + urlencode(f | {'sortBy': 'adtype'}) for f in filters]:
        try:
            page, data = load(MK_BOARD + path)
        except (OSError, ValueError) as error:
            errors.append(str(error))
            continue
        links = dict(re.findall(r'href="(/(?:en/job|rabota)/([\da-f-]{36})/[a-z0-9-]+)', page))
        urls = {ident: path for path, ident in links.items()}
        for item in data:
            if not isinstance(item, dict) or not {'title', 'id', 'endsAt'} <= item.keys():
                continue
            ident = field(data, item, 'id')
            title = field(data, item, 'title', '')
            if ident not in urls or BAD_ROLE.search(title):
                continue
            if not any(re.search(pattern, title, re.I) for pattern in ROLES.values()):
                continue
            if timestamp(field(data, item, 'endsAt')) > time.time():
                candidates.setdefault(ident, (title, urls[ident]))
    if len(errors) == len(filters) + 1:
        raise ValueError(errors[0])

    results = []
    ordered = sorted(candidates.items(), key=lambda pair: any(language_title(p, pair[1][0]) for p in LANGUAGES.values()), reverse=True)
    for ident, (_, path) in ordered[:45]:
        url = MK_BOARD + path
        try:
            _, data = load(url)
            item = next((x for x in data if isinstance(x, dict) and 'endsAt' in x and
                         field(data, x, 'id') == ident), None)
            if not item:
                raise ValueError('Anzeigendetails fehlen')
            expires = timestamp(field(data, item, 'applicationsEnabledUntil') or field(data, item, 'endsAt'))
            if not expires or expires <= time.time():
                continue
            location = field(data, item, 'location', {})
            org = field(data, item, 'organization', {})
            work = field(data, item, 'workTypes', [])
            work = [data[index] for index in work] if isinstance(work, list) else []
            location = field(data, location, 'summary', '') if isinstance(location, dict) else location
            company = field(data, org, 'name', '') if isinstance(org, dict) else ''
            description = field(data, item, 'html') or field(data, item, 'requirements') or ''
            job = row('Vrabotuvanje MK', field(data, item, 'title'), company, description, location,
                      url, '', field(data, item, 'publishedAt'), ident)
            if job:
                job.update(mk_board=True, expires_at=expires, details_checked=True,
                           mode_hint='hybrid' if 'hybrid' in work else 'remote' if 'remote' in work else 'unknown')
                results.append(job)
        except (OSError, ValueError, IndexError, TypeError) as error:
            errors.append(str(error))
    if candidates and not results and errors:
        raise ValueError(errors[0])
    return results, errors


def support_board(get, row):
    data = get('https://apply.workable.com/api/v1/widget/accounts/supportyourapp')
    jobs = []
    if not isinstance(data.get('jobs'), list):
        raise ValueError('Workable liefert keine Stellenliste')
    for item in data['jobs']:
        mode = 'remote' if item.get('telecommuting') else 'unknown'
        loc = ', '.join(x for x in (item.get('city'), item.get('country')) if x)
        job = row('Workable · SupportYourApp', item.get('title'), 'SupportYourApp', '', loc,
                  item.get('url'), '', item.get('published_on'), item.get('shortcode'))
        if job:
            job.update(mode_hint=mode, employment=item.get('employment_type') or '')
            jobs.append(job)
    return jobs


def kariera_board(read, row):
    base = 'https://direct.kariera.mk'
    last_request = 0

    def load(path):
        nonlocal last_request
        time.sleep(max(0, 1 - (time.monotonic() - last_request)))
        last_request = time.monotonic()
        return read(base + path, 'text/html').decode()

    filters = ({'s': 'германски'}, {'city': '71'}, {'city': '44'}, {'occupation': '15'}, {'occupation': '40'})
    links = {}
    errors = []
    for search in filters:
        try:
            page = load('/search?' + urlencode({'city': '-1', 'occupation': '-1', 's': ''} | search))
            if 'v2-search' not in page:
                raise ValueError('Suchseite liefert keine lesbare Stellenliste')
            for path, title in re.findall(r"""class=['"]v2-search-job-link['"] href=['"](/job/[\w-]+/[\w-]+)['"]>(.*?)</a>""", page, re.S):
                title = unescape(title)
                if not BAD_ROLE.search(title) and any(re.search(pattern, title, re.I) for pattern in ROLES.values()):
                    links[path] = title
        except (OSError, ValueError) as error:
            errors.append(str(error))
    if len(errors) == len(filters):
        raise ValueError(errors[0])

    jobs = []
    zone = ZoneInfo('Europe/Skopje')
    for path in list(links)[:24]:
        try:
            page = load(path)
            title = re.search(r'<h1\b[^>]*>(.*?)</h1>', page, re.S)
            company = re.search(r"""class=['"]v2-job-company-name['"][^>]*>(.*?)</a>""", page, re.S)
            description = re.search(r"""class=['"]v2-job-body['"][^>]*>(.*?)</section>""", page, re.S)
            deadline = re.search(r'<small>Активен до</small>\s*<span>(\d{2}\.\d{2}\.\d{4})</span>', page)
            location = re.search(r'<small>Локација</small>\s*<span>(.*?)</span>', page, re.S)
            if not all((title, company, description, deadline, location)):
                raise ValueError('Pflichtangaben in der Anzeige fehlen')
            expires = (datetime.strptime(deadline[1], '%d.%m.%Y').replace(tzinfo=zone) + timedelta(days=1)).timestamp()
            if expires <= time.time():
                continue
            loc = location[1]
            if 'Работа од дома' in loc:
                loc = 'Работа од дома, Nordmazedonien'
            job = row('KARIERA.mk', title[1], company[1], description[1], loc, base + path, raw_id=path.split('/')[2])
            if job:
                job.update(expires_at=expires, details_checked=True, mk_board=True)
                jobs.append(job)
        except (OSError, ValueError) as error:
            errors.append(str(error))
    return jobs, errors
