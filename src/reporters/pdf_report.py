from pathlib import Path

from .html_report import HTMLReporter


class PDFReporter:
    def __init__(self, config: dict, db):
        self.config = config
        self.db = db
        self.html_reporter = HTMLReporter(config, db)

    def generate(self, dt: str, output_path: str):
        html_path = Path(output_path).with_suffix(".html")
        self.html_reporter.generate(dt, str(html_path))

        try:
            from playwright.sync_api import sync_playwright
            with sync_playwright() as p:
                browser = p.chromium.launch()
                page = browser.new_page()
                page.goto(f"file://{html_path.resolve()}")
                page.pdf(path=output_path, format="A4", print_background=True)
                browser.close()
            html_path.unlink()
        except ImportError:
            print("  [PDF] Playwright not available. Install with: pip install playwright && playwright install chromium")
