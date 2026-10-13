# EURES Ireland Job Scraper

Scrapes job postings located in Ireland from the [EURES job mobility portal](https://europa.eu/eures/portal/jv-se/search?locationCodes=ie&lang=en) once a day, using GitHub Actions. Results are saved as weekly CSV files committed back to this repository.

## What it produces

Two CSV files per week in the `data/` folder:

| File | Contents |
|------|----------|
| `headlines_<YYYY-MM-DD>.csv` | One row per job from the search results: title, employer, location, dates, schedule, short description, link |
| `details_<YYYY-MM-DD>.csv` | One row per job from its detail record: employer, number of posts, contact name/email/phone/website, application instructions, dates, deadline, contract type, hours, salary, experience, education, languages, full description, and the raw JSON |

Both tables share a `job_id` column, so they can be joined on it.

`<YYYY-MM-DD>` is the **Sunday that started the week** (UTC). For example, files for the week beginning Sunday 18 October 2026 are named `headlines_2026-10-18.csv` and `details_2026-10-18.csv`.

## How it works

- A GitHub Actions workflow (`.github/workflows/scrape.yml`) runs daily at **03:17 UTC**.
- `scrape.py` queries the EURES search API for Ireland with a "last 24 hours" filter, pages through all results, then fetches the detail record for each job.
- Job IDs already present in any earlier file are skipped, so overlapping runs never create duplicates.
- New rows are appended to the current week's files. The first run after Sunday 00:01 UTC creates a fresh pair of files, and the previous week's files are left untouched.
- The workflow commits any changes in `data/` back to the repo.

## Setup

1. Create a GitHub repository and add these files, keeping this structure:
   ```
   scrape.py
   README.md
   .github/workflows/scrape.yml
   ```
2. Go to **Settings â†’ Actions â†’ General â†’ Workflow permissions** and select **Read and write permissions**.
3. Go to the **Actions** tab, choose **EURES Ireland daily scrape**, and click **Run workflow** to test it.
4. After that it runs automatically every day.

## Collecting the data

Each week, download the finished week's two files from the `data/` folder in the repo (open the file, click the download icon), or clone/pull the repository.

## Running locally

```bash
pip install requests
python scrape.py
```

Output goes to `./data/`.

## Configuration

Edit the constants at the top of `scrape.py`:

| Setting | Purpose |
|---------|---------|
| `PAGE_SIZE` | Results per search request (default 50) |
| `DELAY` | Seconds to wait between requests (default 1.0) |
| `DETAIL_URLS` | Candidate detail-record endpoints; the first that responds is used |

To change the run time, edit the `cron` line in `scrape.yml` (times are UTC). To scrape a different country, change `locationCodes` in `post_search()`.

## Troubleshooting

- **Search request fails or returns nothing:** the portal's internal API may have changed. Open the search page in a browser, press F12, go to **Network â†’ Fetch/XHR**, and look at the search and job-detail requests. Update `SEARCH_URL`, `DETAIL_URLS`, and the request body in `scrape.py` to match.
- **Detail columns are empty:** the field names in `detail_row()` are best guesses. The `raw_json` column holds the complete record; check it to find the right field names and update the mapping.
- **"No detail for <id>" warnings:** the headline row is still saved, but the detail record could not be retrieved.
- **Scheduled runs are late:** GitHub can delay scheduled workflows by up to an hour at busy times.
- **Schedule stopped:** GitHub disables scheduled workflows after 60 days without repository activity. The daily data commits normally prevent this; if it happens, re-enable the workflow in the Actions tab.

## Notes

- Check the EURES portal's terms of use before relying on automated access. The scraper waits between requests to keep the load light.
- Dates and times are UTC throughout.
