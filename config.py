# yield_agent/config.py

import os

# --- General GCP Configuration ---
PROJECT_ID = os.getenv("PROJECT_ID", "interns-2020")
LOCATION = os.getenv("LOCATION", "us-central1")

# The LLM powering the Agent reasoning
MODEL_NAME = "gemini-3.5-flash"

# ============================================================
# BigQuery Data Tables
# ============================================================
DATASET_ID = "sytheticdata"

# CORRECTED: Pointing to the actual tables in your dataset
TABLE_MASTER_LEDGER = f"{PROJECT_ID}.{DATASET_ID}.unified_live_factory_view"
TABLE_TRAINING_DATA = f"{PROJECT_ID}.{DATASET_ID}.training_data_synthetic"
TABLE_CORRECTIVE_ACTIONS = f"{PROJECT_ID}.{DATASET_ID}.corrective_action_history"

# ============================================================
# GCS Context Files
# ============================================================
ARTIFACTS_BUCKET = f"{PROJECT_ID}_yield_agent_artifacts"
SCHEMA_FILE = "yield_schema.json"
PRODUCT_SEMANTICS_FILE = "yield_products.json"

