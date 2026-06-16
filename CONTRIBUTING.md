# Contributing to AlphaForge

AlphaForge is split across two repositories, plus a clean internal split between
the analytics core and the service layer. Knowing where a change belongs is the
main thing to get right.

## Two repositories

| repo | owns | you touch it when |
|------|------|-------------------|
| **AlphaForge** (this repo) | the analytics core (`src/alphaforge`) and the API (`src/alphaforge_api`) | adding factors, data sources, metrics, validation, or API endpoints |
| **MarketDNA_DB** | all database schema and migrations (`supabase/migrations`) | changing tables, row-level security, or storage buckets |

The database lives in its own repo so it can evolve (and new services can be
added) without touching the application. The API connects to it over the network
via env vars and never defines schema.

## The dependency rule

The arrow only ever points **api -> core**. The core (`alphaforge`) must never
import anything from `alphaforge_api`, web frameworks, Supabase, or Redis. This is
what lets analytics contributors work without ever seeing the service layer.

- Pure analytics work: stay in `src/alphaforge`. Install `pip install -e ".[engine]"`.
- Service work (endpoints, worker, persistence): `src/alphaforge_api`. Install `pip install -e ".[api]"`.

If you find yourself wanting to import a web or database thing into the core,
that logic belongs in the API layer instead.

## Where things go

| change | location |
|--------|----------|
| new factor | `src/alphaforge/factors/` (register with `@register_factor`) |
| new price/fundamentals source | `src/alphaforge/data/` or `src/alphaforge/fundamentals/` (implement the provider interface) |
| new metric | `src/alphaforge/metrics/` |
| new API endpoint | `src/alphaforge_api/routes/` |
| background job logic | `src/alphaforge_api/worker.py` |
| table / RLS / bucket change | **MarketDNA_DB** `supabase/migrations/` (new migration) |

## Local development

```bash
# core only (analytics contributors)
pip install -e ".[engine,dev]"
pytest

# full service stack
pip install -e ".[api,engine,dev]"
```

## Conventions

- Factors return scores where higher = more attractive and use only trailing
  data (no lookahead). The engine and tests enforce this.
- Run `ruff check` and `pytest` before opening a PR. API tests mock Supabase and
  Redis, so the suite runs offline.
- Keep the core free of network/database imports.
