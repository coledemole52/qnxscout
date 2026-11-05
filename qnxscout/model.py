from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Optional


@dataclass
class Finding:
    rule: str
    severity: str
    file: str
    line: int
    message: str
    snippet: str = ""
    confidence: str = "high"      # high: QNX definitely compiles this line; medium: depends on build config
    symbol: str = ""
    in_tests: bool = False
    note: str = ""

    def key(self):
        return (self.rule, self.file, self.line, self.symbol)

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass
class ScanResult:
    root: str
    files_scanned: int = 0
    c_files: int = 0
    build_files: int = 0
    findings: list = field(default_factory=list)
    provided: dict = field(default_factory=dict)       # symbol -> where the project defines it
    build_systems: list = field(default_factory=list)
    score: Optional[dict] = None
    duration_s: float = 0.0
    sdp: Optional[str] = None
    uses: dict = field(default_factory=dict)          # library -> project calls its API
