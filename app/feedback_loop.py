import time
import logging

def run_feedback_loop(db, experiment, conversation, ai_client, executor, notifier, max_iterations=10):
    """
    Core feedback loop for iterative AI code generation and execution.

    Roles:
    - User: initial prompt and any additional input
    - AI: generative AI model providing code suggestions
    - Jupyter (Machine): executes code and returns output/errors
    """

    logger = logging.getLogger(__name__)
    experiment.status = 'running'
    _safe_commit(db)

    try:
        from models import Message
        for iteration in range(max_iterations):
            # Fetch conversation history: only User & Jupyter messages
            messages = [
                {"sender": msg.sender, "content": msg.content}
                for msg in db.query(
                    Message
                ).filter_by(experiment_id=experiment.id).all()
            ]

            if iteration == 0 and not messages:
                messages.append({"sender": "user", "content": experiment.prompt})

            # AI generates next code
            original, code, text = ai_client.query(messages)
            conversation.append("system", original)

            # Execute AI code
            execution_result = None
            if code:
                execution_result = executor.execute(code)
                execution_result = "\n".join([
                    "Evaluate the below juypter result from the provided code",
                    "if it address the problem do not return a code but summary message\n",
                    "---- Juypter Result ----",
                    execution_result
                ])
                conversation.append("assistant", execution_result or text)

            _safe_commit(db)

            # Success heuristic
            if not execution_result:
                experiment.status = 'success'
                _safe_commit(db)
                break

            time.sleep(1)
        else:
            experiment.status = 'failed'
            _safe_commit(db)

    except Exception as e:
        logger.exception("Exception in feedback loop")
        conversation.append("system", f"Exception in feedback loop: {str(e)}")
        experiment.status = 'failed'
        _safe_commit(db, rollback_on_fail=True)

    finally:
        executor.shutdown()

        # Send email notification
        from models import Message
        full_convo = "\n\n".join(
            f"{msg.sender}: {msg.content}"
            for msg in db.query(Message).filter_by(experiment_id=experiment.id).all()
        )
        subject = f"Experiment {experiment.id} finished with status: {experiment.status.upper()}"
        body = f"Final status: {experiment.status}\n\nConversation history:\n{full_convo}"
        print(subject, body)
        # notifier(subject=subject, body=body, to_email="user@example.com", smtp_cfg={})


def _safe_commit(db, rollback_on_fail=True):
    try:
        db.commit()
    except Exception as e:
        db.rollback()
        if rollback_on_fail:
            logging.error(f"Commit failed; transaction rolled back: {e}")
        else:
            raise
