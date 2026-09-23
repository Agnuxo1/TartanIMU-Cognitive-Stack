"""JEV-directed multi-agent orchestration package."""

__all__ = ["JEVOrchestrator", "OpportunityAgent", "Opportunity", "ProjectProfile", "JevClient", "JevConnectionError", "create_jev_client", "get_jev_client", "resolve_jev_keys"]


def __getattr__(name: str):
    if name == "JEVOrchestrator":
        from .orchestrator import JEVOrchestrator
        return JEVOrchestrator
    if name in {"OpportunityAgent", "Opportunity", "ProjectProfile"}:
        from .opportunity_agent import OpportunityAgent, Opportunity, ProjectProfile
        return {"OpportunityAgent": OpportunityAgent, "Opportunity": Opportunity, "ProjectProfile": ProjectProfile}[name]
    if name in {"JevClient", "JevConnectionError", "create_jev_client", "get_jev_client", "resolve_jev_keys"}:
        from .connection import JevClient, JevConnectionError, create_jev_client, get_jev_client, resolve_jev_keys
        return locals()[name]
    raise AttributeError(name)
