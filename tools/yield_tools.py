# yield_agent/tools/yield_tools.py

from google.cloud import bigquery
import os
import pandas as pd
from typing import List, Dict, Any
import json

# CORRECTED: Importing the correct table names from the config
from config import PROJECT_ID, TABLE_MASTER_LEDGER, TABLE_TRAINING_DATA, TABLE_CORRECTIVE_ACTIONS, TABLE_MITIGATION_OPTIONS, TABLE_ALTERNATIVE_INVENTORY, TABLE_PRODUCTION_CAPACITY, TABLE_CARRIER_RATES

# Initialize BigQuery Client explicitly
bq_client = bigquery.Client(project=PROJECT_ID)
print(f"--- [SYSTEM] BigQuery Client initialized for Project: {PROJECT_ID} ---")

def get_active_thresholds() -> Dict[str, float]:
    """Retrieves the active UI slider threshold settings from threshold_config.json."""
    config_path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "threshold_config.json")
    default_thresholds = {
        "critical_yield_threshold": 82.0,
        "high_risk_yield_threshold": 90.0,
        "max_temp": 200.0,
        "max_pressure": 5.0,
        "max_vibration": 0.3,
        "max_rework_rate": 5.0,
        "max_scrap_rate": 2.0
    }
    try:
        if os.path.exists(config_path):
            with open(config_path, "r") as f:
                return json.load(f)
    except Exception as e:
        print(f"Error reading threshold_config.json: {e}")
    return default_thresholds

_trained_model = None
# Features used for training and prediction
_feature_cols = ['Chamber_Temp_C', 'Chamber_Pressure_mTorr', 'Vibration_Level_g', 'Rework_Rate', 'Scrap_Rate', 'Defect_Count']

def _get_trained_model():
    """Trains a Random Forest model on the dedicated training data table."""
    global _trained_model
    if _trained_model is not None:
        return _trained_model

    print(f"--- [SYSTEM] Training ML model on `{TABLE_TRAINING_DATA}` ---")
    
    # CORRECTED: Train on the synthetic training data table
    sql = f"""
    SELECT
      Chamber_Temp_C, Chamber_Pressure_mTorr, Vibration_Level_g,
      COALESCE(Rework_Rate, 0) AS Rework_Rate,
      COALESCE(Scrap_Rate, 0) AS Scrap_Rate,
      COALESCE(Defect_Count, 0) AS Defect_Count,
      Actual_Yield
    FROM
      `{TABLE_TRAINING_DATA}`
    WHERE
      Actual_Yield IS NOT NULL
    """
    df_train = bq_client.query(sql).to_dataframe()
    
    if df_train.empty:
        raise ValueError("No data found in the training table to train the model.")

    X_train = df_train[_feature_cols].fillna(0)
    y_train = df_train['Actual_Yield']
    
    model = RandomForestRegressor(n_estimators=50, random_state=42)
    model.fit(X_train, y_train)
    
    _trained_model = model
    return _trained_model


def predict_lot_yield(lot_id: str) -> Dict[str, Any]:
    """Retrieves pre-calculated prediction and risk from the master ledger once analyzed by Express."""
    sql = f"""
    SELECT Product_ID, Target_Yield_Pct, Agent_Predicted_Yield_Pct, Agent_Risk_Level, Status, Deficit_Units
    FROM `{TABLE_MASTER_LEDGER}` WHERE Lot_ID = @lot_id LIMIT 1
    """
    job_config = bigquery.QueryJobConfig(query_parameters=[bigquery.ScalarQueryParameter("lot_id", "STRING", lot_id)])
    
    try:
        df_live = bq_client.query(sql, job_config=job_config).to_dataframe()
        if df_live.empty:
            return {"error": f"Lot {lot_id} not found in the master ledger."}
            
        row = df_live.iloc[0]
        
        status = row.get('Status')
        if status != 'ANALYZED':
            return {"error": f"Lot {lot_id} has not been analyzed by the Express backend yet (Current Status: {status})."}
            
        predicted_yield = row['Agent_Predicted_Yield_Pct']
        if pd.isna(predicted_yield):
            return {"error": f"No prediction has been pre-computed for Lot {lot_id} yet."}
            
        predicted_yield = round(float(predicted_yield), 1)
        risk = row.get('Agent_Risk_Level', 'Low')
        target_yield = float(row['Target_Yield_Pct']) if pd.notna(row['Target_Yield_Pct']) else 92.0
        deficit_units = int(row['Deficit_Units']) if pd.notna(row['Deficit_Units']) else 0
            
        return {
            "lot_id": lot_id, "product_id": row['Product_ID'],
            "predicted_yield_percent": predicted_yield,
            "target_yield_percent": target_yield,
            "deficit_units": deficit_units,
            "risk_level": risk, "status": "success"
        }
    except Exception as e:
        return {"error": f"Retrieval failed: {str(e)}"}

def get_high_risk_lots() -> Dict[str, Any]:
    """Retrieves the active production lots currently identified as High or Critical risk from the master ledger once analyzed."""
    print("--- [TOOL] Scanning Master Ledger for High-Risk Lots ---")
    sql = f"""
    SELECT Lot_ID, Product_ID, Target_Yield_Pct, Agent_Predicted_Yield_Pct, Agent_Risk_Level
    FROM `{TABLE_MASTER_LEDGER}`
    WHERE Status = 'ANALYZED'
    """
    try:
        df = bq_client.query(sql).to_dataframe()
        if df.empty:
            return {"message": "No analyzed high-risk lots found.", "status": "success", "lots": []}
        
        lots_list = []
        for _, row in df.iterrows():
            risk = row.get("Agent_Risk_Level")
            if risk in ["High", "Critical", "CRITICAL", "HIGH", "MODERATE", "Moderate"]:
                lots_list.append({
                    "lot_id": row["Lot_ID"],
                    "product_id": row["Product_ID"],
                    "target_yield_percent": float(row["Target_Yield_Pct"]) if pd.notna(row["Target_Yield_Pct"]) else 92.0,
                    "predicted_yield_percent": float(row["Agent_Predicted_Yield_Pct"]) if pd.notna(row["Agent_Predicted_Yield_Pct"]) else 0.0,
                    "risk_level": risk
                })
        return {"status": "success", "lots": lots_list}
    except Exception as e:
        return {"error": f"Failed to retrieve high-risk lots: {str(e)}"}

def update_all_predictions() -> Dict[str, str]:
    """Informs the agent that predictions are managed by the unified MLOps pipeline."""
    print("--- [TOOL] update_all_predictions called ---")
    return {"message": "BigQuery Master Ledger predictions are automatically updated by the GCP ML Pipeline schedule."}


def get_lot_telemetry(lot_id: str) -> Dict[str, Any]:
    """Fetches physical sensor telemetry for a lot from the master ledger."""
    print(f"--- [TOOL] Fetching Telemetry for Root Cause on Lot: {lot_id} ---")
    # CORRECTED: Query the unified_live_factory_view
    sql = f"SELECT Chamber_Temp_C, Chamber_Pressure_mTorr, Vibration_Level_g FROM `{TABLE_MASTER_LEDGER}` WHERE Lot_ID = @lot_id LIMIT 1"
    job_config = bigquery.QueryJobConfig(query_parameters=[bigquery.ScalarQueryParameter("lot_id", "STRING", lot_id)])
    try:
        df = bq_client.query(sql, job_config=job_config).to_dataframe()
        if df.empty: return {"error": f"No telemetry found for Lot {lot_id}."}
        return df.iloc[0].to_dict()
    except Exception as e: return {"error": str(e)}

def log_corrective_action(lot_id: str, primary_cause: str, recommendation: str, priority: str) -> Dict[str, Any]:
    import uuid; from datetime import datetime
    print(f"--- [TOOL] Logging Corrective Action for Lot: {lot_id} ---")
    action_id = f"ACT-{uuid.uuid4().hex[:6].upper()}"
    row = {"Action_ID": action_id, "Timestamp": datetime.utcnow().isoformat(), "Lot_ID": lot_id, "Primary_Root_Cause": primary_cause, "Recommended_Mitigation": f"[{priority}] {recommendation}", "Execution_Status": "PENDING", "Execution_Type": "MANUAL"}
    try:
        errors = bq_client.insert_rows_json(TABLE_CORRECTIVE_ACTIONS, [row])
        if not errors: return {"status": "success", "action_id": action_id}
        else: return {"error": str(errors)}
    except Exception as e: return {"status": "simulated_success", "message": f"Simulated logging: {recommendation}"}

def get_mitigation_options() -> List[Dict[str, Any]]:
    """Retrieves the master catalog of solution mitigation options."""
    print("--- [TOOL] Fetching Mitigation Options Catalog ---")
    sql = f"SELECT Option_ID, Action_Name, Description, Time_Impact_Days, Fill_Rate_Pct, Feasibility_Score, Base_Cost_Per_Unit_USD, Fixed_Execution_Cost_USD FROM `{TABLE_MITIGATION_OPTIONS}`"
    try:
        df = bq_client.query(sql).to_dataframe()
        return df.to_dict(orient="records")
    except Exception as e:
        print(f"Error fetching mitigation options: {e}")
        return []

def get_alternative_inventory(product_id: str) -> List[Dict[str, Any]]:
    """Fetches alternative warehouse stock levels for a given Product_ID."""
    print(f"--- [TOOL] Fetching Alternative Warehouse Inventory for Product: {product_id} ---")
    sql = f"SELECT Warehouse_ID, Product_ID, Quantity_Available, Distance_KM, Transfer_Time_Days, Transfer_Cost_Per_Unit FROM `{TABLE_ALTERNATIVE_INVENTORY}` WHERE Product_ID = @product_id"
    job_config = bigquery.QueryJobConfig(query_parameters=[bigquery.ScalarQueryParameter("product_id", "STRING", product_id)])
    try:
        df = bq_client.query(sql, job_config=job_config).to_dataframe()
        return df.to_dict(orient="records")
    except Exception as e:
        print(f"Error fetching alternative inventory: {e}")
        return []

def get_production_capacity() -> List[Dict[str, Any]]:
    """Fetches line capacity, lead times, and overtime labor costs."""
    print("--- [TOOL] Fetching Production Capacity and Labor Costs ---")
    sql = f"SELECT Site_ID, Line_Capacity_Remaining, Standard_Lead_Time_Days, Overtime_Capacity_Available, Overtime_Cost_Per_Unit FROM `{TABLE_PRODUCTION_CAPACITY}`"
    try:
        df = bq_client.query(sql).to_dataframe()
        return df.to_dict(orient="records")
    except Exception as e:
        print(f"Error fetching production capacity: {e}")
        return []

def get_carrier_rates() -> List[Dict[str, Any]]:
    """Fetches carrier service tiers, transit times, rates, and reliability stats."""
    print("--- [TOOL] Fetching Logistics Carrier Rates ---")
    sql = f"SELECT Carrier_ID, Service_Tier, Transit_Time_Days, Base_Rate_Per_KG, Reliability_Rate FROM `{TABLE_CARRIER_RATES}`"
    try:
        df = bq_client.query(sql).to_dataframe()
        return df.to_dict(orient="records")
    except Exception as e:
        print(f"Error fetching carrier rates: {e}")
        return []
