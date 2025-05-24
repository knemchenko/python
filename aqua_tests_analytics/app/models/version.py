from sqlalchemy import Column, Integer, String, DateTime, ForeignKey, UniqueConstraint
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from app import db

class Version(db.Model):
    __tablename__ = 'versions'

    id = Column(Integer, primary_key=True, autoincrement=True)
    panel_id = Column(Integer, ForeignKey('panels.id'), nullable=False)
    version = Column(String(128), nullable=False)
    created_ts = Column(DateTime(timezone=True), server_default=func.now())

    panel = relationship('Panel', back_populates='versions')
    test_runs = relationship('TestRun', back_populates='version')
    test_aggregates = relationship('TestAgg', back_populates='version')

    __table_args__ = (UniqueConstraint('panel_id', 'version', name='uq_panel_version'),)

    def __repr__(self):
        return f"<Version {self.version} (Panel ID: {self.panel_id})>"
