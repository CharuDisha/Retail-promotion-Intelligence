"""
Shared configuration for the Promotion Incrementality & Margin Optimization pipeline.
Edit the paths below to match your repository layout, then run scripts 00-07 in order.
"""
import os

# --- directories ---
DATA_DIR = "./data/raw"          # wsdr.csv, upcsdr.csv, codebook PDF go here
PROCESSED_DIR = "./data/processed"  # all pipeline outputs land here
DB_PATH = os.path.join(PROCESSED_DIR, "build.duckdb")

os.makedirs(PROCESSED_DIR, exist_ok=True)

# --- source files ---
WSDR_CSV = os.path.join(DATA_DIR, "weekly_sales.csv")
UPCSDR_CSV = os.path.join(DATA_DIR, "products.csv")
CODEBOOK_PDF = os.path.join(DATA_DIR, "Dominicks-Manual-and-Codebook_KiltsCenter.pdf")

# --- pipeline outputs (in dependency order) ---
WEEK_DECODE_CSV = os.path.join(PROCESSED_DIR, "week_decode.csv")
CAMPAIGN_DIAGNOSTICS_CSV = os.path.join(PROCESSED_DIR, "campaign_diagnostics.csv")
CONTROL_AVAILABILITY_CSV = os.path.join(PROCESSED_DIR, "control_product_availability.csv")
CONTROL_SETS_CSV = os.path.join(PROCESSED_DIR, "control_sets.csv")
CONTROL_DIAGNOSTICS_CSV = os.path.join(PROCESSED_DIR, "control_diagnostics.csv")
MAIN_PANEL_PKL = os.path.join(PROCESSED_DIR, "fs_main_panel.pkl")
CANN_PANEL_PKL = os.path.join(PROCESSED_DIR, "fs_cann_panel.pkl")
ESTIMATION_RESULTS_CSV = os.path.join(PROCESSED_DIR, "estimation_results.csv")
FINAL_FACT_CSV = os.path.join(PROCESSED_DIR, "fact_promotion_campaign_effects_v1.csv")

# --- locked identification-quality thresholds (Section 1 of the locked plan) ---
MIN_PARTICIPATING_STORES = 10
MIN_PRE_TREATMENT_WEEKS = 8
MIN_POST_TREATMENT_WEEKS = 8
MIN_CANDIDATE_CONTROL_STORES = 5
MIN_TREATED_STORE_WEEKS = 400

# --- matching (Section 3) ---
PRE_PERIOD_WEEKS = 8      # weeks of pre-treatment history used for matching/pretrend/placebo
K_PRIMARY = 10
K_SENSITIVITY = [5, 20]
LOWCROSS_EXCLUDE_FRACTION = 0.30  # exclude the closest 30% of matches to build the lower-cross-elasticity set

# --- validation / classification (Sections 5, 6, 9) ---
FDR_ALPHA = 0.05
KEEP_CANNIBALIZATION_MAX = 0.20
