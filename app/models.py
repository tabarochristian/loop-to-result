from sqlalchemy import Column, String, Text, DateTime, Enum, ForeignKey, Integer
from sqlalchemy.orm import declarative_base, relationship
from sqlalchemy.sql import func

Base = declarative_base()

class Experiment(Base):
    __tablename__ = "experiments"

    id = Column(String, primary_key=True)  # UUID4
    prompt = Column(Text, nullable=False)
    ai_choice = Column(String, nullable=False)
    model = Column(String, nullable=True)
    status = Column(
        Enum(
            'pending', 'running', 'failed', 'success',
            name='status_enum'
        ),
        default='pending'
    )
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    # relationship to messages
    messages = relationship("Message", back_populates="experiment")


class Message(Base):
    __tablename__ = "messages"

    id = Column(Integer, primary_key=True, autoincrement=True)
    experiment_id = Column(String, ForeignKey("experiments.id"), nullable=False)
    sender = Column(String, nullable=False)  # 'AI' or 'Executor'
    content = Column(Text, nullable=False)

    experiment = relationship("Experiment", back_populates="messages")
