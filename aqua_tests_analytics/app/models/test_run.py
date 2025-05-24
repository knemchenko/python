import enum
from sqlalchemy import Column, Integer, String, DateTime, ForeignKey, Enum, Numeric
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from app import db

class TestStatus(enum.Enum):
    PASS = "pass"
    FAIL = "fail"
    IGNORED = "ignored"
    SKIPPED = "skipped"
    WARNING = "warning"

class TestRun(db.Model):
    __tablename__ = 'test_runs'

    id = Column(Integer, primary_key=True, autoincrement=True)
    version_id = Column(Integer, ForeignKey('versions.id'), nullable=False)
    test_id = Column(String(256), nullable=False)
    class_name = Column(String(256), nullable=True)
    status = Column(Enum(TestStatus), nullable=False)
    duration_seconds = Column(Numeric(10, 3), nullable=True)
    started_ts = Column(DateTime(timezone=True), nullable=True, server_default=func.now())

    version = relationship('Version', back_populates='test_runs')

    def __repr__(self):
        return f"<TestRun {self.test_id} (Version ID: {self.version_id}, Status: {self.status})>"
