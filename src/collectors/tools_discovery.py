import hashlib
import re
from datetime import date, datetime, timezone

import httpx
from bs4 import BeautifulSoup

from .base import BaseCollector, is_within_max_age

TOOL_CATEGORIES = {
    "cost-visibility": ["cost-explorer", "cost-management", "cost-analysis", "cost-visibility", "billing"],
    "kubernetes": ["kubernetes", "k8s", "kubecost", "opencost", "container", "kube"],
    "rightsizing": ["rightsizing", "right-size", "compute-optimizer", "recommendations"],
    "commitment": ["savings-plans", "reserved-instances", "commitment", "discount"],
    "governance": ["governance", "policy", "compliance", "tagging", "budget", "guardrails"],
    "multi-cloud": ["multi-cloud", "multicloud", "cross-cloud", "hybrid-cloud"],
    "ai-cost": ["ai-cost", "gpu-cost", "ml-cost", "llm-cost", "model-cost"],
    "finops-platform": ["finops", "cloud-finops", "finops-platform", "cloud-cost-platform"],
    "open-source": ["open-source", "open source", "oss", "free"],
    "saas-cost": ["saas", "saas-cost", "saas-management", "software-management"],
}

CLOUD_KEYWORDS = {
    "aws": ["aws", "amazon web services"],
    "azure": ["azure", "microsoft azure"],
    "gcp": ["gcp", "google cloud", "google cloud platform"],
    "multi-cloud": ["multi-cloud", "multicloud", "cross-cloud"],
}

FINOPPS_TOOL_BLOGS = [
    {"name": "CloudZero FinOps Tools", "url": "https://www.cloudzero.com/blog/finops-tools/", "category": "finops-platform"},
    {"name": "Vantage FinOps Guide", "url": "https://www.vantage.sh/blog/best-finops-tools-for-cloud-cost-management", "category": "finops-platform"},
    {"name": "Finout FinOps Tools Guide", "url": "https://www.finout.io/blog/finops-tools-guide", "category": "finops-platform"},
    {"name": "Rapyer FinOps Tools", "url": "https://www.rapyder.com/blog/best-finops-tools/", "category": "finops-platform"},
    {"name": "Flexera FinOps Tools", "url": "https://www.flexera.com/blog/finops/finops-tools/", "category": "finops-platform"},
    {"name": "CloudFinOpsCost Tools", "url": "https://cloudfinopscost.com/tools", "category": "finops-platform"},
    {"name": "ResourceChest FinOps Tools", "url": "https://github.com/ResourceChest/finops-tools", "category": "finops-platform"},
]

GITHUB_TOOL_TOPICS = [
    "finops", "cloud-cost", "cloud-finops", "finops-tools",
    "cloud-cost-optimization", "kubernetes-cost", "opencost",
    "kubecost", "infracost", "cloud-financial-management",
    "cost-optimization", "cloud-management",
]


class ToolsDiscoveryCollector(BaseCollector):
    def name(self):
        return "Tools Discovery"

    def collect(self) -> list[dict]:
        tools = []
        discovered_from = set()

        gh_tools = self._discover_from_github()
        for t in gh_tools:
            key = t.get("github", t.get("url", ""))
            if key and key not in discovered_from:
                discovered_from.add(key)
                tools.append(t)

        blog_tools = self._discover_from_blog_lists()
        for t in blog_tools:
            key = t.get("url", "")
            if key and key not in discovered_from:
                discovered_from.add(key)
                tools.append(t)

        web_tools = self._discover_from_web()
        for t in web_tools:
            key = t.get("url", "")
            if key and key not in discovered_from:
                discovered_from.add(key)
                tools.append(t)

        for tool in tools:
            self._classify_tool(tool)
            tool["id"] = hashlib.sha256(
                (tool.get("github", "") or tool.get("url", "")).encode()
            ).hexdigest()[:16]
            tool["discovered_date"] = date.today().isoformat()

        return tools

    def _discover_from_github(self) -> list[dict]:
        tools = []
        headers = {"User-Agent": self.user_agent}
        token = self.config.get("api_keys", {}).get("github", "")
        if token:
            headers["Authorization"] = f"Bearer {token}"

        min_stars = self.config.get("sources", {}).get("api", {}).get("github", {}).get("min_stars", 5)

        with httpx.Client(timeout=self.timeout) as client:
            for topic in GITHUB_TOOL_TOPICS:
                try:
                    query = f"topic:{topic} stars:>={min_stars}"
                    resp = client.get(
                        "https://api.github.com/search/repositories",
                        params={"q": query, "sort": "stars", "order": "desc", "per_page": 15},
                        headers=headers,
                    )
                    if resp.status_code != 200:
                        continue
                    data = resp.json()
                    for repo in data.get("items", []):
                        pushed = repo.get("pushed_at")
                        if pushed:
                            pushed_dt = datetime.fromisoformat(pushed.replace("Z", "+00:00"))
                            if not is_within_max_age(pushed_dt):
                                continue

                        full_name = repo["full_name"]
                        topics = repo.get("topics", [])
                        lang = repo.get("language") or ""

                        is_open_source = True
                        license_info = repo.get("license")
                        gh_url = repo["html_url"]
                        stars = repo.get("stargazers_count", 0)

                        tools.append({
                            "name": repo.get("name", ""),
                            "vendor": self._detect_vendor(full_name, topics),
                            "category": "general",
                            "cloud": self._detect_cloud(topics, repo.get("description", ""), topics),
                            "open_source": is_open_source,
                            "url": repo.get("homepage") or gh_url,
                            "github": gh_url,
                            "description": (repo.get("description") or "")[:2000],
                            "tags": ",".join(topics),
                            "stars": stars,
                            "language": lang,
                        })
                except Exception as e:
                    print(f"  [Tools/GitHub] Error fetching topic '{topic}': {e}")

        return tools

    def _discover_from_blog_lists(self) -> list[dict]:
        tools = []
        headers = {"User-Agent": self.user_agent}

        with httpx.Client(timeout=self.timeout, follow_redirects=True) as client:
            for blog in FINOPPS_TOOL_BLOGS:
                try:
                    if "github.com" in blog["url"]:
                        parts = blog["url"].strip("/").split("/")
                        if len(parts) >= 5:
                            owner_repo = "/".join(parts[-2:])
                            gh_url = f"https://github.com/{owner_repo}"
                            tools.append({
                                "name": owner_repo,
                                "vendor": parts[-2],
                                "category": blog["category"],
                                "cloud": "multi-cloud",
                                "open_source": True,
                                "url": gh_url,
                                "github": gh_url,
                                "description": f"FinOps tools curated list from {blog['name']}",
                                "tags": "finops,tools,curated-list",
                            })
                        continue

                    resp = client.get(blog["url"])
                    if resp.status_code != 200:
                        continue
                    soup = BeautifulSoup(resp.text, "html.parser")
                    text = soup.get_text(separator=" ", strip=True)

                    gh_pattern = re.findall(
                        r'https?://github\.com/[\w.-]+/[\w.-]+(?!\S*\.\w{2,})',
                        text
                    )
                    seen = set()
                    for gh_url in gh_pattern[:10]:
                        gh_url = gh_url.rstrip("/).,;:")
                        if gh_url in seen:
                            continue
                        if "/blob/" in gh_url or "/tree/" in gh_url:
                            continue
                        seen.add(gh_url)
                        parts = gh_url.strip("/").split("/")
                        if len(parts) >= 5:
                            tools.append({
                                "name": parts[-1],
                                "vendor": parts[-2],
                                "category": blog["category"],
                                "cloud": "multi-cloud",
                                "open_source": True,
                                "url": gh_url,
                                "github": gh_url,
                                "description": f"Discovered from {blog['name']}",
                                "tags": "finops,tool",
                            })
                except Exception as e:
                    print(f"  [Tools/Blog] Error scraping {blog['name']}: {e}")

        return tools

    def _discover_from_web(self) -> list[dict]:
        tools = []
        known_tool_pages = [
            "https://www.finops.org/",
        ]
        headers = {"User-Agent": self.user_agent}

        with httpx.Client(timeout=self.timeout, follow_redirects=True) as client:
            for url in known_tool_pages:
                try:
                    resp = client.get(url)
                    if resp.status_code != 200:
                        continue
                    soup = BeautifulSoup(resp.text, "html.parser")
                    for link in soup.find_all("a", href=True):
                        href = link["href"]
                        if not href.startswith("https://github.com/"):
                            continue
                        if "/blob/" in href or "/tree/" in href:
                            continue
                        gh_url = href.split("?")[0].rstrip("/")
                        parts = gh_url.strip("/").split("/")
                        if len(parts) >= 5:
                            tools.append({
                                "name": parts[-1],
                                "vendor": parts[-2],
                                "category": "finops-platform",
                                "cloud": "multi-cloud",
                                "open_source": True,
                                "url": gh_url,
                                "github": gh_url,
                                "description": link.get("title") or f"Tool from finops.org",
                                "tags": "finops,tool",
                            })
                except Exception:
                    pass

        return tools

    def _detect_vendor(self, full_name: str, topics: list[str]) -> str:
        vendor = full_name.split("/")[0] if "/" in full_name else ""
        return vendor.replace("-", " ").title() if vendor else "Community"

    def _detect_cloud(self, repo_topics: list[str], description: str, all_tags: list[str]) -> str:
        text = " ".join(repo_topics + all_tags) + " " + (description or "").lower()
        for cloud, kws in CLOUD_KEYWORDS.items():
            if any(kw in text for kw in kws):
                return cloud
        return "multi-cloud"

    def _classify_tool(self, tool: dict):
        text = (
            tool.get("tags", "") + " "
            + (tool.get("description") or "").lower() + " "
            + tool.get("name", "").lower() + " "
            + tool.get("language", "")
        )
        for category, kws in TOOL_CATEGORIES.items():
            if any(kw.lower() in text for kw in kws):
                tool["category"] = category
                return
        tool["category"] = "general"

    def persist_tools(self, tools: list[dict]) -> int:
        if not self.db:
            return 0
        count = 0
        for tool in tools:
            try:
                self.db.upsert_tool(tool)
                count += 1
            except Exception as e:
                print(f"  [Tools] Error persisting {tool.get('name')}: {e}")
        return count
