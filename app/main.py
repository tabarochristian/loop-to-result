from fastapi import FastAPI, Request, Form, HTTPException, Depends, WebSocket, WebSocketDisconnect
from fastapi.responses import RedirectResponse
from fastapi.templating import Jinja2Templates
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session
from typing import List, Dict
import asyncio
import json
import logging
from datetime import datetime, timedelta

from experiment_manager import ExperimentManager
from models import Experiment, Message
from db import SessionLocal, get_session

# Configure logging
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(name)s - %(message)s")
logger = logging.getLogger(__name__)

app = FastAPI()
templates = Jinja2Templates(directory="templates")

# WebSocket connections
active_connections: Dict[str, List[WebSocket]] = {}

@app.websocket("/ws/{experiment_id}")
async def websocket_endpoint(websocket: WebSocket, experiment_id: str):
    await websocket.accept()
    if experiment_id not in active_connections:
        active_connections[experiment_id] = []
    active_connections[experiment_id].append(websocket)
    
    # Create a single session for the WebSocket connection
    db = SessionLocal()
    try:
        # Send initial experiment data
        experiment = db.query(Experiment).get(experiment_id)
        if not experiment:
            await websocket.send_json({"event": "deleted"})
            return
        
        last_timestamp = datetime.utcnow() - timedelta(days=1)  # Start with a wide range
        last_status = experiment.status
        
        # Send initial messages
        messages = (
            db.query(Message)
            .filter(Message.experiment_id == experiment_id)
            .order_by(Message.timestamp.asc())
            .all()
        )
        if messages:
            last_timestamp = messages[-1].timestamp
            for message in messages:
                await websocket.send_json({
                    "event": "new_message",
                    "message": {
                        "sender": message.sender,
                        "content": message.content,
                        "timestamp": message.timestamp.isoformat()
                    }
                })
            logger.info(f"Sent {len(messages)} initial messages for experiment {experiment_id}")
        
        while True:
            experiment = db.query(Experiment).get(experiment_id)
            if not experiment:
                await websocket.send_json({"event": "deleted"})
                break
            
            # Check for new messages
            messages = (
                db.query(Message)
                .filter(Message.experiment_id == experiment_id, Message.timestamp > last_timestamp)
                .order_by(Message.timestamp.asc())
                .all()
            )
            if messages:
                last_timestamp = messages[-1].timestamp
                for message in messages:
                    await websocket.send_json({
                        "event": "new_message",
                        "message": {
                            "sender": message.sender,
                            "content": message.content,
                            "timestamp": message.timestamp.isoformat()
                        }
                    })
                logger.info(f"Sent {len(messages)} new messages for experiment {experiment_id}")
            
            # Check for status change
            if experiment.status != last_status:
                last_status = experiment.status
                await websocket.send_json({
                    "event": "status_update",
                    "experiment": {
                        "id": experiment.id,
                        "status": experiment.status,
                        "ai_client": experiment.ai_client,
                        "model": experiment.model
                    }
                })
                logger.info(f"Sent status update ({last_status}) for experiment {experiment_id}")
            
            db.commit()  # Ensure session is fresh
            await asyncio.sleep(1)  # Reduced to 1 second for faster updates
    except WebSocketDisconnect:
        logger.info(f"WebSocket disconnected for experiment {experiment_id}")
    except Exception as e:
        logger.error(f"WebSocket error for experiment {experiment_id}: {str(e)}")
    finally:
        db.close()
        if experiment_id in active_connections and websocket in active_connections[experiment_id]:
            active_connections[experiment_id].remove(websocket)
            if not active_connections[experiment_id]:
                del active_connections[experiment_id]

@app.get("/")
async def index(request: Request, db: Session = Depends(get_session)):
    experiments = db.query(Experiment).order_by(Experiment.created_at.desc()).all()
    return templates.TemplateResponse(
        "index.html",
        {"request": request, "experiments": experiments}
    )

@app.post("/start")
async def start(
    request: Request,
    prompt: str = Form(...),
    model: str = Form(...),
    db: Session = Depends(get_session)
):
    try:
        client, model = model.split(':')
        manager = ExperimentManager(SessionLocal)
        exp_id = manager.start_experiment(prompt, client, model)
        db.commit()
        exp = {}

        exp["id"] = exp_id,
        # Return JSON response with experiment details
        return JSONResponse(status_code=200, content=exp)
    except Exception as e:
        logger.error(f"Error starting experiment: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to start experiment")

@app.get("/progress/{experiment_id}")
async def progress(experiment_id: str, request: Request, db: Session = Depends(get_session)):
    experiment = db.query(Experiment).get(experiment_id)
    if not experiment:
        return RedirectResponse("/", status_code=303)
    
    messages = (
        db.query(Message)
        .filter(Message.experiment_id == experiment_id)
        .order_by(Message.timestamp.asc())
        .all()
    )
    experiments = db.query(Experiment).order_by(Experiment.created_at.desc()).all()
    return templates.TemplateResponse(
        "progress.html",
        {
            "request": request,
            "experiment": experiment,
            "messages": messages,
            "experiments": experiments
        }
    )

@app.post("/progress/{experiment_id}/input")
async def add_input(experiment_id: str, content: str = Form(...), db: Session = Depends(get_session)):
    experiment = db.query(Experiment).get(experiment_id)
    if not experiment or experiment.status not in ["running", "pending"]:
        raise HTTPException(status_code=404, detail="Experiment not found or not active")
    
    message = Message(
        experiment_id=experiment_id,
        sender="user",
        content=content,
        timestamp=datetime.utcnow()
    )
    db.add(message)
    db.commit()
    
    if experiment_id in active_connections:
        for conn in active_connections[experiment_id]:
            await conn.send_json({
                "event": "new_message",
                "message": {
                    "sender": message.sender,
                    "content": message.content,
                    "timestamp": message.timestamp.isoformat()
                }
            })
        logger.info(f"Notified {len(active_connections[experiment_id])} clients of new message for experiment {experiment_id}")
    
    return {"status": "success"}

@app.post("/delete/{experiment_id}")
async def delete_experiment(experiment_id: str, db: Session = Depends(get_session)):
    experiment = db.query(Experiment).get(experiment_id)
    if not experiment:
        return RedirectResponse("/", status_code=303)
    
    experiment.status = "stopped"
    db.commit()
    
    db.query(Message).filter(Message.experiment_id == experiment_id).delete()
    db.delete(experiment)
    db.commit()
    
    if experiment_id in active_connections:
        for conn in active_connections[experiment_id]:
            await conn.send_json({"event": "deleted"})
        logger.info(f"Notified {len(active_connections[experiment_id])} clients of deletion for experiment {experiment_id}")
    
    return RedirectResponse("/", status_code=303)

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)