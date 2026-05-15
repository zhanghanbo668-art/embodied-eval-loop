"""Report generation service."""

from .comparison import build_comparison_report
from .gate import run_regression_gate
from .service import build_report

__all__ = ["build_report", "build_comparison_report", "run_regression_gate"]
