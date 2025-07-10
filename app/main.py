from fastapi import FastAPI, Request, Form
from fastapi.responses import RedirectResponse
from fastapi.templating import Jinja2Templates

from experiment_manager import ExperimentManager
from models import Base, Experiment, Message
from db import SessionLocal, engine

# Initialize DB schema on startup
Base.metadata.create_all(bind=engine)

app = FastAPI()
templates = Jinja2Templates(directory="templates")

@app.get("/")
def index(request: Request):
    """
    Renders the home page with:
    - form to start a new experiment
    - list of all experiments & their statuses (sidebar)
    """
    db = SessionLocal()
    experiments = db.query(Experiment).order_by(Experiment.created_at.desc()).all()
    return templates.TemplateResponse(
        "index.html",
        locals()
    )

@app.post("/start")
def start(
    request: Request,
    prompt: str = Form(...),
    model: str = Form(...)
):
    """
    Starts a new experiment with selected AI & model
    """
    # create session only for this HTTP request
    db = SessionLocal()
    client, model = model.split(':')

    # pass SessionLocal, not db
    manager = ExperimentManager(SessionLocal)

    exp_id = manager.start_experiment(prompt, client, model)

    db.close()  # clean up db used here
    return RedirectResponse(f"/progress/{exp_id}", status_code=303)


@app.get("/progress/{experiment_id}")
def progress(experiment_id: str, request: Request):
    """
    Shows progress of a specific experiment:
    - current status
    - all messages exchanged (AI & executor)
    """
    db = SessionLocal()
    experiment = db.query(Experiment).get(experiment_id)
    if not experiment:
        db.close()
        return RedirectResponse("/", status_code=303)

    messages = (
        db.query(Message)
        .filter(Message.experiment_id == experiment_id)
        .order_by(Message.id.asc())
        .all()
    )
    
    # experiments = db.query(Experiment).order_by(Experiment.created_at.desc()).all()
    db.close()
    return templates.TemplateResponse(
        "progress.html",
        locals()
    )