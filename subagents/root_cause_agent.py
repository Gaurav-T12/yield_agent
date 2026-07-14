# yield_agent/subagents/root_cause_agent.py

from google.adk.agents import Agent
from tools.yield_tools import get_lot_telemetry, get_active_thresholds
from prompts.root_cause_prompts import get_root_cause_instructions
from config import MODEL_NAME

# UPDATED: Removed supplier_id to match the real schema.
schema_context = "unified_live_factory_view(Lot_ID, Chamber_Temp_C, Chamber_Pressure_mTorr, Vibration_Level_g)"
products_context = "98-XVCD, IronWolf Pro 18TB"

root_cause_agent = Agent(
    model=MODEL_NAME,
    name="root_cause_agent",
    description="Investigates physical sensor telemetry anomalies and explains the root causes of yield degradation.",
    instruction=get_root_cause_instructions(
        schema_str=schema_context,
        products_str=products_context
    ),
    tools=[get_lot_telemetry, get_active_thresholds]
)
