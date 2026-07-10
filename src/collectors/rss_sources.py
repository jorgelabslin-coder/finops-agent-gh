import hashlib
from datetime import datetime, timezone

import feedparser

from .base import BaseCollector


class RSSCollector(BaseCollector):
    def name(self):
        return "RSS Feeds"

    def collect(self) -> list[dict]:
        items = []
        rss_configs = self.config.get("sources", {}).get("rss", [])
        for cfg in rss_configs:
            try:
                feed = feedparser.parse(cfg["url"])
                for entry in feed.entries[:self.config.get("collect", {}).get("max_items_per_source", 50)]:
                    published = entry.get("published_parsed") or entry.get("updated_parsed")
                    if published:
                        dt = datetime(*published[:6], tzinfo=timezone.utc)
                    else:
                        dt = datetime.now(timezone.utc)

                    item_id = hashlib.sha256(
                        (cfg["url"] + "|" + entry.get("link", entry.get("id", ""))).encode()
                    ).hexdigest()[:16]

                    items.append({
                        "id": item_id,
                        "date": dt.strftime("%Y-%m-%d"),
                        "source_id": cfg["name"].lower().replace(" ", "-"),
                        "title": entry.get("title", "").strip(),
                        "url": entry.get("link", ""),
                        "summary": (entry.get("summary") or entry.get("description") or "")[:2000],
                        "tags": ",".join(t.get("term", "") for t in entry.get("tags", [])),
                        "category": cfg.get("category", "general"),
                        "content_raw": entry.get("content", [{}])[0].get("value", "") if entry.get("content") else "",
                        "content_parsed": "",
                    })
            except Exception as e:
                print(f"  [RSS] Error fetching {cfg.get('name')}: {e}")

        return items
