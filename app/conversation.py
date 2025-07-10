from sqlalchemy.sql import func
from models import Message

class Conversation:
    """
    Helper class to manage database-backed conversation messages.
    """
    def __init__(self, db, experiment_id: str):
        self.db = db
        self.experiment_id = experiment_id

    def append(self, sender: str, content: str):
        """
        Appends a message to the conversation.
        """
        msg = Message(
            experiment_id=self.experiment_id,
            sender=sender,
            content=content,
            timestamp=func.now()
        )
        self.db.add(msg)
        self.db.commit()