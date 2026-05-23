"""Finding and Severity dataclasses used across the auditor."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional


class Severity(str, Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"

    @property
    def rank(self) -> int:
        return _SEVERITY_RANK[self]

    @classmethod
    def parse(cls, value: str) -> "Severity":
        try:
            return cls(value.lower())
        except ValueError as exc:
            raise ValueError(
                f"unknown severity: {value!r}; expected one of "
                f"{', '.join(s.value for s in cls)}"
            ) from exc

    def __ge__(self, other: object) -> bool:
        if not isinstance(other, Severity):
            return NotImplemented
        return self.rank >= other.rank

    def __gt__(self, other: object) -> bool:
        if not isinstance(other, Severity):
            return NotImplemented
        return self.rank > other.rank

    def __le__(self, other: object) -> bool:
        if not isinstance(other, Severity):
            return NotImplemented
        return self.rank <= other.rank

    def __lt__(self, other: object) -> bool:
        if not isinstance(other, Severity):
            return NotImplemented
        return self.rank < other.rank


_SEVERITY_RANK: Dict[Severity, int] = {
    Severity.LOW: 0,
    Severity.MEDIUM: 1,
    Severity.HIGH: 2,
    Severity.CRITICAL: 3,
}


@dataclass
class Finding:
    """One audit finding pinned to a specific document and field path."""

    rule_id: str
    severity: Severity
    message: str
    file: str
    doc_index: int
    kind: str
    name: str
    namespace: Optional[str] = None
    path: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return {
            "rule_id": self.rule_id,
            "severity": self.severity.value,
            "message": self.message,
            "file": self.file,
            "doc_index": self.doc_index,
            "kind": self.kind,
            "name": self.name,
            "namespace": self.namespace,
            "path": self.path,
        }


@dataclass
class AuditReport:
    """Aggregated result of running the engine over a set of files."""

    findings: List[Finding] = field(default_factory=list)
    files_scanned: int = 0
    documents_scanned: int = 0

    @property
    def counts_by_severity(self) -> Dict[str, int]:
        out = {s.value: 0 for s in Severity}
        for f in self.findings:
            out[f.severity.value] += 1
        return out

    def max_severity(self) -> Optional[Severity]:
        if not self.findings:
            return None
        return max((f.severity for f in self.findings), key=lambda s: s.rank)

    def filter_at_or_above(self, threshold: Severity) -> List[Finding]:
        return [f for f in self.findings if f.severity >= threshold]

    def to_dict(self) -> Dict[str, Any]:
        return {
            "files_scanned": self.files_scanned,
            "documents_scanned": self.documents_scanned,
            "counts_by_severity": self.counts_by_severity,
            "findings": [f.to_dict() for f in self.findings],
        }
