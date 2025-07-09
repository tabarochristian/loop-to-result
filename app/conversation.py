from models import Message
from datetime import datetime

class Conversation:
    """
    Helper to append messages to DB-backed conversation.
    """
    def __init__(self, db, experiment):
        self.db = db
        self.experiment = experiment

    def append(self, sender, content):
        msg = Message(
            experiment_id=self.experiment.id,
            sender=sender,
            content=content,
            timestamp=datetime.utcnow()
        )
        self.db.add(msg)
        self.db.commit()
