# FinOps Intelligence Agent — Plan Maestro

## Objetivo

Agente containerizado que recopila, indexa y genera reportes diarios del ecosistema FinOps
(novedades, herramientas, productos, tecnologías) con histórico consultable y exportable a HTML/PDF.

---

## 1. Arquitectura

```
                      ┌─────────────────────────┐
                      │   Scheduler (cron/CI)    │
                      │    daily @ 06:30 UTC     │
                      └─────────┬───────────────┘
                                │
              ┌─────────────────▼─────────────────┐
              │        FinOps Collector Agent       │
              │  (Python container / 3.12 slim)     │
              ├─────────────────────────────────────┤
              │  - Web scraping (httpx + bs4)       │
              │  - RSS feeds (feedparser)           │
              │  - API sources (GitHub, HN, Reddit) │
              │  - Cloud APIs (AWS/GCP/Azure)       │
              └─────────────────┬───────────────────┘
                                │
              ┌─────────────────▼─────────────────┐
              │           Storage Layer             │
              │  SQLite (histórico portable)        │
              │  + JSON snapshots por día           │
              └─────────────────┬───────────────────┘
                                │
              ┌─────────────────▼─────────────────┐
              │         Outputs                     │
              │  - HTML single-file (compartible)   │
              │  - PDF (bajo demanda)               │
              │  - Sitio estático (GitHub Pages)    │
              │  - FastAPI Web UI (Docker local)    │
              └─────────────────────────────────────┘
```

---

## 2. Stack Tecnológico

| Componente | Tecnología | Justificación |
|---|---|---|
| Lenguaje | Python 3.12+ | Madurez scraping, PDF, APIs |
| Scraping | `httpx` + `beautifulsoup4` | HTTPS/2 async, parsing robusto |
| RSS | `feedparser` | Fuentes RSS FinOps |
| APIs | `boto3`, `google-cloud-billing`, `azure-mgmt-costmanagement` | Cloud providers |
| Almacenamiento | SQLite + JSON files | Cero dependencias externas, portable |
| Web estática | Jinja2 + Fuse.js (JS client-side) | Búsqueda sin backend |
| Web dinámica | FastAPI + Jinja2 (modo Docker) | Búsqueda SQL directa |
| PDF | Playwright headless | HTML→PDF fiel |
| Contenedor | Docker (python:3.12-slim) | Portable, cualquier plataforma |
| CI/CD | GitHub Actions + Pages | Pipeline diario gratuito |

---

## 3. Fuentes de Datos

### RSS / Blogs
- FinOps Foundation blog
- AWS What's New
- Google Cloud Blog
- Azure Updates
- The Duckbill Group
- Last Week in AWS
- Infracost blog, KubeCost blog, OpenCost updates

### APIs Públicas Gratuitas
- **GitHub API**: repos con topic `finops`, `cloud-cost`, `cloud-finops`
- **Hacker News API**: stories sobre `finops`, `cloud cost`, `kubernetes cost`
- **Reddit API**: `r/FinOps`, `r/cloudcost`, `r/aws`, `r/googlecloud`
- **Dev.to API**: artículos tag `finops`, `cloudcost`

### Cloud Provider APIs (Free Tier)
- AWS Cost Explorer API
- GCP Cloud Billing API
- Azure Cost Management API

---

## 4. Estructura del Proyecto

```
finops-agent/
├── Dockerfile
├── docker-compose.yml
├── requirements.txt
├── config.yaml                   # Fuentes + keywords configurables
├── .github/
│   └── workflows/
│       └── daily-collect.yml     # Pipeline CI/CD gratuito
├── src/
│   ├── main.py                   # Entrypoint CLI
│   ├── collectors/
│   │   ├── base.py
│   │   ├── rss_sources.py        # Feedparser
│   │   ├── web_scraper.py        # httpx + bs4
│   │   ├── github_tools.py       # GitHub API → herramientas nuevas
│   │   ├── hackernews.py         # HN API
│   │   ├── reddit.py             # Reddit API
│   │   ├── aws_cost.py           # AWS Cost Explorer (opcional)
│   │   └── gcp_billing.py        # GCP Billing (opcional)
│   ├── storage/
│   │   ├── db.py                 # SQLite + FTS5
│   │   └── snapshot.py           # JSON snapshots
│   ├── site/
│   │   ├── builder.py            # Genera sitio estático
│   │   └── templates/            # Jinja2
│   │       ├── base.html
│   │       ├── index.html        # Timeline
│   │       ├── day.html          # Día individual
│   │       ├── search.html       # Búsqueda
│   │       └── tools.html        # Catálogo herramientas
│   ├── web/
│   │   ├── server.py             # FastAPI (modo Docker)
│   │   └── static/               # CSS/JS
│   └── reporters/
│       ├── html_report.py        # HTML single-file
│       └── pdf_report.py         # PDF (Playwright)
└── data/
    ├── finops.db
    ├── snapshots/
    ├── reports/
    └── site/                     # Publicado en Pages
```

---

## 5. Modelo de Datos (SQLite)

```sql
CREATE TABLE sources (
  id TEXT PRIMARY KEY, name TEXT, type TEXT, url TEXT,
  enabled BOOLEAN DEFAULT 1
);

CREATE TABLE items (
  id TEXT PRIMARY KEY, date TEXT, source_id TEXT REFERENCES sources(id),
  title TEXT, url TEXT, summary TEXT, tags TEXT, category TEXT,
  content_raw TEXT, content_parsed TEXT,
  collected_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE tools (
  id TEXT PRIMARY KEY, name TEXT, vendor TEXT, category TEXT,
  cloud TEXT, open_source BOOLEAN, url TEXT, github TEXT,
  description TEXT, discovered_date TEXT, tags TEXT
);

CREATE TABLE runs (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  date TEXT, started_at TIMESTAMP, items_collected INT, status TEXT
);
```

---

## 6. Formatos de Salida

### HTML Diario (single-file, sin dependencias externas)
```
finops-daily-2026-07-08.html
├── Header: fecha, resumen, stats
├── 📰 Noticias del día
├── 🛠️ Nuevas herramientas / productos
├── ☁️ Actualizaciones AWS / GCP / Azure
├── 📚 Blog posts destacados
└── 🔍 Búsqueda rápida (Fuse.js embebido)
```

### Sitio Web Estático (GitHub Pages)
```
https://<user>.github.io/finops-agent/
├── index.html       → Timeline completo
├── day/YYYY-MM-DD/  → Detalle por día
├── search.html      → Búsqueda con Fuse.js
├── tools.html       → Catálogo de herramientas
└── assets/          → CSS + JS
```

### API REST (Modo Docker local)
```
GET  /api/daily?date=YYYY-MM-DD
GET  /api/search?q=<query>
GET  /api/tools
GET  /api/sources
POST /api/collect/now
GET  /api/report/daily
GET  /api/report/daily/pdf
```

---

## 7. Pipeline GitHub Actions

```yaml
name: FinOps Daily Intelligence
on:
  schedule:
    - cron: '30 6 * * *'  # 06:30 UTC
  workflow_dispatch:

jobs:
  collect-and-publish:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with:
          python-version: '3.12'
          cache: 'pip'
      - run: pip install -r requirements.txt
      - run: python src/main.py --daily
      - name: Generate static site
        run: python src/site/builder.py
      - name: Deploy to GitHub Pages
        uses: peaceiris/actions-gh-pages@v3
        with:
          github_token: ${{ secrets.GITHUB_TOKEN }}
          publish_dir: ./data/site
```

---

## 8. Opciones de Despliegue

| Opción | Comando | Ideal para |
|---|---|---|
| GitHub Actions + Pages | `git push` (automatizado) | Gratuito, sin servidor |
| Docker local | `docker compose up -d` | Desarrollo / equipo pequeño |
| VM con cron | `python src/main.py --daily` | Servidor propio |
| Kubernetes CronJob | `kubectl apply -f cronjob.yaml` | Equipos con K8s |
| AWS ECS Fargate | Task + EventBridge | Equipos AWS |

---

## 9. Configuración (`config.yaml`)

```yaml
sources:
  rss:
    - name: "FinOps Foundation Blog"
      url: "https://www.finops.org/blog/feed.xml"
      category: "community"
    - name: "AWS What's New"
      url: "https://aws.amazon.com/about-aws/whats-new/feed/"
      category: "aws"
    - name: "Google Cloud Blog"
      url: "https://cloud.google.com/feeds/cloudblog.xml"
      category: "gcp"
    - name: "Azure Updates"
      url: "https://azure.microsoft.com/en-us/updates/feed/"
      category: "azure"
  api:
    github:
      topics: ["finops", "cloud-cost", "cloud-finops", "finops-tools"]
      min_stars: 5
    hackernews:
      keywords: ["finops", "cloud cost", "kubernetes cost"]
    reddit:
      subreddits: ["FinOps", "cloudcost", "devops"]
storage:
  db_path: "data/finops.db"
  snapshots_dir: "data/snapshots"
  reports_dir: "data/reports"
  site_dir: "data/site"
```

---

## 10. Roadmap de Implementación

### Fase 1 — MVP
- [ ] Estructura del proyecto + Dockerfile + requirements.txt
- [ ] Colector RSS (FinOps Foundation, AWS, GCP, Azure)
- [ ] Colector GitHub API + Hacker News + Reddit
- [ ] SQLite modelo + persistencia
- [ ] HTML single-file diario
- [ ] Generador sitio estático (timeline + búsqueda Fuse.js)
- [ ] Pipeline GitHub Actions + Pages deploy
- [ ] Docker Compose alternativo con FastAPI
- [ ] Catálogo de herramientas + filtros
- [ ] Configurable via config.yaml

### Fase 2 — Post-MVP
- [ ] Cloud APIs (AWS Cost Explorer, GCP Billing, Azure Cost Mgmt)
- [ ] Exportación PDF (Playwright)
- [ ] Dashboard con gráficos (Chart.js)
- [ ] Histórico navegable por mes/año
- [ ] Alertas por keywords (opcional)

---

## 11. Features Clave

| Feature | Implementación |
|---|---|
| Recolección diaria automática | Cron / CI scheduler |
| Histórico navegable por día | SQLite + UI timeline |
| Búsqueda full-text | Fuse.js (estático) / SQLite FTS5 (dinámico) |
| Reportes HTML single-file | Jinja2 template embebido |
| Exportación PDF | Playwright headless |
| Sin dependencia externa de BD | SQLite embebido |
| Portátil | Docker |
| Catálogo de herramientas FinOps | Tabla dedicada + tags |
| Dos modos de despliegue | GitHub Actions (free) + Docker (local) |
