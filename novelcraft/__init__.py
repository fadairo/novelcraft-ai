"""
NovelCraft AI - An AI-assisted novel writing application.
"""

__version__ = "1.0.0"
__author__ = "NovelCraft Team"
__email__ = "support@novelcraft.ai"

from .core import Document, Character, Project, SnowflakeMethod
from .ai import ClaudeClient, ContentGenerator, StyleAnalyzer
from .editor import ConsistencyChecker, ContinuityTracker

__all__ = [
    "Document",
    "Character", 
    "Project",
    "SnowflakeMethod",
    "ClaudeClient",
    "ContentGenerator",
    "StyleAnalyzer",
    "ConsistencyChecker",
    "ContinuityTracker",
]