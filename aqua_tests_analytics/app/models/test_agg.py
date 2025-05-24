from sqlalchemy import Column, Integer, String, DateTime, ForeignKey, Enum, Numeric, Boolean, PrimaryKeyConstraint
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from app import db
from .test_run import TestStatus  # Import TestStatus enum

class TestAgg(db.Model):
    __tablename__ = 'test_agg'

    version_id = Column(Integer, ForeignKey('versions.id'), primary_key=True)
    test_id = Column(String(256), primary_key=True)
    class_name = Column(String(256), nullable=True) # Added class_name

    last_status = Column(Enum(TestStatus), nullable=True)
    last_started_ts = Column(DateTime(timezone=True), nullable=True)
    passes = Column(Integer, default=0)
    fails = Column(Integer, default=0)
    ignores = Column(Integer, default=0)
    skips = Column(Integer, default=0)
    flips = Column(Integer, default=0)
    t1_transition_rate = Column(Numeric(5, 4), nullable=True)
    t2_fail_after_pass = Column(Numeric(5, 4), nullable=True)
    t3_retry_success = Column(Numeric(5, 4), nullable=True)
    t4_flaky_flag = Column(Boolean, default=False)
    t5_weighted_instab = Column(Numeric(5, 4), nullable=True)
    avg_duration = Column(Numeric(10, 3), nullable=True)
    median_duration = Column(Numeric(10, 3), nullable=True)

    version = relationship('Version', back_populates='test_aggregates')

    __table_args__ = (PrimaryKeyConstraint('version_id', 'test_id'),)

    def __repr__(self):
        return f"<TestAgg test_id={self.test_id} class_name={self.class_name} version_id={self.version_id}>"
