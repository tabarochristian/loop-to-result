import time
import logging
from typing import Callable

from models import Message
from sqlalchemy.sql import func

# Configure logging
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)

def run_feedback_loop(
    db,
    experiment,
    conversation,
    ai_client,
    executor,
    notifier: Callable,
    max_iterations: int = 10
):
    """
    Core feedback loop for iterative AI code generation and execution.
    """
    experiment.status = 'running'
    _safe_commit(db)

    try:
        for iteration in range(max_iterations):
            # Fetch conversation history
            messages = [
                {"sender": msg.sender, "content": msg.content}
                for msg in db.query(Message)
                .filter(Message.experiment_id == experiment.id)
                .order_by(Message.timestamp.asc())
                .all()
            ]

            if iteration == 0 and not messages:
                messages.append({"sender": "user", "content": experiment.prompt})

            # Query AI with history
            original, code, text = ai_client.query(messages)
            conversation.append("system", original)

            # Execute code if present
            execution_result = None
            if code:
                execution_result = executor.execute(code)
                execution_result = "\n".join([
                    "Evaluate the below Jupyter result from the provided code",
                    "If it addresses the problem, return a summary message without code",
                    "---- Jupyter Result ----",
                    execution_result
                ])
                conversation.append("assistant", execution_result or text)

            _safe_commit(db)

            # Check for success
            if not execution_result or "Error" not in execution_result:
                experiment.status = 'success'
                _safe_commit(db)
                break

            # Check for additional user input
            new_messages = db.query(Message).filter(
                Message.experiment_id == experiment.id,
                Message.sender == "user",
                Message.timestamp > func.now() - 60  # Last 60 seconds
            ).all()
            if new_messages:
                logger.info(f"Found {len(new_messages)} new user inputs for experiment {experiment.id}")

            time.sleep(1)
        else:
            experiment.status = 'failed'
            _safe_commit(db)

    except Exception as e:
        logger.exception(f"Exception in feedback loop for experiment {experiment.id}")
        conversation.append("system", f"Exception in feedback loop: {str(e)}")
        experiment.status = 'failed'
        _safe_commit(db, rollback_on_fail=True)

    finally:
        executor.shutdown()
        # Send notification
        full_convo = "\n\n".join(
            f"{msg.sender}: {msg.content}"
            for msg in db.query(Message).filter_by(experiment_id=experiment.id).all()
        )
        subject = f"Experiment {experiment.id} finished with status: {experiment.status.upper()}"
        body = f"Final status: {experiment.status}\n\nConversation history:\n{full_convo}"
        notifier(subject=subject, body=body, to_email="user@example.com", smtp_cfg={})

def _safe_commit(db, rollback_on_fail: bool = True):
    """
    Safely commits database transactions with rollback on failure.
    """
    try:
        db.commit()
    except Exception as e:
        db.rollback()
        logger.error(f"Commit failed; transaction rolled back: {e}")
        if not rollback_on_fail:
            raise