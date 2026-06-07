# Cheese — the example dbt + DuckDB project

A small, self-contained dbt project Humbert connects to out of the box:

```bash
humbert connect ./examples/cheese     # builds the DuckDB warehouse, validates, attaches
humbert status                         # shows the connection + health
humbert start                          # boots the runtime
```

It models **cheese production by country, milk source, and year** as a star schema, with one MetricFlow metric (`total_production`).

## Layout

```
seeds/cheese_production.csv   raw input (area, item, year, value_tonnes)
models/staging/               clean-up + the MetricFlow time spine
models/marts/                 the star: fct_cheese_production, dim_country, dim_date, dim_product
models/semantic/cheese.yml    MetricFlow semantic model + the total_production metric
macros/                       generate_schema_name (so layers are named exactly staging/marts)
scripts/derive_seed.py        regenerates the seed from a raw FAOSTAT dump
data/raw/                     where the raw FAOSTAT dump goes (gitignored)
```

## The data

**Source:** FAOSTAT — Crops and livestock products (QCL), <https://www.fao.org/faostat/en/#data/QCL>
**Licence:** CC BY 4.0. Attribute the FAO when you redistribute.
**Scope:** cheese items × (EU-27 + Switzerland, UK, US) × all years, tidied to long form.

> **Heads-up — the committed seed is a small synthetic placeholder**, not official
> FAOSTAT figures. It exists so the example builds and Humbert's pipeline can be
> verified without a 65 MB download. To replace it with the real data, drop the
> raw QCL bulk file into `data/raw/` and run:
>
> ```bash
> uv run --extra dbt python scripts/derive_seed.py
> ```
>
> The raw dumps are gitignored; the derived seed is what's committed, so
> contributors fetch nothing.
