# CSV Analytics Dashboard

A single-user web application for uploading CSV files, exploring datasets, generating descriptive statistics, finding missing values and duplicates, building interactive charts and exporting analysis summaries.

Built with **Flask**, **Pandas** and **Plotly**, with server-rendered Jinja2 pages, plain JavaScript and Bootstrap 5.

## Features

| Area | What you get |
| --- | --- |
| Upload | Drag-and-drop CSV upload (max 50 MB), encoding and delimiter detection (UTF-8/16, CP1252, Latin-1; `,` `;` tab `\|`), three built-in synthetic sample datasets |
| Persistence | Datasets survive restarts: metadata in SQLite, original CSV plus a Parquet copy on disk |
| Explore | Paginated preview (up to 200 rows per page), stable multi-type sorting, per-column value counts |
| Filtering | AND-combined conditions (`eq`, `ne`, `gt`, `gte`, `lt`, `lte`, `between`, `in`, `not_in`, `contains`, `starts_with`, `is_null`, `not_null`) that apply to every page, chart and export |
| Statistics | Numeric (mean, std, quartiles, skew, kurtosis, IQR outliers...), categorical/text (mode, top values, entropy), datetime and boolean summaries; Pearson/Spearman correlations |
| Data quality | Missing values per column, co-missing patterns, exact and case/whitespace-insensitive duplicate detection on all or selected columns |
| Visualize | Histogram, bar, line, scatter, box, pie, correlation heatmap and missing-values charts, rendered with Plotly.js; PNG download |
| Export | Summary CSVs (overview, statistics, missing, duplicates, correlations) and a PDF analysis report with static charts |

## Quick start

### Docker (recommended)

```bash
docker compose up --build
```

Open http://localhost:8000. Data is stored in the `dashboard-data` volume and survives `docker compose down` / `up`. Use `docker compose down -v` to delete it.

A secret key is generated on first start and stored in the volume. To provide your own, set `SECRET_KEY` in a `.env` file next to `docker-compose.yml`. `HOST_PORT` changes the published port.

### Local development

Requires Python 3.12.

```bash
python -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"
cp .env.example .env            # then set SECRET_KEY
flask --app wsgi db upgrade     # create the SQLite schema
flask --app wsgi run --debug    # http://127.0.0.1:5000
```

Regenerate the sample datasets with `python scripts/generate_samples.py`, and a large test file with `python scripts/generate_large_csv.py 500000 large.csv`.

## Configuration

All settings are environment variables (see `.env.example`).

| Variable | Default | Purpose |
| --- | --- | --- |
| `APP_ENV` | `development` | `development`, `testing` or `production` |
| `SECRET_KEY` | dev placeholder | Session/CSRF signing key. **Set this outside development.** |
| `APP_INSTANCE_PATH` | `./instance` | Holds `app.db` and the `data/` directory (`/data` in Docker) |
| `DATABASE_URL` | `sqlite:///<instance>/app.db` | SQLAlchemy URL for metadata |
| `DATA_DIR` | `<instance>/data` | Dataset file storage |
| `MAX_UPLOAD_MB` | `50` | Upload size limit, enforced server-side |
| `MAX_COLUMNS` | `1000` | Maximum columns per CSV |
| `MAX_CELL_LENGTH` | `10000` | Maximum characters per cell |
| `DATAFRAME_CACHE_SIZE` | `3` | Datasets kept in memory per worker |
| `GUNICORN_WORKERS` / `GUNICORN_THREADS` | `2` / `4` | Docker server concurrency |
| `SESSION_COOKIE_SECURE` | `false` | Set `true` when served over HTTPS |

## Architecture

```
app/
  core/        Framework-independent data logic (no Flask imports): ingest, profiling,
               filters, explore, statistics, quality, charts, exports, report
  storage/     File storage (UUID directories, CSV + Parquet) and SQLAlchemy repository
  services/    DatasetService: ties storage, caching and filtering together
  api/         JSON REST API under /api/v1 (Marshmallow-validated parameters)
  web/         HTML page routes
  templates/   Jinja2 templates; static/ holds JS modules, CSS and vendored Bootstrap/Plotly
migrations/    Alembic migrations
scripts/       Sample and large-file generators
tests/         unit, integration, perf (-m slow) and e2e (-m e2e)
```

Charts are built server-side with Plotly and sent as figure JSON. Histograms, bar, box and pie charts are aggregated on the server; scatter plots are randomly sampled and line charts resampled/binned to at most 10,000 points, so full datasets never reach the browser.

## API

All endpoints live under `/api/v1` and return JSON errors as `{"error": {"code", "message", "details"}}`. Endpoints marked *filters* accept a `filters` query parameter containing a JSON list such as `[{"column": "region", "op": "eq", "value": "North"}]`.

| Method | Path | Description |
| --- | --- | --- |
| GET | `/health` | Liveness check |
| GET | `/samples` | List sample datasets |
| POST | `/samples/<key>` | Load a sample dataset |
| GET / POST | `/datasets` | List datasets / upload a CSV (`multipart/form-data`, field `file`, optional `name`) |
| GET / DELETE | `/datasets/<id>` | Dataset metadata / delete dataset and files |
| GET | `/datasets/<id>/columns` | Column schema and kinds |
| GET | `/datasets/<id>/preview` | Paginated rows: `page`, `page_size` (≤ 200), `sort`, `order`; *filters* |
| GET | `/datasets/<id>/columns/<column>/values` | Top value counts: `top`; *filters* |
| GET | `/datasets/<id>/statistics` | Descriptive statistics; *filters* |
| GET | `/datasets/<id>/correlations` | `method=pearson\|spearman`; *filters* |
| GET | `/datasets/<id>/quality/missing` | Missing-value summary; *filters* |
| GET | `/datasets/<id>/quality/duplicates` | `columns`, `normalize`, `max_groups`; *filters* |
| GET | `/datasets/<id>/chart` | `type`, `x`, `y`, `color`, `agg`, `bins`, `top`, `freq`, `method`; *filters* |
| GET | `/datasets/<id>/export/<kind>.csv` | `kind` = `overview`, `statistics`, `missing`, `duplicates`, `correlations`; *filters* |
| GET | `/datasets/<id>/export/report.pdf` | PDF analysis report; *filters* |

State-changing requests (`POST`, `DELETE`) require the CSRF token from the page's `csrf-token` meta tag in an `X-CSRFToken` header.

## Security

- Uploads: server-side size limit, `.csv` extension and content checks (binary/NUL detection, column/header/cell limits), streamed to a staging area and stored under server-generated UUIDs outside `static/`. Original filenames are never used as paths.
- No endpoint returns the raw file or the full dataset; previews are capped at 200 rows and exports contain summaries only.
- Filters use a whitelist of operators applied with Pandas masks, never `DataFrame.query()` or `eval()`.
- CSV exports neutralise spreadsheet formulas (cells starting with `=`, `+`, `-`, `@`, tab or CR).
- CSRF protection on all mutations, strict Content-Security-Policy (no inline scripts, no CDNs), `X-Content-Type-Options`, `X-Frame-Options`/`frame-ancestors`, `Referrer-Policy`, and `no-store` on API responses.
- The Docker image runs as a non-root user with a read-only root filesystem in Compose.
- This version is single-user and has **no authentication**: do not expose it publicly without putting it behind an authenticating proxy.

## Testing

```bash
ruff check . && ruff format --check .   # lint
mypy                                    # type check
pytest --cov=app                        # unit + integration tests
pytest -m slow                          # 500,000-row performance budget
pip install -e ".[e2e]" && playwright install chromium
pytest -m e2e                           # browser end-to-end flow
```

CI runs lint, type checks, tests with coverage, the Playwright flow and a Docker build/health smoke test.

## Performance

Measured on the generated 500,000-row, 15-column (41 MB) file: upload and parse about 2.4 s, statistics about 1.3 s, sorted preview page about 0.15 s, charts 0.05-0.5 s, PDF report about 2.5 s. Repeated requests are served from the in-memory DataFrame cache.

## Limitations

- CSV only (no Excel); single user, no authentication.
- 500,000 rows is a tested target, not a hard limit; memory use grows with dataset size and `DATAFRAME_CACHE_SIZE` × workers.
