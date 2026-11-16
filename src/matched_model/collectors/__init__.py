"""Benchmark collector registry."""

from matched_model.collectors.aider import AiderCollector
from matched_model.collectors.artificial_analysis import ArtificialAnalysisCollector
from matched_model.collectors.base import BaseCollector, CollectorResult
from matched_model.collectors.deepswe import DeepSWECollector
from matched_model.collectors.livebench import LiveBenchCollector
from matched_model.collectors.lmsys import LMSYSCollector
from matched_model.collectors.swebench import SWEBenchCollector
from matched_model.collectors.terminal_bench import TerminalBenchCollector

ALL_COLLECTORS: list[BaseCollector] = [
    DeepSWECollector(),
    ArtificialAnalysisCollector(),
    SWEBenchCollector(),
    LiveBenchCollector(),
    AiderCollector(),
    TerminalBenchCollector(),
    LMSYSCollector(),
]

__all__ = [
    "ALL_COLLECTORS",
    "BaseCollector",
    "CollectorResult",
    "DeepSWECollector",
    "ArtificialAnalysisCollector",
    "SWEBenchCollector",
    "LiveBenchCollector",
    "AiderCollector",
    "TerminalBenchCollector",
    "LMSYSCollector",
]
