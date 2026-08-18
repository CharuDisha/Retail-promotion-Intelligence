"""
Stage 1: Load raw CSVs into DuckDB and build the staging layer.

Input:  config.WSDR_CSV, config.UPCSDR_CSV, config.WEEK_DECODE_CSV
Output: config.DB_PATH  (tables: raw_wsdr, raw_upcsdr, raw_week_decode,
                          stg_products, dim_week, stg_sales)

Key data-quality fixes applied here (found during pipeline development,
worth keeping as comments so nobody "fixes" them back to the buggy version):

1. upcsdr.csv is not UTF-8 — DuckDB's read_csv_auto needs encoding='latin-1'
   or it throws an invalid-unicode error on product description fields.
2. The SALE column arrives as a true SQL NULL for blank values, not empty
   string. `TRIM(SALE) = ''` silently fails to match NULL, so without
   COALESCE(SALE,'') every blank row gets miscategorized as UNKNOWN_CODE
   instead of NONE — this affects roughly 80% of all rows if missed.
3. Revenue must be computed as PRICE * MOVE / QTY (unbundling multi-packs),
   per the codebook. PRICE * MOVE alone overstates revenue by ~7% on this
   category.
"""
import duckdb

from config import DB_PATH, WSDR_CSV, UPCSDR_CSV, WEEK_DECODE_CSV


def main():
    con = duckdb.connect(DB_PATH)

    # --- raw layer ---
    con.execute(f"""
        CREATE OR REPLACE TABLE raw_wsdr AS
        SELECT * FROM read_csv_auto('{WSDR_CSV}', header=True)
    """)
    con.execute(f"""
        CREATE OR REPLACE TABLE raw_upcsdr AS
        SELECT * FROM read_csv_auto('{UPCSDR_CSV}', encoding='latin-1')
    """)
    con.execute(f"""
        CREATE OR REPLACE TABLE raw_week_decode AS
        SELECT * FROM read_csv_auto('{WEEK_DECODE_CSV}')
    """)

    # --- staging: products ---
    con.execute("""
        CREATE OR REPLACE TABLE stg_products AS
        SELECT
            UPC::BIGINT                                  AS upc,
            COM_CODE::BIGINT                              AS commodity_code,
            TRIM(REPLACE(DESCRIP,'~',''))                 AS product_name,
            (DESCRIP LIKE '~%')                            AS is_discontinued,
            TRIM(SIZE)                                     AS product_size,
            "CASE"::BIGINT                                 AS case_pack
        FROM raw_upcsdr
    """)

    # --- staging: calendar / holiday lookup ---
    con.execute("""
        CREATE OR REPLACE TABLE dim_week AS
        SELECT
            week::INTEGER                                  AS week,
            start_date::DATE                                AS week_start_date,
            end_date::DATE                                  AS week_end_date,
            NULLIF(TRIM(special_event), '')                 AS holiday_flag
        FROM raw_week_decode
    """)

    # --- staging: sales (the core fact grain: store x upc x week) ---
    con.execute("""
        CREATE OR REPLACE TABLE stg_sales AS
        SELECT
            STORE::INTEGER                                 AS store,
            UPC::BIGINT                                     AS upc,
            WEEK::INTEGER                                   AS week,
            MOVE::INTEGER                                   AS units_sold,
            QTY::INTEGER                                    AS bundle_qty,
            PRICE::DOUBLE                                   AS unit_price,
            ROUND(PRICE * MOVE / NULLIF(QTY,0), 2)          AS sales_dollars,
            PROFIT::DOUBLE                                  AS gross_margin_pct,
            ROUND((PRICE * MOVE / NULLIF(QTY,0)) * (PROFIT/100.0), 2) AS gross_margin_dollars,
            CASE
                WHEN TRIM(COALESCE(SALE,'')) IN ('B','S','C') THEN TRIM(SALE)
                WHEN TRIM(COALESCE(SALE,'')) = ''             THEN 'NONE'
                ELSE 'UNKNOWN_CODE'
            END                                              AS promo_code,
            TRIM(COALESCE(SALE,'')) IN ('B','S','C')          AS is_promo_flagged,
            (MOVE > 0 AND PRICE = 0)                          AS price_data_flag
        FROM raw_wsdr
        WHERE OK = 1
    """)

    n_sales = con.execute("SELECT count(*) FROM stg_sales").fetchone()[0]
    n_products = con.execute("SELECT count(*) FROM stg_products").fetchone()[0]
    n_weeks = con.execute("SELECT count(*) FROM dim_week").fetchone()[0]
    print(f"stg_sales: {n_sales:,} rows | stg_products: {n_products:,} | dim_week: {n_weeks:,}")

    con.close()


if __name__ == "__main__":
    main()