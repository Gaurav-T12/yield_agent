# yield_agent/tools/yield_tools.py

from google.cloud import bigquery
import os
import pandas as pd
from sklearn.ensemble import RandomForestRegressor
from typing import List, Dict, Any
import json

# CORRECTED: Importing the correct table names from the config
from config import PROJECT_ID, TABLE_MASTER_LEDGER, TABLE_TRAINING_DATA, TABLE_CORRECTIVE_ACTIONS

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
    """Calculates ML yield for a lot from the master ledger and saves it back to the table."""
    
    # CORRECTED: Predict on the unified_live_factory_view
    sql = f"""
    SELECT Product_ID, Chamber_Temp_C, Chamber_Pressure_mTorr, Vibration_Level_g,
           COALESCE(Rework_Rate, 0) AS Rework_Rate, 
           COALESCE(Scrap_Rate, 0) AS Scrap_Rate,
           COALESCE(Defect_Count, 0) AS Defect_Count,
           COALESCE(Target_Yield_Pct, 92.0) AS Target_Yield_Pct,
           Agent_Predicted_Yield_Pct
    FROM `{TABLE_MASTER_LEDGER}` WHERE Lot_ID = @lot_id LIMIT 1
    """
    job_config = bigquery.QueryJobConfig(query_parameters=[bigquery.ScalarQueryParameter("lot_id", "STRING", lot_id)])
    
    try:
        df_live = bq_client.query(sql, job_config=job_config).to_dataframe()
        if df_live.empty:
            return {"error": f"Lot {lot_id} not found in the master ledger."}
            
        row = df_live.iloc[0]
        
        # COMMENTED OUT: Local model training and prediction
        # model = _get_trained_model()
        # X_live = df_live[_feature_cols].fillna(0)
        # predicted_yield = round(float(model.predict(X_live)[0]), 1)
        
        # Read the pre-calculated prediction from the database
        predicted_yield = row['Agent_Predicted_Yield_Pct']
        if pd.isna(predicted_yield):
            return {"error": f"No prediction has been pre-computed for Lot {lot_id} yet."}
            
        predicted_yield = round(float(predicted_yield), 1)
        
        # Load dynamic thresholds
        thresholds = get_active_thresholds()
        crit_thresh = thresholds.get("critical_yield_threshold", 82.0)
        high_thresh = thresholds.get("high_risk_yield_threshold", 90.0)
        
        if predicted_yield < crit_thresh:
            risk = "Critical"
        elif predicted_yield < high_thresh:
            risk = "High"
        else:
            risk = "Low"
            
        # COMMENTED OUT: Writing prediction back to database since another model manages it
        # if pd.isna(row['Agent_Predicted_Yield_Pct']) or row['Agent_Predicted_Yield_Pct'] != predicted_yield:
        #      _save_prediction_to_db(lot_id, predicted_yield, risk)
            
        target_yield = float(row['Target_Yield_Pct'])
            
        return {
            "lot_id": lot_id, "product_id": row['Product_ID'],
            "predicted_yield_percent": predicted_yield,
            "target_yield_percent": target_yield,
            "risk_level": risk, "status": "success"
        }
    except Exception as e:
        return {"error": f"Retrieval failed: {str(e)}"}

def _save_prediction_to_db(lot_id: str, prediction: float, risk_level: str):
    """Saves the calculated prediction back into the master ledger."""
    print(f"--- [DATABASE] Saving prediction ({prediction}%) and risk ({risk_level}) for {lot_id} to master ledger ---")
    # CORRECTED: Update the unified_live_factory_view table
    update_sql = f"""
        UPDATE `{TABLE_MASTER_LEDGER}`
        SET Agent_Predicted_Yield_Pct = @prediction,
            Agent_Risk_Level = @risk_level
        WHERE Lot_ID = @lot_id
    """
    job_config = bigquery.QueryJobConfig(
        query_parameters=[
            bigquery.ScalarQueryParameter("prediction", "FLOAT64", prediction),
            bigquery.ScalarQueryParameter("risk_level", "STRING", risk_level),
            bigquery.ScalarQueryParameter("lot_id", "STRING", lot_id)
        ]
    )
    bq_client.query(update_sql, job_config=job_config).result()

def update_all_predictions() -> Dict[str, Any]:
    """Finds all lots in the master ledger missing a prediction and fills them in."""
    print("--- [AUTONOMOUS ENGINE] Scanning master ledger for missing predictions ---")
    # CORRECTED: Scan the unified_live_factory_view
    sql = f"SELECT Lot_ID FROM `{TABLE_MASTER_LEDGER}` WHERE Agent_Predicted_Yield_Pct IS NULL"
    
    try:
        lots = [row['Lot_ID'] for row in bq_client.query(sql)]
        if not lots:
             return {"message": "Scan complete. No lots were found missing predictions.", "status": "success"}

        updated_count = 0
        for lot in lots:
            res = predict_lot_yield(lot)
            if "error" not in res:
                updated_count += 1
        return {"message": f"Successfully predicted and updated {updated_count} of {len(lots)} lots.", "status": "success"}
    except Exception as e:
        return {"error": str(e)}

def get_high_risk_lots() -> Dict[str, Any]:
    """Retrieves the active production lots currently identified as High or Critical risk from the master ledger."""
    print("--- [TOOL] Scanning Master Ledger for High-Risk Lots ---")
    sql = f"""
    SELECT Lot_ID, Product_ID, Target_Yield_Pct, Agent_Predicted_Yield_Pct
    FROM `{TABLE_MASTER_LEDGER}`
    """
    try:
        df = bq_client.query(sql).to_dataframe()
        if df.empty:
            return {"message": "No lots found.", "status": "success", "lots": []}
        
        thresholds = get_active_thresholds()
        crit_thresh = thresholds.get("critical_yield_threshold", 82.0)
        high_thresh = thresholds.get("high_risk_yield_threshold", 90.0)
        
        lots_list = []
        for _, row in df.iterrows():
            pred = row["Agent_Predicted_Yield_Pct"]
            if pd.isna(pred):
                continue
            
            pred_val = float(pred)
            if pred_val < crit_thresh:
                risk = "Critical"
            elif pred_val < high_thresh:
                risk = "High"
            else:
                continue  # Low risk lot
                
            lots_list.append({
                "lot_id": row["Lot_ID"],
                "product_id": row["Product_ID"],
                "target_yield_percent": float(row["Target_Yield_Pct"]) if pd.notna(row["Target_Yield_Pct"]) else 92.0,
                "predicted_yield_percent": pred_val,
                "risk_level": risk
            })
        return {"status": "success", "lots": lots_list}
    except Exception as e:
        return {"error": f"Failed to retrieve high-risk lots: {str(e)}"}


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
