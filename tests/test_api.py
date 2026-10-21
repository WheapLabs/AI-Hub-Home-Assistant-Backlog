"""Tests of the HTTP client against a small fake hub (aiohttp test server)."""

from __future__ import annotations

import aiohttp
import pytest
from aiohttp import web
from api import BacklogClient, CannotConnect, InvalidAuth, Refused, normalize_url

TOKEN = "test-token"


def fake_hub(state: dict) -> web.Application:
    state.setdefault("rev", 3)
    state.setdefault("data", {"taches": {}, "demandes": {}})
    state.setdefault("calls", [])

    def authorized(request: web.Request) -> bool:
        return request.headers.get("Authorization") == f"Bearer {TOKEN}"

    async def sante(request):
        return web.json_response({"ok": True})

    async def historique(request):
        if not authorized(request):
            return web.json_response({"erreur": "Jeton du Backlog requis."}, status=401)
        return web.json_response({"copies": []})

    async def donnees(request):
        if not authorized(request):
            return web.json_response({"erreur": "Jeton du Backlog requis."}, status=401)
        state["calls"].append(("donnees", request.headers.get("If-None-Match")))
        etag = f'"{state["rev"]}"'
        if request.headers.get("If-None-Match") == etag:
            return web.Response(status=304, headers={"ETag": etag})
        return web.json_response({"rev": state["rev"], "quand": 0, "data": state["data"]}, headers={"ETag": etag})

    async def service(request):
        if not authorized(request):
            return web.json_response({"erreur": "Jeton du Backlog requis."}, status=401)
        body = await request.json()
        state["calls"].append(("service", body))
        action, donnees = body["action"], body["donnees"]
        if action == "exporter":
            return web.json_response({"rev": state["rev"], "reponse": state["data"]})
        if action == "repondre":
            return web.json_response({"erreur": f"Aucun point « à revoir » : {donnees['item']}", "code": "not_found"}, status=404)
        if action == "ajouter_tache":
            if "inconnu" in donnees:
                return web.json_response({"erreur": "Champ inconnu : inconnu.", "code": "invalid"}, status=400)
            state["rev"] += 1
            state["data"]["taches"][donnees["id"]] = donnees
            return web.json_response({"rev": state["rev"], "reponse": {"id": donnees["id"], "items": 0}})
        if action == "plante":
            return web.json_response({"erreur": "boum"}, status=500)
        return web.json_response({"erreur": "Action inconnue.", "code": "unknown_command"}, status=400)

    app = web.Application()
    for prefix in ("/backlog-api", ""):
        app.router.add_get(f"{prefix}/sante", sante)
        app.router.add_get(f"{prefix}/historique", historique)
        app.router.add_get(f"{prefix}/donnees", donnees)
        app.router.add_post(f"{prefix}/service", service)
    return app


@pytest.fixture
async def hub(aiohttp_server):
    state: dict = {}
    server = await aiohttp_server(fake_hub(state))
    async with aiohttp.ClientSession() as session:
        yield state, server, session


def client(server, session, token=TOKEN, path="/backlog-api"):
    return BacklogClient(session, str(server.make_url(path)), token)


@pytest.mark.parametrize(
    ("given", "expected"),
    [
        ("https://hub.example", "https://hub.example/backlog-api"),
        ("https://hub.example/", "https://hub.example/backlog-api"),
        ("https://hub.example/backlog-api/", "https://hub.example/backlog-api"),
        (" http://192.0.2.10:8782/backlog-api ", "http://192.0.2.10:8782/backlog-api"),
        ("https://hub.example/other?x=1", "https://hub.example/other"),
    ],
)
def test_normalize_url(given, expected):
    assert normalize_url(given) == expected


@pytest.mark.parametrize("bad", ["", "hub.example", "ftp://hub.example", "https://"])
def test_normalize_url_refuses(bad):
    with pytest.raises(ValueError):
        normalize_url(bad)


async def test_validate_ok(hub):
    _, server, session = hub
    await client(server, session).validate()


async def test_validate_bad_token(hub):
    _, server, session = hub
    with pytest.raises(InvalidAuth):
        await client(server, session, token="wrong").validate()


async def test_validate_not_a_backlog(hub):
    _, server, session = hub
    with pytest.raises(CannotConnect):
        await client(server, session, path="/nothing-here").validate()


async def test_unreachable():
    async with aiohttp.ClientSession() as session:
        with pytest.raises(CannotConnect):
            await BacklogClient(session, "http://127.0.0.1:9", TOKEN).health()


async def test_service_write_and_answer(hub):
    state, server, session = hub
    out = await client(server, session).service("ajouter_tache", {"id": "t-x", "titre": "X"})
    assert out == {"rev": 4, "reponse": {"id": "t-x", "items": 0}}
    assert state["calls"][-1] == ("service", {"action": "ajouter_tache", "donnees": {"id": "t-x", "titre": "X"}})


async def test_service_export(hub):
    _, server, session = hub
    out = await client(server, session).service("exporter")
    assert out["reponse"] == {"taches": {}, "demandes": {}}


async def test_service_refused_field(hub):
    _, server, session = hub
    with pytest.raises(Refused, match="Champ inconnu") as err:
        await client(server, session).service("ajouter_tache", {"id": "t-x", "inconnu": 1})
    assert err.value.status == 400


async def test_service_refused_not_found(hub):
    _, server, session = hub
    with pytest.raises(Refused, match="Aucun point") as err:
        await client(server, session).service("repondre", {"item": "nope", "reponse": "x"})
    assert err.value.code == "not_found"


async def test_service_server_error(hub):
    _, server, session = hub
    with pytest.raises(CannotConnect, match="500"):
        await client(server, session).service("plante")


async def test_service_bad_token(hub):
    _, server, session = hub
    with pytest.raises(InvalidAuth):
        await client(server, session, token="wrong").service("exporter")


async def test_snapshot_uses_etag(hub):
    state, server, session = hub
    c = client(server, session)
    first = await c.snapshot()
    again = await c.snapshot()
    assert again is first and first.rev == 3
    assert state["calls"][-1] == ("donnees", '"3"')
    await c.service("ajouter_tache", {"id": "t-y"})
    changed = await c.snapshot()
    assert changed.rev == 4 and "t-y" in changed.data["taches"]
