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
    def __init__(self, session_factory):
        self.session_factory = session_factory  # pass the factory, not a session
        self.db = self.session_factory()

    def start_experiment(self, prompt, ai_choice, model):
        experiment = Experiment(
            id=str(uuid.uuid4()),
            prompt=prompt,
            ai_choice=ai_choice,
            model=model,
            status='pending'
        )
        self.db.add(experiment)
        self.db.commit()

        try:
            conversation = Conversation(experiment.id, self.db)
            ai_client = get_client(ai_choice, model)
            executor = JupyterExecutor()

            thread = threading.Thread(
                target=self._run_in_thread,
                args=(experiment.id, ai_client, executor),
                daemon=True
            )
            thread.start()

        except Exception as e:
            print(e)
            experiment.status = 'failed'
            with open("experiment_errors.log", "a") as log_file:
                log_file.write(f"Experiment ID: {experiment.id} — Error: {experiment.status}\n")

        self.db.commit()
        return experiment.id

    def _run_in_thread(self, experiment_id, ai_client, executor):
        # Create a new session for this thread
        db = self.session_factory()
        try:
            experiment = db.query(Experiment).get(experiment_id)
            conversation = Conversation(db, experiment_id)

            run_feedback_loop(
                db,
                experiment,
                conversation,
                ai_client,
                executor,
                send_email
            )
        finally:
            db.close()
