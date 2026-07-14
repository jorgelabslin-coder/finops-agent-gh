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

        root_path = ""
        css_path = "assets/"

        self._render("index.html", output_dir / "index.html", {
            "dates": dates,
            "grouped_by_date": grouped_by_date,
            "sources": sources,
            "total_items": len(all_items),
            "root_path": root_path,
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
                "root_path": "../",
                "css_path": "../assets/",
            })

        self._render("search.html", output_dir / "search.html", {
            "dates": dates,
            "root_path": root_path,
            "css_path": css_path,
        })

        self._render("tools.html", output_dir / "tools.html", {
            "tools": tools,
            "root_path": root_path,
            "css_path": css_path,
        })

        # Generate dashboard
        self._generate_dashboard(output_dir, all_items, sources, tools, root_path, css_path)

        # Generate monthly pages
        self._generate_monthly(output_dir, all_items, dates, day_dir)

        # Generate archive
        self._generate_archive(output_dir, dates, root_path, css_path)

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

    def _generate_dashboard(self, output_dir, all_items, sources, tools, root_path, css_path):
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
            "root_path": root_path,
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
                "root_path": "../",
                "css_path": "../assets/",
            })

    def _generate_archive(self, output_dir, dates, root_path, css_path):
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
            "root_path": root_path,
            "css_path": css_path,
        })

    def _render(self, template_name: str, output_path: Path, context: dict):
        template = self.env.get_template(template_name)
        html = template.render(**context)
        with open(output_path, "w", encoding="utf-8") as f:
            f.write(html)

    def _write_assets(self, assets_dir: Path):
        css = """@import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700;800&display=swap');
* { margin:0; padding:0; box-sizing:border-box; }
::selection { background:rgba(96,165,250,0.3); color:#fff; }
body { font-family:'Inter',-apple-system,BlinkMacSystemFont,'Segoe UI',Roboto,sans-serif; background:#07070d; color:#e2e8f0; line-height:1.7; -webkit-font-smoothing:antialiased; }
.container { max-width:1100px; margin:0 auto; padding:2rem 1.5rem; }
.nav { display:flex; align-items:center; gap:0.25rem; padding:0.75rem 0; margin-bottom:3rem; border-bottom:1px solid rgba(255,255,255,0.04); }
.nav a { color:#64748b; text-decoration:none; font-size:0.875rem; font-weight:500; padding:0.5rem 1rem; border-radius:8px; transition:all 0.2s; }
.nav a:hover { color:#f1f5f9; background:rgba(255,255,255,0.04); text-decoration:none; }
.nav a.active { color:#60a5fa; background:rgba(96,165,250,0.08); }
.nav .nav-brand { font-weight:700; font-size:1rem; color:#f1f5f9; margin-right:auto; padding:0.5rem 0; letter-spacing:-0.02em; background:none; }
.nav .nav-brand:hover { background:none; color:#60a5fa; }
.hero { text-align:center; padding:2rem 0 1.5rem; position:relative; }
.hero h1 { font-size:clamp(1.8rem,3vw,2.5rem); font-weight:800; letter-spacing:-0.03em; background:linear-gradient(135deg,#f1f5f9 0%,#60a5fa 50%,#a78bfa 100%); -webkit-background-clip:text; -webkit-text-fill-color:transparent; background-clip:text; margin-bottom:0.5rem; }
.hero p { font-size:1.125rem; color:#64748b; max-width:600px; margin:0 auto; }
h1 { font-size:2rem; font-weight:700; color:#f1f5f9; letter-spacing:-0.02em; margin-bottom:0.5rem; }
h2 { font-size:1.25rem; font-weight:600; color:#f1f5f9; letter-spacing:-0.01em; }
a { color:#60a5fa; text-decoration:none; transition:color 0.2s; }
a:hover { color:#93bbfc; }
.card { background:#0d0d18; border:1px solid rgba(255,255,255,0.05); border-radius:12px; padding:1.25rem; margin-bottom:0.75rem; transition:all 0.25s; }
.card:hover { border-color:rgba(96,165,250,0.2); box-shadow:0 4px 24px rgba(96,165,250,0.06); transform:translateY(-1px); }
.card h3 { font-size:0.95rem; font-weight:600; line-height:1.5; }
.card h3 a { color:#e2e8f0; }
.card h3 a:hover { color:#60a5fa; }
.card .meta { font-size:0.8rem; color:#64748b; }
.card .summary { font-size:0.85rem; color:#94a3b8; margin-top:0.5rem; line-height:1.6; }
.tag { display:inline-block; background:linear-gradient(135deg,rgba(96,165,250,0.1),rgba(167,139,250,0.1)); color:#a78bfa; font-size:0.7rem; font-weight:500; padding:0.15rem 0.6rem; border-radius:999px; margin-right:0.25rem; border:1px solid rgba(167,139,250,0.15); }
.date-header { font-size:1.05rem; font-weight:600; color:#fbbf24; margin:2rem 0 1rem; padding-bottom:0.5rem; border-bottom:1px solid rgba(255,255,255,0.05); }
.date-header a { color:#fbbf24; }
.date-header a:hover { color:#fcd34d; }
.search-box { margin-bottom:2rem; }
.search-box input { width:100%; padding:0.875rem 1.25rem; background:#0d0d18; border:1px solid rgba(255,255,255,0.08); border-radius:12px; color:#f1f5f9; font-size:1rem; font-family:'Inter',sans-serif; outline:none; transition:all 0.25s; }
.search-box input::placeholder { color:#475569; }
.search-box input:focus { border-color:rgba(96,165,250,0.4); box-shadow:0 0 0 3px rgba(96,165,250,0.08); }
.stats { display:flex; gap:1rem; margin-bottom:2.5rem; flex-wrap:wrap; }
.stat { background:#0d0d18; border:1px solid rgba(255,255,255,0.05); border-radius:12px; padding:1.25rem 2rem; text-align:center; flex:1; min-width:120px; transition:all 0.25s; }
.stat:hover { border-color:rgba(96,165,250,0.2); transform:translateY(-1px); box-shadow:0 4px 20px rgba(96,165,250,0.05); }
.stat-value { font-size:1.75rem; font-weight:800; color:#60a5fa; letter-spacing:-0.02em; }
.stat-label { font-size:0.75rem; color:#64748b; text-transform:uppercase; letter-spacing:0.05em; font-weight:500; margin-top:0.25rem; }
.footer { text-align:center; color:#334155; font-size:0.8rem; margin-top:4rem; padding-top:2rem; border-top:1px solid rgba(255,255,255,0.04); }
.footer a { color:#475569; }
.footer a:hover { color:#60a5fa; }
.footer .footer-brand { color:#64748b; font-weight:500; }
.chart-grid { display:grid; grid-template-columns:1fr 1fr; gap:1.25rem; margin:2rem 0; }
@media (max-width:700px) { .chart-grid { grid-template-columns:1fr; } }
.chart-card { background:#0d0d18; border:1px solid rgba(255,255,255,0.05); border-radius:12px; padding:1.5rem; transition:all 0.25s; }
.chart-card:hover { border-color:rgba(255,255,255,0.1); }
.chart-card h2 { font-size:0.9rem; font-weight:600; color:#94a3b8; text-transform:uppercase; letter-spacing:0.04em; margin-bottom:1rem; }
.month-nav { display:flex; align-items:center; justify-content:space-between; padding:1rem 0; margin-bottom:1.5rem; border-bottom:1px solid rgba(255,255,255,0.05); }
.month-nav a { font-size:0.9rem; font-weight:500; color:#60a5fa; padding:0.4rem 0.8rem; border-radius:8px; transition:all 0.2s; }
.month-nav a:hover { background:rgba(96,165,250,0.08); }
.current-month { font-size:1rem; font-weight:600; color:#f1f5f9; }
.archive-grid { display:grid; grid-template-columns:repeat(auto-fill,minmax(180px,1fr)); gap:1rem; margin:1rem 0 2rem; }
.archive-card { display:block; background:#0d0d18; border:1px solid rgba(255,255,255,0.05); border-radius:12px; padding:1.25rem; text-align:center; transition:all 0.25s; }
.archive-card:hover { border-color:rgba(96,165,250,0.2); transform:translateY(-2px); box-shadow:0 8px 24px rgba(96,165,250,0.06); text-decoration:none; }
.month-name { font-size:1.1rem; font-weight:600; color:#f1f5f9; margin-bottom:0.25rem; }
.month-count { font-size:0.85rem; color:#60a5fa; font-weight:500; }
.month-days { font-size:0.75rem; color:#64748b; }
.back-link { display:inline-block; font-size:0.9rem; font-weight:500; color:#64748b; padding:0.4rem 0.8rem; border-radius:8px; transition:all 0.2s; margin-top:1.5rem; }
.back-link:hover { color:#60a5fa; background:rgba(96,165,250,0.08); }
.view-all { font-size:0.85rem; font-weight:500; color:#60a5fa; margin-top:0.25rem; display:inline-block; transition:all 0.2s; }
.view-all:hover { color:#93bbfc; transform:translateX(2px); }
code { font-family:'SF Mono','Fira Code','Cascadia Code',monospace; background:rgba(255,255,255,0.04); border:1px solid rgba(255,255,255,0.06); padding:0.15rem 0.4rem; border-radius:6px; font-size:0.85em; color:#a78bfa; }
p { margin-bottom:1rem; color:#94a3b8; }
"""
        with open(assets_dir / "style.css", "w") as f:
            f.write(css)
