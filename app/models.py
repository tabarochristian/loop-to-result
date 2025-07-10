from sqlalchemy import Column, String, Text, DateTime, Enum, ForeignKey, Integer
from sqlalchemy.orm import declarative_base, relationship
from sqlalchemy.sql import func
from enum import Enum as PyEnum

Base = declarative_base()

class ExperimentStatus(str, PyEnum):
    PENDING = 'pending'
    RUNNING = 'running'
    STOPPED = 'stopped'
    SUCCESS = 'success'
    FAILED = 'failed'

class Experiment(Base):
    __tablename__ = "experiments"

    id = Column(String(36), primary_key=True)  # UUID4
    prompt = Column(Text, nullable=False)
    ai_client = Column(String(50), nullable=False)
    model = Column(String(50), nullable=True)
    status = Column(
        Enum(ExperimentStatus),
        default=ExperimentStatus.PENDING,
        nullable=False
    )
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

    messages = relationship("Message", back_populates="experiment", cascade="all, delete-orphan")

    def __repr__(self):
        return f"<Experiment(id={self.id}, status={self.status}, model={self.model})>"

class Message(Base):
    __tablename__ = "messages"

    id = Column(Integer, primary_key=True, autoincrement=True)
    experiment_id = Column(String(36), ForeignKey("experiments.id"), nullable=False)
    sender = Column(String(20), nullable=False)  # 'user', 'assistant', or 'system'
    content = Column(Text, nullable=False)
    timestamp = Column(DateTime(timezone=True), server_default=func.now())

    experiment = relationship("Experiment", back_populates="messages")

    def __repr__(self):
        return f"<Message(sender={self.sender}, content={self.content[:50]}...)>"