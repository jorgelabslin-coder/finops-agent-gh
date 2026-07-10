import hashlib
from datetime import datetime, timezone

import httpx

from .base import BaseCollector


class HackerNewsCollector(BaseCollector):
    API_BASE = "https://hacker-news.firebaseio.com/v0"

    def name(self):
        return "Hacker News"

    def collect(self) -> list[dict]:
        items = []
        keywords = self.config.get("sources", {}).get("api", {}).get("hackernews", {}).get("keywords", [])

        with httpx.Client(timeout=self.timeout) as client:
            try:
                resp = client.get(f"{self.API_BASE}/newstories.json")
                if resp.status_code != 200:
                    return items
                story_ids = resp.json()[:50]
            except Exception as e:
                print(f"  [HN] Error fetching story list: {e}")
                return items

            for sid in story_ids:
                try:
                    resp = client.get(f"{self.API_BASE}/item/{sid}.json")
                    if resp.status_code != 200:
                        continue
                    story = resp.json()
                    if not story or story.get("type") != "story":
                        continue

                    title = story.get("title", "")
                    text = (story.get("text") or "")[:2000]

                    if not any(kw.lower() in (title + text).lower() for kw in keywords):
                        continue

                    ts = story.get("time", 0)
                    dt = datetime.fromtimestamp(ts, tz=timezone.utc) if ts else datetime.now(timezone.utc)

                    item_id = hashlib.sha256(f"hn|{sid}".encode()).hexdigest()[:16]
                    items.append({
                        "id": item_id,
                        "date": dt.strftime("%Y-%m-%d"),
                        "source_id": "hacker-news",
                        "title": title[:500],
                        "url": story.get("url", f"https://news.ycombinator.com/item?id={sid}"),
                        "summary": text[:2000],
                        "tags": ",".join(keywords),
                        "category": "community",
                        "content_raw": "",
                        "content_parsed": "",
                    })
                except Exception as e:
                    print(f"  [HN] Error processing story {sid}: {e}")

        return items
