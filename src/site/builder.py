from datetime import date
from pathlib import Path

from jinja2 import Environment, FileSystemLoader


class SiteBuilder:
    def __init__(self, config: dict, db):
        self.config = config
        self.db = db
        template_dir = Path(__file__).parent / "templates"
        self.env = Environment(loader=FileSystemLoader(str(template_dir)))

    def build(self, output_dir: Path):
        output_dir.mkdir(parents=True, exist_ok=True)
        assets_dir = output_dir / "assets"
        assets_dir.mkdir(exist_ok=True)

        dates = self.db.get_distinct_dates()
        all_items = self.db.get_items(limit=5000)
        sources = self.db.get_sources()
        tools = self.db.get_tools()

        grouped_by_date = {}
        for item in all_items:
            d = item["date"]
            grouped_by_date.setdefault(d, []).append(item)

        self._render("index.html", output_dir / "index.html", {
            "dates": dates,
            "grouped_by_date": grouped_by_date,
            "sources": sources,
            "total_items": len(all_items),
        })

        day_dir = output_dir / "day"
        day_dir.mkdir(exist_ok=True)
        for d in dates[:30]:
            items = self.db.get_items_by_date(d)
            grouped = {}
            for item in items:
                cat = item.get("category", "general")
                grouped.setdefault(cat, []).append(item)
            self._render("day.html", day_dir / f"{d}.html", {
                "dt": d,
                "items": items,
                "grouped": grouped,
            })

        self._render("search.html", output_dir / "search.html", {
            "dates": dates,
        })

        self._render("tools.html", output_dir / "tools.html", {
            "tools": tools,
        })

        self._write_assets(assets_dir)

    def _render(self, template_name: str, output_path: Path, context: dict):
        template = self.env.get_template(template_name)
        html = template.render(**context)
        with open(output_path, "w", encoding="utf-8") as f:
            f.write(html)

    def _write_assets(self, assets_dir: Path):
        css = """* { margin:0; padding:0; box-sizing:border-box; }
body { font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',Roboto,sans-serif; background:#0f172a; color:#e2e8f0; line-height:1.6; }
.container { max-width:960px; margin:0 auto; padding:2rem 1rem; }
h1 { color:#38bdf8; }
a { color:#38bdf8; text-decoration:none; }
a:hover { text-decoration:underline; }
.card { background:#1e293b; border-radius:.5rem; padding:1rem; margin-bottom:.75rem; }
.card h3 { font-size:1rem; }
.card .meta { font-size:.8rem; color:#94a3b8; }
.card .summary { font-size:.875rem; color:#cbd5e1; margin-top:.5rem; }
.tag { display:inline-block; background:#334155; color:#38bdf8; font-size:.7rem; padding:.15rem .5rem; border-radius:999px; margin-right:.25rem; }
.date-header { color:#facc15; font-size:1.1rem; margin:1.5rem 0 .5rem; padding-bottom:.25rem; border-bottom:1px solid #334155; }
.search-box { margin-bottom:1.5rem; }
.search-box input { width:100%; padding:.75rem; background:#1e293b; border:1px solid #334155; border-radius:.5rem; color:#e2e8f0; font-size:1rem; }
.stats { display:flex; gap:1rem; margin-bottom:2rem; flex-wrap:wrap; }
.stat { background:#1e293b; padding:1rem 1.5rem; border-radius:.5rem; text-align:center; }
.stat-value { font-size:1.5rem; font-weight:700; color:#38bdf8; }
.stat-label { font-size:.75rem; color:#94a3b8; text-transform:uppercase; }
.footer { text-align:center; color:#475569; font-size:.8rem; margin-top:3rem; }
.nav { margin-bottom:1rem; }
.nav a { margin-right:1rem; }
"""
        with open(assets_dir / "style.css", "w") as f:
            f.write(css)
