from __future__ import annotations

from sqlalchemy.orm import Session

from JevPR.db.database import DecisionRecord


class DecisionRepository:
    def __init__(self, session: Session) -> None:
        self.session = session

    def add(self, record: DecisionRecord) -> DecisionRecord:
        self.session.add(record)
        self.session.commit()
        self.session.refresh(record)
        return record