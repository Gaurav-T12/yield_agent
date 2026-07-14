# agent.py
try:
    from yield_agent_main.core import yield_agent as root_agent
except ModuleNotFoundError:
    from core import yield_agent as root_agent

