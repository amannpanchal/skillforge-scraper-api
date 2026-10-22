from __future__ import annotations

import asyncio
import ipaddress
import os
import socket
from datetime import datetime, timezone
from urllib.parse import urlparse

import httpx
from bs4 import BeautifulSoup
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field, HttpUrl

app = FastAPI(
    title="SkillForge Scraper API",
    description="A responsible, rate-limited page metadata extraction API.",
    version="1.0.0",
)

TIMEOUT_SECONDS = float(os.getenv("REQUEST_TIMEOUT_SECONDS", "10"))
MAX_RESPONSE_BYTES = int(os.getenv("MAX_RESPONSE_BYTES", "2000000"))
MIN_HOST_INTERVAL = float(os.getenv("MIN_SECONDS_BETWEEN_HOST_REQUESTS", "1.0"))

_host_last_request: dict[str, float] = {}
_host_locks: dict[str, asyncio.Lock] = {}


class ScrapeRequest(BaseModel):
    url: HttpUrl = Field(description="Public HTTP(S) page URL")


class ScrapeResponse(BaseModel):
    url: str
    status_code: int
    title: str | None
    description: str | None
    canonical_url: str | None
    headings: list[str]
    text: str
    fetched_at: datetime


def _validate_public_url(url: str) -> str:
    parsed = urlparse(url)
    if parsed.scheme not in {"http", "https"} or not parsed.hostname:
        raise HTTPException(status_code=400, detail="Only valid HTTP(S) URLs are allowed.")
    host = parsed.hostname.rstrip(".").lower()
    if host in {"localhost", "localhost.localdomain"}:
        raise HTTPException(status_code=400, detail="Local addresses are not allowed.")

    try:
        addresses = {ipaddress.ip_address(host)}
    except ValueError:
        try:
            records = socket.getaddrinfo(host, parsed.port or (443 if parsed.scheme == "https" else 80))
            addresses = {ipaddress.ip_address(record[4][0]) for record in records}
        except socket.gaierror:
            raise HTTPException(status_code=400, detail="The hostname could not be resolved.")
    if not addresses or any(
        not address.is_global for address in addresses
    ):
        raise HTTPException(status_code=400, detail="Private or non-public network targets are not allowed.")
    return host


async def _respect_host_interval(host: str) -> None:
    lock = _host_locks.setdefault(host, asyncio.Lock())
    async with lock:
        loop = asyncio.get_running_loop()
        now = loop.time()
        wait = MIN_HOST_INTERVAL - (now - _host_last_request.get(host, 0.0))
        if wait > 0:
            await asyncio.sleep(wait)
        _host_last_request[host] = loop.time()


def _extract_page(html: str, final_url: str, status_code: int) -> ScrapeResponse:
    soup = BeautifulSoup(html, "html.parser")
    for element in soup(["script", "style", "noscript", "svg"]):
        element.decompose()

    title = soup.title.get_text(" ", strip=True) if soup.title else None
    meta = soup.find("meta", attrs={"name": lambda value: value and value.lower() == "description"})
    description = meta.get("content", "").strip() or None if meta else None
    canonical_tag = soup.find("link", rel=lambda value: value and "canonical" in value)
    canonical = canonical_tag.get("href") if canonical_tag else None
    headings = [
        heading.get_text(" ", strip=True)
        for heading in soup.find_all(["h1", "h2", "h3"])
        if heading.get_text(" ", strip=True)
    ][:50]
    text = " ".join(soup.get_text(" ", strip=True).split())[:20000]

    return ScrapeResponse(
        url=final_url,
        status_code=status_code,
        title=title,
        description=description,
        canonical_url=canonical,
        headings=headings,
        text=text,
        fetched_at=datetime.now(timezone.utc),
    )


@app.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok"}


@app.post("/scrape", response_model=ScrapeResponse)
async def scrape_page(payload: ScrapeRequest) -> ScrapeResponse:
    url = str(payload.url)
    host = _validate_public_url(url)
    await _respect_host_interval(host)

    timeout = httpx.Timeout(TIMEOUT_SECONDS)
    headers = {"User-Agent": "SkillForgeScraperDemo/1.0 (+educational; respectful rate limits)"}

    last_error: Exception | None = None
    async with httpx.AsyncClient(
        timeout=timeout,
        follow_redirects=False,
        headers=headers,
    ) as client:
        for attempt in range(3):
            try:
                async with client.stream("GET", url) as response:
                    if response.is_redirect:
                        raise HTTPException(
                            status_code=400,
                            detail="Redirects are not followed. Submit the destination URL directly.",
                        )
                    if response.status_code >= 500 and attempt < 2:
                        await asyncio.sleep(0.25 * (2 ** attempt))
                        continue
                    if response.status_code >= 400:
                        raise HTTPException(
                            status_code=502,
                            detail=f"Target site returned HTTP {response.status_code}.",
                        )
                    content_type = response.headers.get("content-type", "").lower()
                    if "text/html" not in content_type and "application/xhtml+xml" not in content_type:
                        raise HTTPException(status_code=415, detail="The target did not return HTML.")
                    chunks: list[bytes] = []
                    size = 0
                    async for chunk in response.aiter_bytes():
                        size += len(chunk)
                        if size > MAX_RESPONSE_BYTES:
                            raise HTTPException(status_code=413, detail="Page exceeds the configured response-size limit.")
                        chunks.append(chunk)
                    encoding = response.encoding or "utf-8"
                    html = b"".join(chunks).decode(encoding, errors="replace")
                    return _extract_page(html, url, response.status_code)
            except HTTPException:
                raise
            except (httpx.TimeoutException, httpx.NetworkError) as exc:
                last_error = exc
                if attempt < 2:
                    await asyncio.sleep(0.25 * (2 ** attempt))

    raise HTTPException(status_code=502, detail=f"Could not fetch target page after retries: {type(last_error).__name__ if last_error else 'unknown error'}.")
