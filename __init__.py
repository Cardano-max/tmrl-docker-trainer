"""
TMRL Docker Trainer - Intelligent Agent Architecture
Based on Dr. Richard Sutton's 3-Layer Design.

Packages:
- core:        Brain capacity layer
- knowledge:   Knowledge layer (FalkorDB graphs, prior knowledge)
- intelligence: Intelligence layer (bin discovery, planning)
- control:     System coordination
- utils:       Exceptions, validators
- adapters:    Environment adapters (TMNF, TM2020)
- config:      Configuration files
- tests:       Validation tests
"""

__version__ = "2.0.0"
