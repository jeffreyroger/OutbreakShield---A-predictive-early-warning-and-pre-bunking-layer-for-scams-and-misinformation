"""Thin service layer the API routes call into (keeps src/api/main.py free of
business logic). FR-5.9's `/status` fields are assembled here.
"""
from __future__ import annotations

from src.db import repository as repo
from src.stage3_rt.ranking import get_escalating_lineages
from src.stage5_publisher.loop import get_loop


def init_loop(auto_publish: bool | None = None) -> dict:
    return get_loop().start(auto_publish=auto_publish)


def get_status() -> dict:
    loop_status = get_loop().status()
    return {
        **loop_status,
        "lineage_count": len(repo.list_lineages()),
        "escalating_lineage_count": len(get_escalating_lineages()),
    }


def get_feed(limit: int | None = None, since: str | None = None) -> list[dict]:
    return repo.get_feed(limit=limit, since=since)


def get_review_queue() -> list[dict]:
    return repo.get_review_queue()


def approve_post(post_id: str, approved_by: str = "reviewer") -> dict:
    post = repo.get_post(post_id)
    if post is None:
        return {"ok": False, "reason": "not_found"}
    if post["state"] != "queued":
        return {"ok": False, "reason": f"post is not queued (state={post['state']})"}
    repo.set_post_state(post_id, "published", approved_by=approved_by)
    return {"ok": True}


def reject_post(post_id: str, approved_by: str = "reviewer") -> dict:
    post = repo.get_post(post_id)
    if post is None:
        return {"ok": False, "reason": "not_found"}
    if post["state"] != "queued":
        return {"ok": False, "reason": f"post is not queued (state={post['state']})"}
    repo.set_post_state(post_id, "rejected", approved_by=approved_by)
    return {"ok": True}
