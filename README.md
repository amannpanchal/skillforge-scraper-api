# SkillForge Scraper API

A small, portfolio-ready web scraping API built with **Python + FastAPI**. It demonstrates safe, responsible fetching with timeouts, retries, per-host rate limiting, URL validation, and clear JSON responses.

> Educational starter project. Only fetch pages you are authorized to access. Respect site terms, robots.txt, and rate limits. This project does not bypass CAPTCHAs, logins, paywalls, or other access controls.

## Features

- `POST /scrape` fetches a public HTTP(S) page and extracts its title, description, headings, canonical URL, and readable text.
- `GET /health` health check.
- URL validation blocks localhost, private/reserved IP addresses, and non-HTTP schemes to reduce SSRF risk.
- Per-host minimum request interval.
- Retries for transient HTTP/network failures with exponential backoff.
- Request timeout, response-size cap, and structured errors.
- Unit tests for parsing and URL validation.
- Dockerfile and `.env.example`.

## Quick start (Windows CMD)

```bat
py -m venv .venv
.venv\Scripts\activate
python -m pip install -r requirements.txt
uvicorn app.main:app --reload
```

Open:
- API docs: http://127.0.0.1:8000/docs
- Health: http://127.0.0.1:8000/health

## Example request

```bash
curl -X POST "http://127.0.0.1:8000/scrape" ^
  -H "Content-Type: application/json" ^
  -d "{\"url\":\"https://example.com\"}"
```

Example response (fields may vary by page):

```json
{
  "url": "https://example.com",
  "status_code": 200,
  "title": "Example Domain",
  "description": null,
  "canonical_url": null,
  "headings": [],
  "text": "Example Domain ...",
  "fetched_at": "2026-01-01T12:00:00+00:00"
}
```

## Run tests

```bat
python -m pytest -q
```

## Docker

```bash
docker build -t skillforge-scraper-api .
docker run --rm -p 8000:8000 skillforge-scraper-api
```

## API contract

### `POST /scrape`

Request:

```json
{ "url": "https://example.com" }
```

Successful response includes the HTTP status, page title, meta description, canonical URL, H1–H3 headings, and cleaned text. Non-success upstream statuses are returned as a clear `502` error rather than silently pretending the fetch succeeded.

### `GET /health`

Returns `{"status":"ok"}`.

## Design notes

- This is a portfolio starter, not a production crawler. The in-memory rate limiter is per process and resets on restart.
- DNS rebinding protection is not comprehensive. For production use, enforce outbound network restrictions at the infrastructure layer and revalidate resolved IPs at connection time.
- Before scraping a domain, check its published rules and obtain permission where required.
