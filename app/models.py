from sqlalchemy import Column, String, Text, DateTime, Enum, ForeignKey, Integer
from sqlalchemy.orm import declarative_base, relationship
from sqlalchemy.sql import func

Base = declarative_base()

class Experiment(Base):
    __tablename__ = "experiments"

    id = Column(String, primary_key=True)  # UUID4
    prompt = Column(Text, nullable=False)
    ai_client = Column(String, nullable=False)  # Renamed from ai_choice for clarity
    model = Column(String, nullable=True)
    status = Column(
        Enum(
            'pending', 'running', 'failed', 'success', 'stopped',
            name='status_enum'
        ),
        default='pending'
    )
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    timestamp = Column(DateTime(timezone=True), server_default=func.now())  # Added for messages

    messages = relationship("Message", back_populates="experiment")

class Message(Base):
    __tablename__ = "messages"

    id = Column(Integer, primary_key=True, autoincrement=True)
    experiment_id = Column(String, ForeignKey("experiments.id"), nullable=False)
    sender = Column(String, nullable=False)
    content = Column(Text, nullable=False)
    timestamp = Column(DateTime(timezone=True), server_default=func.now())

    experiment = relationship("Experiment", back_populates="messages")