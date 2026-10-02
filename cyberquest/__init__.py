"""CyberQuest offline password-strength drill scoring library."""

from .analysis import Analyzer, validate_password
from .dictionary import Dictionary
from .explanation import AnalysisResult, SegmentExplanation, Substitution
from .verify import verify_analysis

__all__ = [
    "Analyzer",
    "AnalysisResult",
    "Dictionary",
    "SegmentExplanation",
    "Substitution",
    "validate_password",
    "verify_analysis",
]

__version__ = "0.1.0"
