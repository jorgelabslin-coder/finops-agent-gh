from pathlib import Path

import yaml
from fastapi import FastAPI, Header, HTTPException, Query
from fastapi.responses import HTMLResponse, FileResponse
from fastapi.staticfiles import StaticFiles

from src.storage.db import Database
from src.reporters.html_report import HTMLReporter

import os
import re
import time

_DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")
_RATE_LIMIT_SECONDS = 60.0
_last_collect_ts: dict = {"ts": 0.0}


def _require_token(x_api_token: str = Header(default="")) -> None:
    expected = os.environ.get("FINOPS_API_TOKEN", "")
    if not expected:
        raise HTTPException(status_code=503, detail="API token not configured")
    if x_api_token != expected:
        raise HTTPException(status_code=401, detail="Invalid or missing API token")


def _validate_date(d: str) -> str:
    if d and not _DATE_RE.fullmatch(d):
        raise HTTPException(status_code=400, detail="Invalid date, expected YYYY-MM-DD")
    return d or time.strftime("%Y-%m-%d")

def create_app(config_path: str = "config.yaml") -> FastAPI:
    with open(config_path) as f:
        config = yaml.safe_load(f)

    app = FastAPI(title="FinOps Intelligence Agent")

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
    def trigger_collect(x_api_token: str = Header(default="")):
        _require_token(x_api_token)
        now = time.time()
        if now - _last_collect_ts["ts"] < _RATE_LIMIT_SECONDS:
            raise HTTPException(status_code=429, detail="Rate limited, wait before triggering another collection")
        _last_collect_ts["ts"] = now
        from src.main import run_daily
        run_daily(config)
        return {"status": "completed"}

    @app.get("/api/report/daily", response_class=HTMLResponse, summary="Get daily HTML report")
    def report_daily(date: str = Query(default=None, description="Date YYYY-MM-DD")):
        d = _validate_date(date)
        reporter = HTMLReporter(config, db)
        reports_dir = Path(config.get("storage", {}).get("reports_dir", "data/reports"))
        reports_dir.mkdir(parents=True, exist_ok=True)
        output = str(reports_dir / f"finops-daily-{d}.html")
        reporter.generate(d, output)
        return HTMLResponse(content=open(output).read())

    @app.get("/api/report/daily/pdf", summary="Get daily PDF report")
    def report_daily_pdf(date: str = Query(default=None, description="Date YYYY-MM-DD")):
        d = _validate_date(date)
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
    app = create_app()
    port = int(os.environ.get("FINOPS_PORT", config.get("server", {}).get("port", 8000)))
    host = os.environ.get("FINOPS_HOST", config.get("server", {}).get("host", "127.0.0.1"))
    uvicorn.run(app, host=host, port=port)
