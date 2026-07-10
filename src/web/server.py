from pathlib import Path

import yaml
from fastapi import FastAPI, Query
from fastapi.responses import HTMLResponse, FileResponse
from fastapi.staticfiles import StaticFiles

from src.storage.db import Database
from src.reporters.html_report import HTMLReporter

app = FastAPI(title="FinOps Intelligence Agent")


def create_app(config_path: str = "config.yaml") -> FastAPI:
    with open(config_path) as f:
        config = yaml.safe_load(f)

    db_path = config.get("storage", {}).get("db_path", "data/finops.db")
    db = Database(db_path)

    @app.get("/api/daily", summary="Get items by date")
    def get_daily(date: str = Query(default=None, description="Date YYYY-MM-DD")):
        if date:
            items = db.get_items_by_date(date)
        else:
            items = db.get_items(limit=100)
        return {"items": items, "count": len(items)}

    @app.get("/api/search", summary="Search items")
    def search(q: str = Query(min_length=1)):
        items = db.search_items(q)
        return {"items": items, "count": len(items)}

    @app.get("/api/tools", summary="List tools")
    def list_tools():
        return {"tools": db.get_tools()}

    @app.get("/api/sources", summary="List sources")
    def list_sources():
        return {"sources": db.get_sources()}

    @app.get("/api/runs", summary="Recent runs")
    def list_runs():
        return {"runs": db.get_recent_runs()}

    @app.post("/api/collect/now", summary="Trigger collection")
    def trigger_collect():
        from src.main import run_daily
        run_daily(config)
        return {"status": "completed"}

    @app.get("/api/report/daily", response_class=HTMLResponse, summary="Get daily HTML report")
    def report_daily(date: str = Query(default=None, description="Date YYYY-MM-DD")):
        from datetime import date as dt_date
        d = date or dt_date.today().isoformat()
        reporter = HTMLReporter(config, db)
        reports_dir = Path(config.get("storage", {}).get("reports_dir", "data/reports"))
        reports_dir.mkdir(parents=True, exist_ok=True)
        output = str(reports_dir / f"finops-daily-{d}.html")
        reporter.generate(d, output)
        return HTMLResponse(content=open(output).read())

    @app.get("/api/report/daily/pdf", summary="Get daily PDF report")
    def report_daily_pdf(date: str = Query(default=None, description="Date YYYY-MM-DD")):
        from datetime import date as dt_date
        d = date or dt_date.today().isoformat()
        from src.reporters.pdf_report import PDFReporter
        pdf_reporter = PDFReporter(config, db)
        reports_dir = Path(config.get("storage", {}).get("reports_dir", "data/reports"))
        reports_dir.mkdir(parents=True, exist_ok=True)
        output = str(reports_dir / f"finops-daily-{d}.pdf")
        pdf_reporter.generate(d, output)
        return FileResponse(output, media_type="application/pdf")

    return app


def start_server(config: dict):
    import uvicorn
    app.state.config = config
    port = config.get("server", {}).get("port", 8000)
    host = config.get("server", {}).get("host", "0.0.0.0")
    uvicorn.run(app, host=host, port=port)
