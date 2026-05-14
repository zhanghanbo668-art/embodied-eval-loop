"""Report generation service."""

from .comparison import build_comparison_report
from .service import build_report

__all__ = ["build_report", "build_comparison_report"]
