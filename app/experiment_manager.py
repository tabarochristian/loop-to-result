import threading
import uuid
import logging
from typing import Callable

from models import Experiment
from conversation import Conversation
from feedback_loop import run_feedback_loop
from executor import JupyterExecutor
from ai_clients import get_client

logger = logging.getLogger(__name__)

class ExperimentManager:
    """Manages experiment lifecycle including creation, execution, and monitoring."""
    
    def __init__(self, session_factory: Callable):
        self.session_factory = session_factory

    def start_experiment(self, prompt: str, ai_choice: str, model: str) -> str:
        """Start a new experiment with the given parameters."""
        db = self.session_factory()
        try:
            experiment = Experiment(
                id=str(uuid.uuid4()),
                prompt=prompt,
                ai_choice=ai_choice,
                model=model,
                status='pending'
            )
            db.add(experiment)
            db.commit()

            # Start execution in a separate thread
            thread = threading.Thread(
                target=self._run_experiment,
                args=(experiment.id,),
                daemon=True
            )
            thread.start()

            return experiment.id
        except Exception as e:
            logger.error(f"Failed to start experiment: {e}")
            db.rollback()
            raise
        finally:
            db.close()

    def _run_experiment(self, experiment_id: str):
        """Run the experiment in a background thread."""
        db = self.session_factory()
        try:
            experiment = db.query(Experiment).get(experiment_id)
            if not experiment:
                logger.error(f"Experiment {experiment_id} not found")
                return

            conversation = Conversation(db, experiment_id)
            ai_client = get_client(experiment.ai_choice, experiment.model)
            executor = JupyterExecutor()

            run_feedback_loop(
                db=db,
                experiment=experiment,
                conversation=conversation,
                ai_client=ai_client,
                executor=executor
            )
        except Exception as e:
            logger.error(f"Error in experiment {experiment_id}: {e}")
            if experiment:
                experiment.status = 'failed'
                db.commit()
        finally:
            executor.shutdown()
            db.close()