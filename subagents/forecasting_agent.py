# yield_agent/subagents/forecasting_agent.py

from google.adk.agents import Agent
from tools.yield_tools import predict_lot_yield, get_high_risk_lots, update_all_predictions, get_active_thresholds
from prompts.forecaster_prompts import get_forecaster_instructions
from config import MODEL_NAME

# Aligned exactly with your verified product names!
schema_context = "lot_yield_data(lot_id, product_id, chamber_temperature, chamber_pressure, vibration_level, rework_quantity, target_yield, actual_yield, agent_prediction)"
products_context = "98-XVCD (Target Yield set dynamically), IronWolf Pro 18TB (Target Yield set dynamically)"

# Agent definition
forecasting_agent = Agent(
    model=MODEL_NAME,
    name="forecasting_agent",
    description="Predicts yield for active production lots and identifies lots at risk.",
    instruction=get_forecaster_instructions(
        schema_str=schema_context,
        products_str=products_context
    ),
    tools=[
        predict_lot_yield,
        get_high_risk_lots,
        update_all_predictions,
        get_active_thresholds
    ]
)
