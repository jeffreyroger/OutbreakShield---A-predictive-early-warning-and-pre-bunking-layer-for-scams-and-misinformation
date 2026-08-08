"""FastAPI app — binds 127.0.0.1 by default (NFR-3.3). See SRS §4.1 for the API
table this file implements 1:1.

Run: uvicorn src.api.main:app --host 127.0.0.1 --port 8000
"""
from __future__ import annotations

from datetime import datetime, timezone

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel

from src.db import repository as repo
from src.stage1_surveillance.replay import get_clock
from src.stage2_lineage.tree import build_forest
from src.stage3_rt.backtest import run_backtest
from src.stage5_publisher import service

app = FastAPI(title="OutbreakShield API", version="0.1.0")


class InitRequest(BaseModel):
    auto_publish: bool | None = None


class SeekRequest(BaseModel):
    timestamp: str


@app.get("/status")
def get_status():
    """FR-5.9: loop running state, mode, simulated date, compression ratio,
    lineage count, escalating lineage count, posts published."""
    return service.get_status()


@app.post("/init")
def post_init(body: InitRequest | None = None):
    """FR-5.1, FR-5.2: starts the autonomous loop, idempotently."""
    auto_publish = body.auto_publish if body else None
    return service.init_loop(auto_publish=auto_publish)


@app.get("/feed")
def get_feed(limit: int | None = None, since: str | None = None):
    """FR-5.3, FR-5.6: published posts, newest-first."""
    return {"posts": service.get_feed(limit=limit, since=since)}


@app.get("/lineages")
def get_lineages():
    """FR-2.6: full lineage forest as nested JSON."""
    return {"lineages": build_forest()}


@app.get("/lineages/{variant_id}/rt")
def get_lineage_rt(variant_id: str):
    """FR-3.3: Rt series with credible interval for one lineage."""
    lineage = repo.get_lineage(variant_id)
    if lineage is None:
        raise HTTPException(status_code=404, detail="lineage not found")
    return {"variant_id": variant_id, "series": repo.get_rt_series(variant_id)}


@app.get("/backtest")
def get_backtest():
    """FR-3.10: per-wave lead time, aggregate coverage, false-alarm count."""
    return run_backtest()


@app.get("/trace")
def get_trace(limit: int = 100):
    """FR-6.2: recent agent decision trace events."""
    return {"events": repo.get_recent_traces(limit=limit)}


@app.get("/review")
def get_review_queue():
    """FR-5.7: pending posts in review mode."""
    return {"posts": service.get_review_queue()}


@app.post("/review/{post_id}/approve")
def approve_post(post_id: str):
    result = service.approve_post(post_id)
    if not result["ok"] and result["reason"] == "not_found":
        raise HTTPException(status_code=404, detail="post not found")
    return result


@app.post("/review/{post_id}/reject")
def reject_post(post_id: str):
    result = service.reject_post(post_id)
    if not result["ok"] and result["reason"] == "not_found":
        raise HTTPException(status_code=404, detail="post not found")
    return result


@app.post("/replay/pause")
def replay_pause():
    get_clock().pause()
    return get_clock().get_status()


@app.post("/replay/resume")
def replay_resume():
    get_clock().resume()
    return get_clock().get_status()


@app.post("/replay/seek")
def replay_seek(body: SeekRequest):
    ts = body.timestamp.replace("Z", "+00:00")
    try:
        target = datetime.fromisoformat(ts).astimezone(timezone.utc)
    except ValueError:
        raise HTTPException(status_code=400, detail="timestamp must be ISO 8601")
    get_clock().seek(target)
    return get_clock().get_status()
