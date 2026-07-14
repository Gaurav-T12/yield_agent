import sys
import os
from google.cloud import bigquery

sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from core import yield_agent
from config import PROJECT_ID, TABLE_MASTER_LEDGER

def run_batch_recommendations():
    print("--- [BATCH RECOMMENDATIONS] Initiating Agentic Mitigation Evaluation ---")
    bq_client = bigquery.Client(project=PROJECT_ID)
    
    # Query lots in master ledger with MODERATE or CRITICAL severity
    sql = f"""
        SELECT Lot_ID, Product_ID, Agent_Risk_Level, Recommended_Mitigation
        FROM `{TABLE_MASTER_LEDGER}`
        WHERE Status = 'ANALYZED' 
          AND Agent_Risk_Level IN ('CRITICAL', 'MODERATE', 'HIGH', 'Medium', 'Critical', 'Moderate')
    """
    try:
        df = bq_client.query(sql).to_dataframe()
        if df.empty:
            print("No lots found requiring mitigation recommendations.")
            return
        
        print(f"Found {len(df)} lots needing mitigation evaluations.")
        for _, row in df.iterrows():
            lot_id = row['Lot_ID']
            product_id = row['Product_ID']
            risk = row['Agent_Risk_Level']
            existing_mitigation = row.get('Recommended_Mitigation')
            
            # Avoid duplicate evaluations if recommendation is already written
            if existing_mitigation and existing_mitigation != "-":
                print(f"Skipping Lot {lot_id} (already has recommendation: {existing_mitigation})")
                continue
                
            print(f"Evaluating Lot {lot_id} (Product: {product_id}, Risk: {risk})...")
            
            # Run the agent turn to evaluate and log
            prompt = f"Perform mitigation evaluation for Lot {lot_id} (Product {product_id}, Risk {risk}). Retrieve all necessary options, inventory, capacity, and rate details. Select the optimal mitigation and log the action."
            response = yield_agent.run(prompt)
            print(f"Agent response for {lot_id}: {response}")
            
    except Exception as e:
        print(f"Batch recommendation run failed: {e}")

if __name__ == "__main__":
    run_batch_recommendations()
