# yield_agent/subagents/recommender_agent.py

from google.adk.agents import Agent
from tools.yield_tools import log_corrective_action, get_mitigation_options, get_alternative_inventory, get_production_capacity, get_carrier_rates
from prompts.recommender_prompts import get_recommender_instructions
from config import MODEL_NAME

# Agent definition
recommender_agent = Agent(
    model=MODEL_NAME,
    name="recommender_agent",
    description="Generates prescriptive corrective actions and logs them in the tracking database.",
    instruction=get_recommender_instructions(),
    tools=[log_corrective_action, get_mitigation_options, get_alternative_inventory, get_production_capacity, get_carrier_rates]
)
