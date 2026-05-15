"""Report generation service."""

from .comparison import build_comparison_report
from .dataset_card import build_dataset_card
from .gate import run_regression_gate
from .service import build_report

__all__ = ["build_report", "build_comparison_report", "run_regression_gate", "build_dataset_card"]
