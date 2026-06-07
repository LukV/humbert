"""Derive the committed cheese seed from a raw FAOSTAT QCL dump.

Documentation + regenerability, not run in CI. Drop the raw FAOSTAT
"Production_Crops_Livestock" bulk download into ``examples/cheese/data/raw/``
(gitignored), then run this from the project dir:

    uv run --extra dbt python scripts/derive_seed.py

It filters to cheese items × a curated country set × all years, tidies the wide
year columns to long, and writes ``seeds/cheese_production.csv``.

Source: FAOSTAT, Crops and livestock products (QCL), https://www.fao.org/faostat/en/#data/QCL
Licence: CC BY 4.0 — attribute FAO when redistributing.
"""

from __future__ import annotations

from pathlib import Path

import duckdb

HERE = Path(__file__).resolve().parent.parent
# The Europe regional NOFLAG bulk download. Swap for the global file if needed.
RAW = HERE / "data" / "raw" / "Production_Crops_Livestock_E_Europe_NOFLAG.csv"
OUT = HERE / "seeds" / "cheese_production.csv"

# EU-27 + Switzerland, UK, US. Individual countries only — never FAOSTAT
# aggregate areas ("European Union (27)", "World", etc.).
COUNTRIES = [
    "Austria", "Belgium", "Bulgaria", "Croatia", "Cyprus", "Czechia", "Denmark",
    "Estonia", "Finland", "France", "Germany", "Greece", "Hungary", "Ireland",
    "Italy", "Latvia", "Lithuania", "Luxembourg", "Malta", "Netherlands (Kingdom of the)",
    "Poland", "Portugal", "Romania", "Slovakia", "Slovenia", "Spain", "Sweden",
    "Switzerland", "United Kingdom of Great Britain and Northern Ireland",
    "United States of America",
]


def main() -> None:
    if not RAW.is_file():
        raise SystemExit(
            f"Raw FAOSTAT file not found: {RAW}\n"
            "Download the QCL bulk 'All Data (Normalized)' from "
            "https://www.fao.org/faostat/en/#data/QCL and place it under data/raw/."
        )

    placeholders = ", ".join(["?"] * len(COUNTRIES))
    query = f"""
        SELECT "Area"                               AS area,
               "Item"                               AS item,
               CAST(REPLACE(year_col, 'Y', '') AS INTEGER) AS year,
               CAST(value AS DOUBLE)                AS value_tonnes
        FROM (
            UNPIVOT (SELECT * FROM read_csv(?, header = true, all_varchar = true))
            ON COLUMNS('^Y[0-9]+$')
            INTO NAME year_col VALUE value
        )
        WHERE "Element" = 'Production'
          AND "Unit" = 't'
          AND lower("Item") LIKE '%cheese%'
          -- exclude the "Cheese (All Kinds)" aggregate so milk-source rows don't double-count
          AND lower("Item") NOT LIKE '%all kinds%'
          AND "Area" IN ({placeholders})
          AND value IS NOT NULL AND value <> ''
        ORDER BY area, item, year
    """
    con = duckdb.connect()
    con.execute(query, [str(RAW), *COUNTRIES])
    OUT.parent.mkdir(parents=True, exist_ok=True)
    con.execute(f"COPY ({query.rstrip()}) TO '{OUT}' (HEADER, DELIMITER ',')", [str(RAW), *COUNTRIES])
    rows = con.execute("SELECT count(*) FROM read_csv(?, header = true)", [str(OUT)]).fetchone()
    print(f"Wrote {rows[0] if rows else 0} rows to {OUT}")


if __name__ == "__main__":
    main()
