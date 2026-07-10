import hashlib
import re
from datetime import datetime, timezone
from urllib.parse import urlparse

import httpx
from bs4 import BeautifulSoup

from .base import BaseCollector


class WebScraper(BaseCollector):
    def name(self):
        return "Web Scraper"

    def collect(self) -> list[dict]:
        items = []
        sources = self.config.get("sources", {}).get("web", [])
        keywords = ["finops", "cloud cost", "cloud-finops", "kubernetes cost"]

        headers = {"User-Agent": self.user_agent}

        with httpx.Client(timeout=self.timeout, follow_redirects=True) as client:
            for source in sources:
                try:
                    resp = client.get(source["url"], headers=headers)
                    if resp.status_code != 200:
                        continue
                    soup = BeautifulSoup(resp.text, "html.parser")
                    text = soup.get_text(separator=" ", strip=True)
                    if any(kw.lower() in text.lower() for kw in keywords):
                        item_id = hashlib.sha256(
                            f"web|{source['url']}|{datetime.now().isoformat()}".encode()
                        ).hexdigest()[:16]
                        title = soup.title.string if soup.title else source["url"]
                        items.append({
                            "id": item_id,
                            "date": datetime.now(timezone.utc).strftime("%Y-%m-%d"),
                            "source_id": urlparse(source["url"]).netloc,
                            "title": title[:500] if title else source["url"],
                            "url": source["url"],
                            "summary": text[:2000],
                            "tags": ",".join(keywords),
                            "category": source.get("category", "general"),
                            "content_raw": resp.text[:50000],
                            "content_parsed": "",
                        })
                except Exception as e:
                    print(f"  [Web] Error scraping {source.get('url')}: {e}")

        return items
