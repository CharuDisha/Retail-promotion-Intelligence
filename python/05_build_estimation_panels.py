"""
Stage 5: Bulk-pull the store-week panels needed for estimation, using the
LOCKED K=10 control assignments from Stage 4.

Input:  config.DB_PATH, config.CONTROL_SETS_CSV
Output: config.MAIN_PANEL_PKL  (campaign_id, store, upc, week, units, margin)
        config.CANN_PANEL_PKL  (campaign_id, week, peer_units)

Two independent pulls, by design (locked Fix 1 — do not merge them):
  - fs_main_panel: treated UPC + its 10 matched control UPCs, at store-week
    grain, for the DiD regression.
  - fs_cann_panel: the SAME-COMMODITY-CODE peer group (excluding the treated
    UPC and anything promoted during the event window), aggregated to one
    category-level series per campaign-week, for the cannibalization metric.
    This is a different, broader set than the DiD control set on purpose —
    using the DiD controls as the cannibalization universe would be circular
    (the controls are selected for high similarity to the treated product,
    which makes them the products MOST likely to be cannibalized).
"""
import duckdb
import pandas as pd

from config import DB_PATH, CONTROL_SETS_CSV, MAIN_PANEL_PKL, CANN_PANEL_PKL, K_PRIMARY, PRE_PERIOD_WEEKS


def main():
    con = duckdb.connect(DB_PATH)

    campaigns = con.execute("""
        SELECT campaign_id, upc AS treated_upc, event_start_week, event_end_week, participating_stores
        FROM campaign_diagnostics WHERE included_v1
    """).fetchdf()
    campaigns["pre_start"] = campaigns["event_start_week"] - PRE_PERIOD_WEEKS

    cs = pd.read_csv(CONTROL_SETS_CSV)
    k10 = cs[cs["variant"] == "K10_primary"].set_index("campaign_id")["control_upcs"]
    campaigns["control_upcs"] = campaigns["campaign_id"].map(k10)

    con.execute("CREATE OR REPLACE TABLE fs_campaigns AS SELECT * FROM campaigns")
    con.execute("""
        CREATE OR REPLACE TABLE fs_campaign_stores AS
        SELECT campaign_id, UNNEST(participating_stores) AS store FROM fs_campaigns
    """)

    # main panel: treated UPC + locked K=10 controls, store-week grain
    con.execute("""
        CREATE OR REPLACE TABLE fs_main_panel AS
        SELECT fcs.campaign_id, s.store, s.upc, s.week, s.units_sold AS units, s.gross_margin_dollars AS margin
        FROM fs_campaign_stores fcs
        JOIN fs_campaigns fc ON fcs.campaign_id = fc.campaign_id
        JOIN stg_sales s ON s.store = fcs.store AND s.week BETWEEN fc.pre_start AND fc.event_end_week
        WHERE s.upc = fc.treated_upc
           OR CONTAINS(',' || fc.control_upcs || ',', ',' || CAST(s.upc AS VARCHAR) || ',')
    """)

    # cannibalization panel: same-commodity-code peer group, aggregated, independent of the DiD control set
    con.execute("""
        CREATE OR REPLACE TABLE fs_cann_panel AS
        SELECT fcs.campaign_id, s.week, SUM(s.units_sold) AS peer_units
        FROM fs_campaign_stores fcs
        JOIN fs_campaigns fc ON fcs.campaign_id = fc.campaign_id
        JOIN stg_sales s ON s.store = fcs.store AND s.week BETWEEN fc.pre_start AND fc.event_end_week
        JOIN stg_products p ON s.upc = p.upc
        JOIN stg_products tp ON tp.upc = fc.treated_upc
        WHERE p.commodity_code = tp.commodity_code
          AND s.upc != fc.treated_upc
          AND s.upc NOT IN (
              SELECT DISTINCT s2.upc FROM stg_sales s2
              WHERE s2.store = fcs.store AND s2.week BETWEEN fc.event_start_week AND fc.event_end_week
                AND s2.is_promo_flagged
          )
        GROUP BY 1,2
    """)

    main_panel = con.execute("SELECT * FROM fs_main_panel").fetchdf()
    cann_panel = con.execute("SELECT * FROM fs_cann_panel").fetchdf()
    con.close()

    main_panel.to_pickle(MAIN_PANEL_PKL)
    cann_panel.to_pickle(CANN_PANEL_PKL)
    campaigns.to_pickle(MAIN_PANEL_PKL.replace("fs_main_panel.pkl", "fs_campaigns.pkl"))

    print(f"fs_main_panel: {len(main_panel):,} rows")
    print(f"fs_cann_panel: {len(cann_panel):,} rows")


if __name__ == "__main__":
    main()