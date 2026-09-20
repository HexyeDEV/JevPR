from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum
from typing import Iterable


class DecisionLevel(StrEnum):
    LOW = "LOW"
    NORMAL = "NORMAL"
    SPECIALIST = "SPECIALIST"

    @classmethod
    def from_score(cls, score: float) -> "DecisionLevel":
        if score < 3.5:
            return cls.LOW
        if score < 7.0:
            return cls.NORMAL
        return cls.SPECIALIST


@dataclass(slots=True)
class DecisionEvidence:
    key: str
    value: float | str


@dataclass(slots=True)
class RiskSignals:
    breaking_api_change: float
    security_sensitive: float
    production_infra_change: float
    model_risk: float


@dataclass(slots=True)
class FileRisk:
    path: str
    score: float
    status: str = "modified"
    additions: int = 0
    deletions: int = 0
    diff: str | None = None


def _clamp(value: float, lower: float, upper: float) -> float:
    return max(lower, min(upper, value))


def _weighted_file_score(file_risks: Iterable[FileRisk]) -> float:
    top_scores = sorted((risk.score for risk in file_risks), reverse=True)[:3]
    if not top_scores:
        return 0.0

    weights = [0.5, 0.3, 0.2]
    total_weight = sum(weights[index] for index in range(len(top_scores)))
    weighted_total = sum(score * weights[index] for index, score in enumerate(top_scores))
    return weighted_total / total_weight


@dataclass(slots=True)
class DecisionResult:
    signals: RiskSignals
    computed_risk: float
    file_risks: list[FileRisk] = field(default_factory=list)
    summary: str = ""
    evidence: list[DecisionEvidence] = field(default_factory=list)

    @classmethod
    def from_assessment(
        cls,
        *,
        signals: RiskSignals,
        file_risks: list[FileRisk],
        evidence: list[DecisionEvidence] | None = None,
    ) -> "DecisionResult":
        signal_risk = 10.0 * (
            0.45 * signals.breaking_api_change
            + 0.35 * signals.security_sensitive
            + 0.20 * signals.production_infra_change
        )
        file_risk = _weighted_file_score(file_risks)
        computed_risk = _clamp(
            0.45 * signals.model_risk + 0.35 * signal_risk + 0.20 * file_risk,
            0.0,
            10.0,
        )

        most_risky = sorted(
            file_risks, key=lambda file_risk_item: file_risk_item.score, reverse=True
        )[:3]
        if most_risky:
            files_summary = ", ".join(
                f"{file_risk.path} ({file_risk.score:.1f}/10)" for file_risk in most_risky
            )
        else:
            files_summary = "no file-level hotspots"

        summary = (
            f"Composite risk {computed_risk:.2f}/10 derived from model risk "
            f"{signals.model_risk:.2f}/10, signal risk {signal_risk:.2f}/10, and "
            f"file risk {file_risk:.2f}/10. Most risky files: {files_summary}."
        )

        return cls(
            signals=signals,
            computed_risk=computed_risk,
            file_risks=sorted(
                file_risks, key=lambda file_risk_item: file_risk_item.score, reverse=True
            ),
            summary=summary,
            evidence=evidence or [],
        )

    @property
    def level(self) -> DecisionLevel:
        return DecisionLevel.from_score(self.computed_risk)

    def top_risky_files(self, limit: int = 3) -> list[FileRisk]:
        return self.file_risks[:limit]