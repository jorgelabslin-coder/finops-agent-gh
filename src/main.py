import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import argparse
from datetime import date, datetime

import yaml
from rich.console import Console

from src.storage.db import Database
from src.storage.snapshot import SnapshotManager
from src.collectors.rss_sources import RSSCollector
from src.collectors.github_tools import GitHubCollector
from src.collectors.hackernews import HackerNewsCollector
from src.collectors.reddit import RedditCollector
from src.collectors.web_scraper import WebScraper
from src.site.builder import SiteBuilder
from src.reporters.html_report import HTMLReporter

console = Console()


def load_config(path: str = "config.yaml") -> dict:
    with open(path) as f:
        return yaml.safe_load(f)


def collect_all(config: dict, db: Database) -> list[dict]:
    all_items = []
    collectors = [
        RSSCollector(config, db),
        GitHubCollector(config, db),
        HackerNewsCollector(config, db),
        RedditCollector(config, db),
        WebScraper(config, db),
    ]

    for collector in collectors:
        console.print(f"  Collecting from [bold]{collector.name()}[/bold]...")
        try:
            items = collector.collect()
            all_items.extend(items)
            console.print(f"    → {len(items)} items")
        except Exception as e:
            console.print(f"    [red]Error: {e}[/red]")

    return all_items


def store_items(db: Database, items: list[dict]):
    new_count = 0
    seen_sources = set()
    for item in items:
        sid = item.get("source_id", "")
        if sid and sid not in seen_sources:
            seen_sources.add(sid)
            db.upsert_source(sid, sid.replace("-", " ").title(), "auto", "")
        if db.insert_item(item):
            new_count += 1
    return new_count


def run_daily(config: dict):
    db_path = config.get("storage", {}).get("db_path", "data/finops.db")
    snapshots_dir = config.get("storage", {}).get("snapshots_dir", "data/snapshots")
    reports_dir = config.get("storage", {}).get("reports_dir", "data/reports")
    site_dir = config.get("storage", {}).get("site_dir", "data/site")

    Path(db_path).parent.mkdir(parents=True, exist_ok=True)
    db = Database(db_path)
    today = date.today().isoformat()
    run_id = db.start_run(today)

    console.print(f"\n[bold cyan]FinOps Intelligence Agent — Daily Run {today}[/bold cyan]\n")

    items = collect_all(config, db)
    new_count = store_items(db, items)

    SnapshotManager(snapshots_dir).save(date.today(), items)

    db.finish_run(run_id, new_count)
    console.print(f"\n[green]✓ Stored {new_count} new items[/green]")

    reports_dir_path = Path(reports_dir)
    reports_dir_path.mkdir(parents=True, exist_ok=True)
    report_path = reports_dir_path / f"finops-daily-{today}.html"
    reporter = HTMLReporter(config, db)
    reporter.generate(today, str(report_path))
    console.print(f"[green]✓ HTML report: {report_path}[/green]")

    site_path = Path(site_dir)
    site_path.mkdir(parents=True, exist_ok=True)
    builder = SiteBuilder(config, db)
    builder.build(site_path)
    console.print(f"[green]✓ Static site: {site_path}/index.html[/green]")

    db.close()
    console.print("[bold green]Done![/bold green]")


def serve(config: dict):
    from src.web.server import start_server
    start_server(config)


def main():
    parser = argparse.ArgumentParser(description="FinOps Intelligence Agent")
    parser.add_argument("--config", default="config.yaml", help="Config file path")
    parser.add_argument("--daily", action="store_true", help="Run daily collection")
    parser.add_argument("--serve", action="store_true", help="Start web UI server")

    args = parser.parse_args()
    config = load_config(args.config)

    if args.daily:
        run_daily(config)
    elif args.serve:
        serve(config)
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
