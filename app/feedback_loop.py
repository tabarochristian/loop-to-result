import time

def run_feedback_loop(db, experiment, conversation, ai_client, executor, notifier, max_iterations=10):
    """
    Core feedback loop for iterative AI code generation and execution.

    Roles:
    - User: initial prompt and any additional input
    - AI: generative AI model providing code suggestions
    - Machine: executes code and returns output/errors

    Args:
        db: DB session
        experiment: Experiment ORM instance
        conversation: Conversation manager
        ai_client: AIClient instance
        executor: JupyterExecutor instance
        notifier: email sending function
        max_iterations: max number of AI-execute cycles before stopping
    """

    experiment.status = 'running'
    db.commit()

    try:
        for iteration in range(max_iterations):
            # Fetch full conversation history as list of dicts
            # Expected keys: sender, content
            messages = [
                {"sender": msg.sender, "content": msg.content}
                for msg in db.query(conversation.db.query(conversation.db.models.Message).filter_by(experiment_id=experiment.id).statement).all()
            ]

            # If first iteration, seed history with initial prompt from User if no messages yet
            if iteration == 0 and not messages:
                messages.append({"sender": "User", "content": experiment.prompt})

            # AI generates next code snippet or refinement
            ai_response = ai_client.query(messages)
            conversation.append("AI", ai_response)

            # Execute AI code
            execution_result = executor.execute(ai_response)
            conversation.append("Machine", execution_result)

            db.commit()

            # Heuristic to detect success (customize as needed)
            if "success" in execution_result.lower() or "error" not in execution_result.lower():
                experiment.status = 'success'
                db.commit()
                break

            # Sleep briefly to avoid API flooding or kernel overload
            time.sleep(1)
        else:
            experiment.status = 'failed'
            db.commit()
    except Exception as e:
        conversation.append("System", f"Exception in feedback loop: {str(e)}")
        experiment.status = 'failed'
        db.commit()
    finally:
        executor.shutdown()
        # Send email notification with summary
        full_convo = "\n\n".join(
            f"{msg.sender}: {msg.content}" for msg in db.query(conversation.db.query(conversation.db.models.Message).filter_by(experiment_id=experiment.id).statement).all()
        )
        subject = f"Experiment {experiment.id} finished with status: {experiment.status.upper()}"
        body = f"Final status: {experiment.status}\n\nConversation history:\n{full_convo}"
        notifier(subject=subject, body=body, to_email="user@example.com", smtp_cfg={})
