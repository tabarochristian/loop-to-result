from fastapi import FastAPI, Request, Form, WebSocket, WebSocketDisconnect
from fastapi.responses import RedirectResponse, HTMLResponse
from fastapi.templating import Jinja2Templates
from fastapi.staticfiles import StaticFiles
import uuid
import json
from typing import List, Dict

from experiment_manager import ExperimentManager
from models import Base, Experiment, Message
from db import SessionLocal, engine, get_db
from websocket_manager import WebSocketManager

# Initialize DB schema on startup
Base.metadata.create_all(bind=engine)

app = FastAPI()
templates = Jinja2Templates(directory="templates")
app.mount("/static", StaticFiles(directory="static"), name="static")

# WebSocket manager for real-time updates
websocket_manager = WebSocketManager()

@app.get("/", response_class=HTMLResponse)
async def index(request: Request):
    """Render the home page with experiment list and creation form."""
    db = SessionLocal()
    try:
        experiments = db.query(Experiment).order_by(Experiment.created_at.desc()).all()
        return templates.TemplateResponse(
            "index.html",
            {"request": request, "experiments": experiments}
        )
    finally:
        db.close()

@app.post("/start")
async def start_experiment(
    request: Request,
    prompt: str = Form(...),
    model: str = Form(...)
):
    """Start a new experiment with selected AI model."""
    db = SessionLocal()
    try:
        client, model_name = model.split(':')
        manager = ExperimentManager(get_db)
        exp_id = manager.start_experiment(prompt, client, model_name)
        return RedirectResponse(f"/experiment/{exp_id}", status_code=303)
    finally:
        db.close()

@app.get("/experiment/{experiment_id}", response_class=HTMLResponse)
async def view_experiment(experiment_id: str, request: Request):
    """View experiment details and progress."""
    db = SessionLocal()
    try:
        experiment = db.query(Experiment).get(experiment_id)
        if not experiment:
            return RedirectResponse("/", status_code=303)

        messages = (
            db.query(Message)
            .filter(Message.experiment_id == experiment_id)
            .order_by(Message.id.asc())
            .all()
        )
        
        return templates.TemplateResponse(
            "experiment.html",
            {
                "request": request,
                "experiment": experiment,
                "messages": messages
            }
        )
    finally:
        db.close()

@app.post("/experiment/{experiment_id}/stop")
async def stop_experiment(experiment_id: str):
    """Stop a running experiment."""
    db = SessionLocal()
    try:
        experiment = db.query(Experiment).get(experiment_id)
        if experiment:
            experiment.status = 'stopped'
            db.commit()
            await websocket_manager.broadcast(
                experiment_id,
                {"type": "status_update", "status": "stopped"}
            )
        return RedirectResponse(f"/experiment/{experiment_id}", status_code=303)
    finally:
        db.close()

@app.post("/experiment/{experiment_id}/delete")
async def delete_experiment(experiment_id: str):
    """Delete an experiment (after stopping it if running)."""
    db = SessionLocal()
    try:
        experiment = db.query(Experiment).get(experiment_id)
        if experiment:
            if experiment.status == 'running':
                experiment.status = 'stopped'
                db.commit()
                await websocket_manager.broadcast(
                    experiment_id,
                    {"type": "status_update", "status": "stopped"}
                )
            db.delete(experiment)
            db.commit()
        return RedirectResponse("/", status_code=303)
    finally:
        db.close()

@app.post("/experiment/{experiment_id}/message")
async def add_message(
    experiment_id: str,
    request: Request,
    message: str = Form(...)
):
    """Add a user message to a running experiment."""
    db = SessionLocal()
    try:
        experiment = db.query(Experiment).get(experiment_id)
        if experiment and experiment.status == 'running':
            msg = Message(
                experiment_id=experiment_id,
                sender="user",
                content=message
            )
            db.add(msg)
            db.commit()
            await websocket_manager.broadcast(
                experiment_id,
                {
                    "type": "new_message",
                    "sender": "user",
                    "content": message,
                    "timestamp": msg.timestamp.isoformat()
                }
            )
        return RedirectResponse(f"/experiment/{experiment_id}", status_code=303)
    finally:
        db.close()

@app.websocket("/ws/{experiment_id}")
async def websocket_endpoint(
    websocket: WebSocket,
    experiment_id: str
):
    """WebSocket endpoint for real-time updates."""
    await websocket.accept()
    websocket_manager.register(experiment_id, websocket)
    
    try:
        while True:
            data = await websocket.receive_text()
            # Handle incoming messages if needed
    except WebSocketDisconnect:
        websocket_manager.unregister(experiment_id, websocket)