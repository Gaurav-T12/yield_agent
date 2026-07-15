# agent.py
try:
    from yield_agent.core import yield_agent as root_agent
except ModuleNotFoundError:
    from core import yield_agent as root_agent

