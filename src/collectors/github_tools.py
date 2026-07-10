import hashlib
from datetime import datetime, timezone

import httpx

from .base import BaseCollector


class GitHubCollector(BaseCollector):
    def name(self):
        return "GitHub"

    def collect(self) -> list[dict]:
        items = []
        gh_config = self.config.get("sources", {}).get("api", {}).get("github", {})
        topics = gh_config.get("topics", [])
        min_stars = gh_config.get("min_stars", 5)

        headers = {"User-Agent": self.user_agent}
        if token := self.config.get("api_keys", {}).get("github"):
            headers["Authorization"] = f"Bearer {token}"

        with httpx.Client(timeout=self.timeout) as client:
            for topic in topics:
                try:
                    query = f"topic:{topic} stars:>={min_stars}"
                    resp = client.get(
                        "https://api.github.com/search/repositories",
                        params={"q": query, "sort": "updated", "per_page": 10},
                        headers=headers,
                    )
                    if resp.status_code != 200:
                        continue
                    data = resp.json()
                    for repo in data.get("items", []):
                        item_id = hashlib.sha256(
                            f"github|{repo['id']}".encode()
                        ).hexdigest()[:16]
                        updated = datetime.fromiso_string(
                            repo["updated_at"].replace("Z", "+00:00")
                        )
                        items.append({
                            "id": item_id,
                            "date": updated.strftime("%Y-%m-%d"),
                            "source_id": "github",
                            "title": f"[{repo['full_name']}] {repo.get('description', '')[:120]}",
                            "url": repo["html_url"],
                            "summary": repo.get("description", "")[:2000],
                            "tags": topic,
                            "category": "tools",
                            "content_raw": "",
                            "content_parsed": "",
                        })
                except Exception as e:
                    print(f"  [GitHub] Error fetching topic '{topic}': {e}")

        return items
