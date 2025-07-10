import threading
import uuid
import logging
from typing import Callable

from models import Experiment
from conversation import Conversation
from feedback_loop import run_feedback_loop
from executor import JupyterExecutor
from ai_clients import get_client

# Configure logging
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)

class ExperimentManager:
    """
    Manages the creation and execution of experiments.
    """
    def __init__(self, session_factory: Callable):
        self.session_factory = session_factory
        self.db = self.session_factory()

    def start_experiment(self, prompt: str, ai_choice: str, model: str) -> str:
        """
        Starts a new experiment and returns its ID.
        """
        experiment = Experiment(
            id=str(uuid.uuid4()),
            prompt=prompt,
            ai_client=ai_choice,
            model=model,
            status='pending'
        )
        self.db.add(experiment)
        self.db.commit()

        try:
            conversation = Conversation(self.db, experiment.id)
            ai_client = get_client(ai_choice, model)
            executor = JupyterExecutor()

            thread = threading.Thread(
                target=self._run_in_thread,
                args=(experiment.id, ai_client, executor),
                daemon=True
            )
            thread.start()
        except Exception as e:
            logger.error(f"Error starting experiment {experiment.id}: {str(e)}")
            experiment.status = 'failed'
            self.db.commit()
            with open("experiment_errors.log", "a") as log_file:
                log_file.write(f"Experiment ID: {experiment.id} — Error: {str(e)}\n")
            raise

        return experiment.id

    def _run_in_thread(self, experiment_id: str, ai_client, executor):
        """
        Runs the experiment in a separate thread with a new DB session.
        """
        db = self.session_factory()
        try:
            experiment = db.query(Experiment).get(experiment_id)
            conversation = Conversation(db, experiment_id)
            run_feedback_loop(
                db=db,
                experiment=experiment,
                conversation=conversation,
                ai_client=ai_client,
                executor=executor,
                notifier=lambda subject, body, to_email, smtp_cfg: print(subject, body)
            )
        except Exception as e:
            logger.error(f"Error in thread for experiment {experiment_id}: {str(e)}")
        finally:
            db.close()
            executor.shutdown()