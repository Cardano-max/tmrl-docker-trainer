"""
Knowledge Package - Layer 2: Knowledge

What the system KNOWS (stored in FalkorDB knowledge graphs).

Components:
- KnowledgeManager: Per-frame knowledge graph (Sutton 15-01-2026)
- FrameRecorder: Records frames from live environment
- MemoryHandler: Short/long term memory
- PriorKnowledgeManager: Prior knowledge detection and loading from disk

Meeting Reference: "FalkorDB is our long term intelligence"
Meeting Reference: "The system should be able to record one node per frame"
Meeting Reference: "when there is previous knowledge... no need to validate anything"
"""

from .knowledge_manager import (
    KnowledgeManager,
    FrameRecorder,
    EpisodeRecorder,
    FrameObservation,
    FrameAction,
    Transition
)
from .memory_handler import MemoryHandler
from .prior_knowledge import PriorKnowledgeManager

__all__ = [
    'KnowledgeManager',
    'FrameRecorder',
    'EpisodeRecorder',
    'FrameObservation',
    'FrameAction',
    'Transition',
    'MemoryHandler',
    'PriorKnowledgeManager',
]
