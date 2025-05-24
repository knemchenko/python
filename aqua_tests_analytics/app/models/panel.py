from sqlalchemy import Column, Integer, String
from sqlalchemy.orm import relationship
from app import db

class Panel(db.Model):
    __tablename__ = 'panels'

    id = Column(Integer, primary_key=True, autoincrement=True)
    panel_type = Column(String(128), unique=True, nullable=False)

    versions = relationship('Version', back_populates='panel')

    def __repr__(self):
        return f"<Panel {self.panel_type}>"
