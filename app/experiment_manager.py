import threading
import uuid

from models import Experiment
from conversation import Conversation
from feedback_loop import run_feedback_loop
from executor import JupyterExecutor
from ai_clients import get_client
from notifier import send_email


class ExperimentManager:
    """
    Responsible for creating and starting experiments
    """
    def __init__(self, db):
        self.db = db

    def start_experiment(self, prompt, ai_choice, model):
        # Create new Experiment record
        experiment = Experiment(
            id=str(uuid.uuid4()),
            prompt=prompt,
            ai_choice=ai_choice,
            model=model,
            status='pending'
        )
        self.db.add(experiment)
        self.db.commit()

        # Set up supporting components
        conversation = Conversation(experiment.id, self.db)
        executor = JupyterExecutor()
        ai_client = get_client(ai_choice, model)

        # Start feedback loop in background thread
        thread = threading.Thread(
            target=run_feedback_loop,
            args=(self.db, experiment, conversation, ai_client, executor, send_email),
            daemon=True
        )
        thread.start()

        return experiment.id
