import json
from collections import defaultdict
from datetime import date, datetime
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

        all_items = self.db.get_items(limit=5000)
        sources = self.db.get_sources()
        tools = self.db.get_tools()

        grouped_by_date = {}
        for item in all_items:
            d = item["date"]
            grouped_by_date.setdefault(d, []).append(item)

        dates = sorted(grouped_by_date.keys(), reverse=True)

        # root-level CSS path
        css_path = "assets/"

        self._render("index.html", output_dir / "index.html", {
            "dates": dates,
            "grouped_by_date": grouped_by_date,
            "sources": sources,
            "total_items": len(all_items),
            "css_path": css_path,
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
                "css_path": "../assets/",
            })

        self._render("search.html", output_dir / "search.html", {
            "dates": dates,
            "css_path": css_path,
        })

        self._render("tools.html", output_dir / "tools.html", {
            "tools": tools,
            "css_path": css_path,
        })

        # Generate dashboard
        self._generate_dashboard(output_dir, all_items, sources, tools, css_path)

        # Generate monthly pages
        self._generate_monthly(output_dir, all_items, dates, day_dir)

        # Generate archive
        self._generate_archive(output_dir, dates, css_path)

        # Search items.json
        search_items = [
            {
                "title": item.get("title", ""),
                "url": item.get("url", ""),
                "summary": (item.get("summary") or "")[:300],
                "date": item.get("date", ""),
                "source_name": item.get("source_name", item.get("source_id", "")),
                "tags": item.get("tags", ""),
            }
            for item in all_items
        ]
        with open(day_dir / "items.json", "w", encoding="utf-8") as f:
            json.dump(search_items, f, ensure_ascii=False)

        self._write_assets(assets_dir)

    def _generate_dashboard(self, output_dir, all_items, sources, tools, css_path):
        items_by_date = defaultdict(int)
        items_by_category = defaultdict(int)
        items_by_source = defaultdict(int)
        items_by_month = defaultdict(int)

        for item in all_items:
            d = item.get("date", "")
            items_by_date[d] += 1
            items_by_category[item.get("category", "general")] += 1
            source = item.get("source_name", item.get("source_id", "unknown"))
            items_by_source[source] += 1
            if len(d) >= 7:
                month_key = d[:7]
                items_by_month[month_key] += 1

        sorted_dates = sorted(items_by_date.keys())
        self._render("dashboard.html", output_dir / "dashboard.html", {
            "total_items": len(all_items),
            "total_days": len(items_by_date),
            "sources": sources,
            "tools": tools,
            "chart_dates_labels": json.dumps(sorted_dates[-30:]),
            "chart_dates_data": json.dumps([items_by_date[d] for d in sorted_dates[-30:]]),
            "chart_categories_labels": json.dumps(list(items_by_category.keys())),
            "chart_categories_data": json.dumps(list(items_by_category.values())),
            "chart_sources_labels": json.dumps(list(items_by_source.keys())),
            "chart_sources_data": json.dumps(list(items_by_source.values())),
            "chart_monthly_labels": json.dumps(sorted(items_by_month.keys())),
            "chart_monthly_data": json.dumps([items_by_month[m] for m in sorted(items_by_month.keys())]),
            "css_path": css_path,
        })

    def _generate_monthly(self, output_dir, all_items, dates, day_dir):
        items_by_month = defaultdict(list)
        for d in dates:
            month_key = d[:7]
            items_by_month[month_key].append(d)

        month_dir = output_dir / "month"
        month_dir.mkdir(exist_ok=True)

        sorted_months = sorted(items_by_month.keys())
        for i, month_key in enumerate(sorted_months):
            month_dates = sorted(items_by_month[month_key], reverse=True)
            month_items = defaultdict(list)
            total = 0
            for d in month_dates:
                day_items = self.db.get_items_by_date(d)
                month_items[d] = day_items
                total += len(day_items)

            dt = datetime.strptime(month_key + "-01", "%Y-%m-%d")
            month_label = dt.strftime("%B %Y")

            prev_month = sorted_months[i - 1] if i > 0 else None
            next_month = sorted_months[i + 1] if i < len(sorted_months) - 1 else None

            def fmt_month(m):
                d = datetime.strptime(m + "-01", "%Y-%m-%d")
                return d.strftime("%B %Y")

            self._render("month.html", month_dir / f"{month_key}.html", {
                "month_label": month_label,
                "month_key": month_key,
                "total_items": total,
                "dates": month_dates,
                "items_by_date": month_items,
                "prev_month": prev_month,
                "prev_month_label": fmt_month(prev_month) if prev_month else None,
                "prev_month_url": f"../month/{prev_month}.html" if prev_month else None,
                "next_month": next_month,
                "next_month_label": fmt_month(next_month) if next_month else None,
                "next_month_url": f"../month/{next_month}.html" if next_month else None,
                "day_url_prefix": "../day/",
                "css_path": "../assets/",
            })

    def _generate_archive(self, output_dir, dates, css_path):
        years = defaultdict(lambda: defaultdict(dict))
        for d in dates:
            year = d[:4]
            month_key = d[:7]
            dt = datetime.strptime(month_key + "-01", "%Y-%m-%d")
            label = dt.strftime("%B")

            if "label" not in years[year][month_key]:
                years[year][month_key] = {"label": label, "count": 0, "days": 0}
            years[year][month_key]["count"] += 1
            years[year][month_key]["days"] += 1

        # count items per month instead of days
        years_items = defaultdict(lambda: defaultdict(lambda: {"label": "", "count": 0, "days": 0}))
        for d in dates:
            year = d[:4]
            month_key = d[:7]
            dt = datetime.strptime(month_key + "-01", "%Y-%m-%d")
            label = dt.strftime("%B")
            years_items[year][month_key]["label"] = label
            years_items[year][month_key]["count"] += 1
            years_items[year][month_key]["days"] = len(set(
                dd for dd in dates if dd.startswith(month_key)
            ))

        self._render("archive.html", output_dir / "archive.html", {
            "years": dict(years_items),
            "css_path": css_path,
        })

    def _render(self, template_name: str, output_path: Path, context: dict):
        template = self.env.get_template(template_name)
        html = template.render(**context)
        with open(output_path, "w", encoding="utf-8") as f:
            f.write(html)

    def _write_assets(self, assets_dir: Path):
        css = """* { margin:0; padding:0; box-sizing:border-box; }
body { font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',Roboto,sans-serif; background:#0f172a; color:#e2e8f0; line-height:1.6; }
.container { max-width:960px; margin:0 auto; padding:2rem 1rem; }
h1 { color:#38bdf8; font-size:1.5rem; margin-bottom:.5rem; }
h1 + p { color:#94a3b8; margin-bottom:1.5rem; }
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
.search-box input:focus { outline:none; border-color:#38bdf8; }
.stats { display:flex; gap:1rem; margin-bottom:2rem; flex-wrap:wrap; }
.stat { background:#1e293b; padding:1rem 1.5rem; border-radius:.5rem; text-align:center; flex:1; min-width:100px; }
.stat-value { font-size:1.5rem; font-weight:700; color:#38bdf8; }
.stat-label { font-size:.75rem; color:#94a3b8; text-transform:uppercase; }
.footer { text-align:center; color:#475569; font-size:.8rem; margin-top:3rem; padding-top:1rem; border-top:1px solid #1e293b; }
.nav { margin-bottom:1.5rem; display:flex; gap:.5rem; flex-wrap:wrap; }
.nav a { background:#1e293b; padding:.4rem .8rem; border-radius:.4rem; font-size:.85rem; transition:background .2s; }
.nav a:hover { background:#334155; text-decoration:none; }
.chart-grid { display:grid; grid-template-columns:1fr 1fr; gap:1rem; margin-bottom:2rem; }
@media (max-width:640px) { .chart-grid { grid-template-columns:1fr; } }
.chart-card { background:#1e293b; border-radius:.5rem; padding:1rem; }
.chart-card h2 { color:#facc15; font-size:1rem; margin-bottom:.75rem; }
.month-nav { display:flex; justify-content:space-between; align-items:center; margin:1.5rem 0; }
.month-nav a { background:#1e293b; padding:.5rem 1rem; border-radius:.4rem; }
.current-month { font-size:1.1rem; color:#facc15; font-weight:600; }
.archive-grid { display:grid; grid-template-columns:repeat(auto-fill,minmax(180px,1fr)); gap:.75rem; margin-bottom:2rem; }
.archive-card { background:#1e293b; border-radius:.5rem; padding:1rem; text-align:center; transition:background .2s; }
.archive-card:hover { background:#334155; text-decoration:none; }
.month-name { font-size:1.1rem; font-weight:600; color:#38bdf8; }
.month-count { font-size:.85rem; color:#94a3b8; margin-top:.25rem; }
.month-days { font-size:.75rem; color:#64748b; }
"""
        with open(assets_dir / "style.css", "w") as f:
            f.write(css)
