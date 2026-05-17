"""
models/identity_context.py
──────────────────────────
Scoped identity context for face recognition.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional


class IdentityScopeType(str, Enum):
    SELF    = "self"      # student: match only own embeddings
    SECTION = "section"   # teacher: match only section's enrolled students
    GLOBAL  = "global"    # admin / legacy: full index scan


@dataclass
class ScopeTarget:
    scope_type: IdentityScopeType
    student_ids: List[str] = field(default_factory=list)
    resolved_by: str = ""
    resolved_at: str = ""
    section_id: Optional[str] = None
    period_id: Optional[str] = None


@dataclass
class ScopedMatchResult:
    matched: bool
    student_id: Optional[str]
    student_name: Optional[str]
    confidence: float
    distance: float
    scope: ScopeTarget
    candidates_searched: int
    message: str = ""
    metadata: Dict[str, Any] = field(default_factory=dict)
