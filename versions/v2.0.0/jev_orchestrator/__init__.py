"""JEV-directed multi-agent orchestration package."""

__all__ = ["JEVOrchestrator", "Thinktank", "ThinktankResult"]


def __getattr__(name: str):
    """Keep lightweight modules runnable with ``python -m`` without import cycles."""
    if name == "JEVOrchestrator":
        from .orchestrator import JEVOrchestrator

        return JEVOrchestrator
    if name in {"Thinktank", "ThinktankResult"}:
        from .thinktank import Thinktank, ThinktankResult

        return {"Thinktank": Thinktank, "ThinktankResult": ThinktankResult}[name]
    raise AttributeError(name)
