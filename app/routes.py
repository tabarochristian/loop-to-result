from flask import Blueprint, request, jsonify
from .database import SessionLocal
from .models import Experiment, Message
from .conversation import Conversation
from .ai_clients import get_client
from .executor import JupyterExecutor
from .notifier import send_email
from .feedback_loop import run_feedback_loop
import threading
import os

bp = Blueprint("api", __name__, url_prefix="/api")


@bp.route("/experiments", methods=["GET"])
def list_experiments():
    db = SessionLocal()
    experiments = db.query(Experiment).order_by(Experiment.created_at.desc()).all()
    result = [
        {"id": e.id, "status": e.status, "prompt": e.prompt, "ai_client": e.ai_client, "model": e.model}
        for e in experiments
    ]
    db.close()
    return jsonify(result)


@bp.route("/experiments/<int:exp_id>", methods=["GET"])
def get_experiment(exp_id):
    db = SessionLocal()
    experiment = db.query(Experiment).get(exp_id)
    if not experiment:
        db.close()
        return jsonify({"error": "Experiment not found"}), 404

    messages = db.query(Message).filter_by(experiment_id=exp_id).order_by(Message.timestamp).all()
    convo = [
        {"sender": m.sender, "content": m.content, "timestamp": m.timestamp.isoformat()}
        for m in messages
    ]
    result = {
        "id": experiment.id,
        "status": experiment.status,
        "prompt": experiment.prompt,
        "ai_client": experiment.ai_client,
        "model": experiment.model,
        "conversation": convo,
    }
    db.close()
    return jsonify(result)


@bp.route("/experiments", methods=["POST"])
def create_experiment():
    db = SessionLocal()
    data = request.json
    experiment = Experiment(
        prompt=data["prompt"],
        ai_client=data["ai_client"],
        model=data["model"] or "",
        status="pending",
    )
    db.add(experiment)
    db.commit()
    db.refresh(experiment)

    # Create conversation manager
    conversation = Conversation(db, experiment)

    # Instantiate AI client and executor
    ai_client = get_client(data["ai_client"], data["model"])
    executor = JupyterExecutor()

    # SMTP config
    smtp_cfg = {
        "host": os.getenv("SMTP_HOST", "smtp.example.com"),
        "port": int(os.getenv("SMTP_PORT", 587)),
        "username": os.getenv("SMTP_USERNAME", ""),
        "password": os.getenv("SMTP_PASSWORD", ""),
        "use_tls": os.getenv("SMTP_USE_TLS", "true").lower() == "true",
    }

    # Run feedback loop in background thread
    thread = threading.Thread(
        target=run_feedback_loop,
        args=(db, experiment, conversation, ai_client, executor, lambda **kwargs: send_email(**kwargs, smtp_cfg=smtp_cfg)),
        daemon=True,
    )
    thread.start()

    return jsonify({"id": experiment.id})
