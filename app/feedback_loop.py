import time
import logging
from typing import Optional

from models import Message

logger = logging.getLogger(__name__)

def run_feedback_loop(
    db,
    experiment,
    conversation,
    ai_client,
    executor,
    max_iterations: int = 10,
    iteration_delay: float = 1.0
):
    """Core feedback loop for iterative AI code generation and execution."""
    
    experiment.status = 'running'
    _safe_commit(db)

    try:
        for iteration in range(max_iterations):
            if experiment.status == 'stopped':
                logger.info(f"Experiment {experiment.id} stopped by user")
                break

            # Get conversation history
            messages = _get_conversation_history(db, experiment.id, iteration, experiment.prompt)

            # Get AI response
            original, code, text = ai_client.query(messages)
            conversation.append("system", original)

            # Execute code if available
            execution_result = _execute_code(executor, code, conversation) if code else None

            # Check for completion
            if _should_complete(execution_result, iteration, max_iterations):
                experiment.status = 'success'
                _safe_commit(db)
                break

            time.sleep(iteration_delay)
    except Exception as e:
        logger.exception(f"Error in feedback loop for experiment {experiment.id}")
        experiment.status = 'failed'
        conversation.append("system", f"Error: {str(e)}")
        _safe_commit(db, rollback_on_fail=True)
    finally:
        executor.shutdown()

def _get_conversation_history(db, experiment_id: str, iteration: int, prompt: str) -> list:
    """Get conversation history from database."""
    messages = [
        {"sender": msg.sender, "content": msg.content}
        for msg in db.query(Message)
        .filter_by(experiment_id=experiment_id)
        .order_by(Message.id.asc())
        .all()
    ]
    if iteration == 0 and not messages:
        messages.append({"sender": "user", "content": prompt})
    return messages

def _execute_code(executor, code: str, conversation) -> Optional[str]:
    """Execute code and handle results."""
    try:
        execution_result = executor.execute(code)
        if execution_result:
            formatted_result = "\n".join([
                "Jupyter Execution Result:",
                "------------------------",
                execution_result,
                "\nEvaluate the above result. If it solves the problem, provide a summary instead of more code."
            ])
            conversation.append("assistant", formatted_result)
            return formatted_result
    except Exception as e:
        error_msg = f"Execution error: {str(e)}"
        conversation.append("system", error_msg)
        return error_msg
    return None

def _should_complete(execution_result: Optional[str], iteration: int, max_iterations: int) -> bool:
    """Determine if the feedback loop should complete."""
    if not execution_result:
        return True
    if "error" in execution_result.lower():
        return False
    if iteration >= max_iterations - 1:
        return True
    return False

def _safe_commit(db, rollback_on_fail: bool = True):
    """Safely commit database changes with error handling."""
    try:
        db.commit()
    except Exception as e:
        db.rollback()
        if rollback_on_fail:
            logger.error(f"Commit failed; transaction rolled back: {e}")
        else:
            raise