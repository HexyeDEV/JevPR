from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Any

from typesafe_sdk import AsyncTypeSafeClient, Noul, Score

from JevPR.decisions.context import PullRequestContext
from JevPR.decisions.models import DecisionEvidence, DecisionResult, FileRisk, RiskSignals
from JevPR.providers.base import DecisionProvider


RISK_SCORE_CRITERIA = [
    "0 - no risk",
    "1 - negligible risk",
    "2 - very low risk",
    "3 - low risk",
    "4 - slightly elevated risk",
    "5 - moderate risk",
    "6 - medium-high risk",
    "7 - high risk",
    "8 - very high risk",
    "9 - critical risk",
]


@dataclass(slots=True)
class JevProvider(DecisionProvider):
    base_url: str | None = None
    api_key: str | None = None

    def __post_init__(self) -> None:
        self.logger = logging.getLogger(__name__)

    def _build_state(self, context: PullRequestContext) -> dict[str, Any]:
        return {
            "pull_request": {
                "title": context.title,
                "base_branch": context.base_branch,
                "head_branch": context.head_branch,
                "labels": context.labels,
                "changed_files": [
                    {
                        "path": file.path,
                        "status": file.status,
                        "additions": file.additions,
                        "deletions": file.deletions,
                        "diff": file.diff,
                    }
                    for file in context.changed_files
                ],
            }
        }

    def _build_questions(
        self, context: PullRequestContext
    ) -> tuple[dict[str, Any], list[tuple[str, str]]]:
        questions: dict[str, Any] = {
            "breaking_api_change": Noul(
                instructions="Is this Pull Request likely to introduce a breaking API change?"
            ),
            "security_sensitive": Noul(
                instructions="Is this Pull Request security-sensitive?"
            ),
            "production_infra_change": Noul(
                instructions="Does this change modify production infrastructure?"
            ),
            "overall_risk": Score(
                instructions="How risky is this Pull Request?",
                criteria=RISK_SCORE_CRITERIA,
            ),
        }
        file_questions: list[tuple[str, str]] = []

        for index, file in enumerate(context.changed_files):
            key = f"file_risk_{index}"
            questions[key] = Score(
                instructions=f"How risky are the changes on file {file.path}?",
                criteria=RISK_SCORE_CRITERIA,
            )
            file_questions.append((key, file.path))

        return questions, file_questions

    @staticmethod
    def _extract_scalar(result_container: Any, key: str, attribute: str) -> float:
        item = result_container[key]
        if hasattr(item, attribute):
            return float(getattr(item, attribute))
        if isinstance(item, dict):
            return float(item.get(attribute, 0.0))
        return float(item)

    async def evaluate(self, context: PullRequestContext) -> DecisionResult:
        state = self._build_state(context)
        questions, file_questions = self._build_questions(context)

        self.logger.info(
            "calling Jev",
            extra={
                "repository": context.repository,
                "number": context.number,
                "changed_files": len(context.changed_files),
                "question_count": len(questions),
            },
        )

        async with AsyncTypeSafeClient() as client:
            response = await client.system_one(state=state, questions=questions)

        self.logger.info(
            "jev response received",
            extra={
                "repository": context.repository,
                "number": context.number,
                "noul_count": len(response.nouls),
                "score_count": len(response.scores),
            },
        )

        nouls = response.nouls
        scores = response.scores

        signals = RiskSignals(
            breaking_api_change=self._extract_scalar(nouls, "breaking_api_change", "noul"),
            security_sensitive=self._extract_scalar(nouls, "security_sensitive", "noul"),
            production_infra_change=self._extract_scalar(
                nouls, "production_infra_change", "noul"
            ),
            model_risk=self._extract_scalar(scores, "overall_risk", "score"),
        )

        file_risks = [
            FileRisk(
                path=file_path,
                score=self._extract_scalar(scores, key, "score"),
                status=file.status,
                additions=file.additions,
                deletions=file.deletions,
                diff=file.diff,
            )
            for (key, file_path), file in zip(file_questions, context.changed_files, strict=True)
        ]

        evidence = [
            DecisionEvidence(key="breaking_api_change", value=signals.breaking_api_change),
            DecisionEvidence(key="security_sensitive", value=signals.security_sensitive),
            DecisionEvidence(
                key="production_infra_change", value=signals.production_infra_change
            ),
            DecisionEvidence(key="overall_risk", value=signals.model_risk),
        ]
        evidence.extend(
            DecisionEvidence(key=file_risk.path, value=file_risk.score)
            for file_risk in file_risks
        )

        self.logger.debug(
            "file risk ranking computed",
            extra={
                "repository": context.repository,
                "number": context.number,
                "top_files": [file_risk.path for file_risk in file_risks[:3]],
            },
        )

        return DecisionResult.from_assessment(
            signals=signals,
            file_risks=file_risks,
            evidence=evidence,
        )