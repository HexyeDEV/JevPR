from __future__ import annotations

from JevPR.github.reviews import ReviewRequest


def build_review_request(reviewers: list[str], approve: bool = False) -> ReviewRequest:
    return ReviewRequest(reviewers=reviewers, approve=approve)