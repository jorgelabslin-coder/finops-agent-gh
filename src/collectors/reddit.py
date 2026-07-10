import hashlib
from datetime import datetime, timezone

import httpx

from .base import BaseCollector


class RedditCollector(BaseCollector):
    def name(self):
        return "Reddit"

    def collect(self) -> list[dict]:
        items = []
        subreddits = self.config.get("sources", {}).get("api", {}).get("reddit", {}).get("subreddits", [])
        keywords = ["finops", "cloud cost", "kubernetes cost", "cloud-finops"]

        headers = {"User-Agent": self.user_agent}

        with httpx.Client(timeout=self.timeout, headers=headers) as client:
            for sub in subreddits:
                try:
                    resp = client.get(
                        f"https://www.reddit.com/r/{sub}/hot.json",
                        params={"limit": 25},
                    )
                    if resp.status_code != 200:
                        continue
                    data = resp.json()
                    for post in data.get("data", {}).get("children", []):
                        p = post["data"]
                        title = p.get("title", "")
                        selftext = (p.get("selftext") or "")[:2000]

                        if not any(kw.lower() in (title + selftext).lower() for kw in keywords):
                            continue

                        ts = p.get("created_utc", 0)
                        dt = datetime.fromtimestamp(ts, tz=timezone.utc) if ts else datetime.now(timezone.utc)

                        item_id = hashlib.sha256(f"reddit|{p['id']}".encode()).hexdigest()[:16]
                        items.append({
                            "id": item_id,
                            "date": dt.strftime("%Y-%m-%d"),
                            "source_id": f"reddit-r-{sub.lower()}",
                            "title": title[:500],
                            "url": f"https://reddit.com{p['permalink']}",
                            "summary": selftext[:2000],
                            "tags": sub,
                            "category": "community",
                            "content_raw": "",
                            "content_parsed": "",
                        })
                except Exception as e:
                    print(f"  [Reddit] Error fetching r/{sub}: {e}")

        return items
