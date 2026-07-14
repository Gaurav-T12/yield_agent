# yield_agent/core.py

import logging
from google.adk.agents import Agent
from google.adk.apps import App

# Internal Imports
from prompts.yield_agent_prompts import YIELD_AGENT_INSTRUCTION
from subagents.forecasting_agent import forecasting_agent
from subagents.root_cause_agent import root_cause_agent
from subagents.recommender_agent import recommender_agent
from config import MODEL_NAME, PROJECT_ID

# --------------------------------------------------
# 1. DEFINE FUNCTIONAL GUARDRAILS (Security)
# --------------------------------------------------
YIELD_JUDGE_INSTRUCTION = (
    "You are a functional guardrail for the Yield Optimization Agent. "
    "Classify the input:\n"
    "1. SAFE: Related to semiconductor yield, lots, sensors, telemetry, process steps, or suppliers.\n"
    "2. REDIRECT: Related to general sales, office payroll, or marketing campaigns.\n"
    "3. UNSAFE: General coding, roleplay, creative writing, or non-business queries."
)

YIELD_REDIRECT_MSG = (
    "I specialize in Yield Optimization, lot forecasting, and equipment anomaly detection. "
    "For other enterprise questions, please refer to the primary corporate assistant."
)

# --------------------------------------------------
# 2. RUNTIME INITIALIZATION
# --------------------------------------------------
logging.basicConfig(level=logging.INFO)
print("✅ Yield Agent Runtime Initialized - ADK Secure Mode active.")

# --------------------------------------------------
# 3. SUB-AGENT REGISTRATION
# --------------------------------------------------
all_subagents = [
    forecasting_agent,
    root_cause_agent,
    recommender_agent
]

# Reset parent_agent reference to allow dynamic reloading / re-registration
for sa in all_subagents:
    sa.parent_agent = None

# --------------------------------------------------

# 4. MASTER ROOT AGENT SETUP
# --------------------------------------------------
yield_agent = Agent(
    name="yield_agent",
    model=MODEL_NAME,
    description="Main entry point for the AI-Powered Yield Optimization Assistant.",
    instruction=YIELD_AGENT_INSTRUCTION,
    sub_agents=all_subagents
)

yield_app = App(name="yield", root_agent=yield_agent)
if __name__ == "__main__":
    # This launches the built-in ADK CLI emulator
    yield_app.run(run_mode="interactive")
