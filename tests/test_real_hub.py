"""Contract test against the real AI Hub Backlog service, run in a temporary folder.

Skipped unless AIHUB_BACKLOG_SERVICE points to the hub's ``aihub-backlog`` script, e.g.
``AIHUB_BACKLOG_SERVICE=../AI-Hub/ct/bin/aihub-backlog pytest``.
"""

from __future__ import annotations

import json
import os
import socket
import subprocess
import sys
import time
import urllib.request

import aiohttp
import pytest
from api import BacklogClient, InvalidAuth, Refused

SERVICE = os.environ.get("AIHUB_BACKLOG_SERVICE")
pytestmark = pytest.mark.skipif(not SERVICE, reason="AIHUB_BACKLOG_SERVICE not set")


@pytest.fixture(scope="module")
def real_hub(tmp_path_factory):
    tmp = tmp_path_factory.mktemp("hub")
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        port = s.getsockname()[1]
    env = dict(
        os.environ,
        AIHUB_BACKLOG_DIR=str(tmp / "data"),
        AIHUB_BACKLOG_CONF=str(tmp / "conf"),
        AIHUB_BACKLOG_PANNEAU=str(tmp / "panneau"),
        AIHUB_BACKLOG_IMAGES=str(tmp / "images"),
        AIHUB_BACKLOG_PORT=str(port),
        AIHUB_SYSTEMD_RUN="/bin/false",
    )
    proc = subprocess.Popen([sys.executable, "-I", SERVICE], env=env)
    url = f"http://127.0.0.1:{port}/backlog-api"
    for _ in range(50):
        try:
            urllib.request.urlopen(url + "/sante", timeout=1)
            break
        except OSError:
            time.sleep(0.1)
    token = subprocess.run(
        [sys.executable, "-I", SERVICE, "jeton"], env=env, capture_output=True, text=True, check=True
    ).stdout.strip()
    empty = {c: {} for c in ("taches", "journal", "fait", "demandes", "revoir", "verifier", "decisions", "etat")}
    req = urllib.request.Request(
        url + "/importer", method="POST", data=json.dumps({"data": empty}).encode(),
        headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json"},
    )
    urllib.request.urlopen(req, timeout=5).close()
    yield url, token
    proc.terminate()
    proc.wait(5)


async def test_round_trip(real_hub):
    url, token = real_hub
    async with aiohttp.ClientSession() as session:
        c = BacklogClient(session, url, token)
        await c.validate()
        out = await c.service(
            "ajouter_tache",
            {"id": "t-test", "titre": "Test", "prio": "semaine", "type": "tester", "domaine": "Tests", "action": "Try",
             "items": [{"id": "t-test-1", "n": "It works"}]},
        )
        assert out["reponse"] == {"id": "t-test", "items": 1}
        assert (await c.service("ajouter_journal", {"titre": "Hello", "genre": "constat", "domaine": "Tests"}))["reponse"]["id"]
        await c.service("cocher", {"ids": ["t-test-1"], "par": "test"})
        snap = await c.snapshot()
        assert snap.data["fait"]["t-test-1"]["fait"] is True
        assert (await c.snapshot()) is snap  # 304
        export = (await c.service("exporter"))["reponse"]
        assert "t-test" in export["taches"]
        with pytest.raises(Refused):
            await c.service("ajouter_tache", {"id": "t-test", "inconnu": 1})
        with pytest.raises(Refused):
            await c.service("repondre", {"item": "nope", "reponse": "x"})
        with pytest.raises(Refused):
            await c.service("decision_traitee", {"cible": "nope", "reponse": "x"})
        assert (await c.service("supprimer", {"collection": "taches", "id": "t-test"}))["reponse"] == {"supprime": True}
        with pytest.raises(InvalidAuth):
            await BacklogClient(session, url, "wrong").validate()
