"""Unified exploration engine package with lazy exports."""

from __future__ import annotations

from importlib import import_module

__all__ = ["ExplorationOrchestrator", "DomRichnessDetector", "detect_dom_richness"]


def __getattr__(name: str):
    if name == "ExplorationOrchestrator":
        return import_module(".orchestrator", __name__).ExplorationOrchestrator
    if name == "DomRichnessDetector":
        return import_module(".browser_use_tools", __name__).DomRichnessDetector
    if name == "detect_dom_richness":
        return import_module(".browser_use_tools", __name__).detect_dom_richness
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
