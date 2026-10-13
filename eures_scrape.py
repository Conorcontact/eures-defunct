"""EURES Ireland job scraper.

Writes two weekly CSVs (week starts Sunday, UTC), joinable on job_id:
  data/headlines_<YYYY-MM-DD>.csv   one row per job from the search results
  data/details_<YYYY-MM-DD>.csv     one row per job from the job's detail record
"""
import csv, glob, json, os, sys, time
import datetime as dt
import requests

BASE = "https://europa.eu/eures/api/jv-searchengine/public/jv-search"
SEARCH_URL = f"{BASE}/search"
# Detail endpoint candidates - the first that returns 200 is used.
DETAIL_URLS = [
    "https://europa.eu/eures/api/jv-searchengine/public/jv/id/{id}?lang=en",
    BASE + "/jv/id/{id}?lang=en",
    BASE + "/jv/{id}?lang=en",
]
PORTAL_JOB_URL = "https://europa.eu/eures/portal/jv-se/jv-details/{id}?lang=en"
PAGE_SIZE = 50
DELAY = 1.0  # seconds between requests, be polite
DATA_DIR = "data"
HEADERS = {"Content-Type": "application/json", "Accept": "application/json",
           "User-Agent": "Mozilla/5.0 (personal job-feed scraper)"}

HEADLINE_COLS = ["job_id", "scraped_at", "title", "employer", "location",
                 "country_codes", "creation_date", "last_modified", "schedule",
                 "short_description", "url"]
DETAIL_COLS = ["job_id", "scraped_at", "title", "employer_name", "number_of_posts",
               "contact_name", "contact_email", "contact_phone", "contact_website",
               "application_instructions", "creation_date", "last_modified",
               "application_deadline", "start_date", "end_date", "location",
               "contract_type", "hours", "salary", "experience", "education",
               "languages", "description", "raw_json"]


def week_start(today=None):
    today = today or dt.datetime.utcnow().date()
    return today - dt.timedelta(days=(today.weekday() + 1) % 7)  # last Sunday


def dig(d, *paths, default=""):
    """Return first non-empty value found along any dotted path."""
    for p in paths:
        cur = d
        for k in p.split("."):
            if isinstance(cur, list):
                cur = cur[0] if cur else None
            if isinstance(cur, dict):
                cur = cur.get(k)
            else:
                cur = None
                break
        if cur not in (None, "", [], {}):
            return cur
    return default


def flat(v):
    if isinstance(v, (list, dict)):
        return json.dumps(v, ensure_ascii=False)
    return v


def post_search(page):
    body = {
        "resultsPerPage": PAGE_SIZE, "page": page, "sortSearch": "MOST_RECENT",
        "keywords": [], "publicationPeriod": "LAST_DAY", "occupationUris": [],
        "skillUris": [], "requiredExperienceCodes": [], "positionScheduleCodes": [],
        "sectorCodes": [], "educationLevelCodes": [], "positionOfferingCodes": [],
        "locationCodes": ["ie"], "euresFlagCodes": [], "otherBenefitsCodes": [],
        "requiredLanguages": [], "minNumberPost": None, "sessionId": "gh-actions",
    }
    for attempt in range(3):
        r = requests.post(SEARCH_URL, json=body, headers=HEADERS, timeout=60)
        if r.status_code == 200:
            return r.json()
        time.sleep(5 * (attempt + 1))
    r.raise_for_status()


def get_detail(job_id):
    for url in DETAIL_URLS:
        try:
            r = requests.get(url.format(id=job_id), headers=HEADERS, timeout=60)
            if r.status_code == 200:
                return r.json()
        except requests.RequestException:
            pass
    return None


def known_ids():
    ids = set()
    for f in glob.glob(f"{DATA_DIR}/headlines_*.csv"):
        with open(f, newline="", encoding="utf-8-sig") as fh:
            ids.update(row["job_id"] for row in csv.DictReader(fh))
    return ids


def append_rows(path, cols, rows):
    new = not os.path.exists(path)
    with open(path, "a", newline="", encoding="utf-8-sig") as fh:
        w = csv.DictWriter(fh, fieldnames=cols, extrasaction="ignore")
        if new:
            w.writeheader()
        w.writerows(rows)


def headline_row(j, now):
    jid = j.get("id")
    return {
        "job_id": jid, "scraped_at": now,
        "title": dig(j, "title"),
        "employer": dig(j, "employer.name"),
        "location": flat(dig(j, "locationMap")),
        "country_codes": flat(dig(j, "locationMap")),
        "creation_date": dig(j, "creationDate"),
        "last_modified": dig(j, "lastModificationDate"),
        "schedule": flat(dig(j, "positionScheduleCodes")),
        "short_description": dig(j, "description"),
        "url": PORTAL_JOB_URL.format(id=jid),
    }


def detail_row(jid, d, now):
    # Field names are best guesses; raw_json keeps everything so nothing is lost.
    jv = d.get("jvProfiles", [d])
    prof = jv[0] if isinstance(jv, list) and jv else d
    return {
        "job_id": jid, "scraped_at": now,
        "title": dig(prof, "title", "jobTitle") or dig(d, "title"),
        "employer_name": dig(prof, "employer.name", "employer.companyName") or dig(d, "employer.name"),
        "number_of_posts": dig(prof, "positionOffering.numberOfPosts", "numberOfPosts", "numberPosts") or dig(d, "numberOfPosts"),
        "contact_name": dig(prof, "applicationInstructions.contact.name", "contact.name"),
        "contact_email": dig(prof, "applicationInstructions.contact.email", "contact.email", "applicationInstructions.email"),
        "contact_phone": dig(prof, "applicationInstructions.contact.phone", "contact.phone"),
        "contact_website": dig(prof, "applicationInstructions.contact.website", "applicationInstructions.url", "contact.website"),
        "application_instructions": flat(dig(prof, "applicationInstructions.instructions", "applicationInstructions")),
        "creation_date": dig(d, "creationDate") or dig(prof, "creationDate"),
        "last_modified": dig(d, "lastModificationDate") or dig(prof, "lastModificationDate"),
        "application_deadline": dig(prof, "applicationEndDate", "applicationDeadline"),
        "start_date": dig(prof, "positionPeriod.startDate", "startDate"),
        "end_date": dig(prof, "positionPeriod.endDate", "endDate"),
        "location": flat(dig(prof, "locations", "location")),
        "contract_type": flat(dig(prof, "positionOfferingCodes", "positionOffering")),
        "hours": flat(dig(prof, "positionScheduleCodes", "positionSchedule")),
        "salary": flat(dig(prof, "salary", "remuneration")),
        "experience": flat(dig(prof, "requiredExperienceCodes", "requiredExperience")),
        "education": flat(dig(prof, "educationLevelCodes", "educationLevel")),
        "languages": flat(dig(prof, "requiredLanguages", "languages")),
        "description": dig(prof, "description", "jobDescription") or dig(d, "description"),
        "raw_json": json.dumps(d, ensure_ascii=False),
    }


def main():
    os.makedirs(DATA_DIR, exist_ok=True)
    stamp = week_start().isoformat()
    head_path = f"{DATA_DIR}/headlines_{stamp}.csv"
    det_path = f"{DATA_DIR}/details_{stamp}.csv"
    seen = known_ids()
    now = dt.datetime.utcnow().isoformat(timespec="seconds") + "Z"

    page, total_pages, new_count = 1, 1, 0
    while page <= total_pages:
        data = post_search(page)
        total_pages = data.get("numberPages") or 1
        jobs = data.get("jvs", [])
        if page == 1:
            print(f"API reports {data.get('numberRecords')} postings in last day")
        heads, dets = [], []
        for j in jobs:
            jid = j.get("id")
            if not jid or jid in seen:
                continue
            seen.add(jid)
            heads.append(headline_row(j, now))
            time.sleep(DELAY)
            d = get_detail(jid)
            if d is None:
                print(f"WARNING: no detail for {jid}", file=sys.stderr)
                continue
            dets.append(detail_row(jid, d, now))
        append_rows(head_path, HEADLINE_COLS, heads)
        append_rows(det_path, DETAIL_COLS, dets)
        new_count += len(heads)
        page += 1
        time.sleep(DELAY)
    print(f"Added {new_count} new postings to week file {stamp}")


if __name__ == "__main__":
    main()
