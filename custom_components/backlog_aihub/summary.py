"""Counts shown by the « to process » sensor (no Home Assistant import, so it can be tested alone)."""

from __future__ import annotations

from typing import Any


def _task_done(task_id: str, task: dict[str, Any], done: dict[str, Any]) -> bool:
    if task.get("prio") == "fait" or (done.get(f"tache:{task_id}") or {}).get("fait"):
        return True
    items = task.get("items") or []
    return bool(items) and all((done.get(i.get("id")) or {}).get("fait") for i in items)


def summarize(data: dict[str, Any]) -> dict[str, int]:
    """What waits for the agents (requests, « not conclusive », 🔍, decisions) and the open tasks."""
    tasks = data.get("taches") or {}
    done = data.get("fait") or {}
    open_tasks = {tid: t for tid, t in tasks.items() if isinstance(t, dict) and not _task_done(tid, t, done)}
    revoir = [r for r in (data.get("revoir") or {}).values() if isinstance(r, dict) and r.get("tache") in tasks]
    verifier = [
        (item, v)
        for item, v in (data.get("verifier") or {}).items()
        if isinstance(v, dict) and v.get("tache") in tasks
    ]
    decisions = [
        x
        for key, x in (data.get("decisions") or {}).items()
        if isinstance(x, dict) and x.get("tache", key) in tasks and not x.get("reponse")
    ]
    counts = {
        "demandes": len(data.get("demandes") or {}),
        "a_revoir": sum(1 for r in revoir if not r.get("reponse")),
        "a_verifier": sum(
            1
            for item, v in verifier
            if v.get("resultat") in (None, "", "attente") and not (done.get(item) or {}).get("fait")
        ),
        "decisions": len(decisions),
        "maintenant": sum(1 for t in open_tasks.values() if t.get("prio") == "maintenant"),
        "taches_ouvertes": len(open_tasks),
    }
    counts["pour_les_agents"] = counts["demandes"] + counts["a_revoir"] + counts["a_verifier"] + counts["decisions"]
    return counts
