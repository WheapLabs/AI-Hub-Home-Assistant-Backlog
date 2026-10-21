"""Config flow, actions and sensor, with the hub mocked by aioclient_mock."""

from __future__ import annotations

import pytest
from homeassistant import config_entries
from homeassistant.config_entries import ConfigEntryState
from homeassistant.const import CONF_API_TOKEN, CONF_URL, CONF_VERIFY_SSL
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType
from homeassistant.exceptions import HomeAssistantError, ServiceValidationError
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.backlog_aihub.const import CONF_CA_CERT, DOMAIN

API = "https://hub.example/backlog-api"
DATA = {
    "taches": {"t-a": {"prio": "maintenant", "items": [{"id": "a1"}]}},
    "fait": {},
    "demandes": {"d1": {"texte": "?"}},
    "revoir": {},
    "verifier": {},
    "decisions": {"t-a": {"tache": "t-a"}},
}
SETTINGS = {CONF_URL: API, CONF_API_TOKEN: "secret", CONF_VERIFY_SSL: True, CONF_CA_CERT: ""}


def mock_hub(aioclient_mock, token_ok=True):
    aioclient_mock.get(f"{API}/sante", json={"ok": True})
    if token_ok:
        aioclient_mock.get(f"{API}/historique", json={"copies": []})
    else:
        aioclient_mock.get(f"{API}/historique", status=401, json={"erreur": "Jeton du Backlog requis."})
    aioclient_mock.get(f"{API}/donnees", json={"rev": 7, "quand": 0, "data": DATA}, headers={"ETag": '"7"'})


async def test_flow_ok(hass: HomeAssistant, aioclient_mock) -> None:
    mock_hub(aioclient_mock)
    result = await hass.config_entries.flow.async_init(DOMAIN, context={"source": config_entries.SOURCE_USER})
    assert result["type"] is FlowResultType.FORM
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {CONF_URL: "https://hub.example/", CONF_API_TOKEN: " secret ", CONF_VERIFY_SSL: True}
    )
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["data"] == SETTINGS
    await hass.async_block_till_done()
    assert aioclient_mock.mock_calls[1][3]["Authorization"] == "Bearer secret"


async def test_flow_bad_token(hass: HomeAssistant, aioclient_mock) -> None:
    mock_hub(aioclient_mock, token_ok=False)
    result = await hass.config_entries.flow.async_init(DOMAIN, context={"source": config_entries.SOURCE_USER})
    result = await hass.config_entries.flow.async_configure(result["flow_id"], {CONF_URL: API, CONF_API_TOKEN: "x"})
    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {CONF_API_TOKEN: "invalid_auth"}


async def test_flow_not_a_hub(hass: HomeAssistant, aioclient_mock) -> None:
    aioclient_mock.get(f"{API}/sante", status=404, text="<html>")
    result = await hass.config_entries.flow.async_init(DOMAIN, context={"source": config_entries.SOURCE_USER})
    result = await hass.config_entries.flow.async_configure(result["flow_id"], {CONF_URL: API, CONF_API_TOKEN: "x"})
    assert result["errors"] == {"base": "cannot_connect"}


async def test_flow_bad_url(hass: HomeAssistant) -> None:
    result = await hass.config_entries.flow.async_init(DOMAIN, context={"source": config_entries.SOURCE_USER})
    result = await hass.config_entries.flow.async_configure(result["flow_id"], {CONF_URL: "hub", CONF_API_TOKEN: "x"})
    assert result["errors"] == {CONF_URL: "invalid_url"}


@pytest.fixture
async def loaded(hass: HomeAssistant, aioclient_mock):
    mock_hub(aioclient_mock)
    entry = MockConfigEntry(domain=DOMAIN, data=SETTINGS, title="Backlog AI Hub")
    entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    assert entry.state is ConfigEntryState.LOADED
    return entry


async def test_sensor(hass: HomeAssistant, loaded) -> None:
    state = hass.states.get("sensor.backlog_ai_hub_to_process")
    assert state is not None
    assert state.state == "2"  # one request + one decision
    assert state.attributes["maintenant"] == 1
    assert state.attributes["rev"] == 7


async def test_actions(hass: HomeAssistant, loaded, aioclient_mock) -> None:
    aioclient_mock.post(f"{API}/service", json={"rev": 8, "reponse": {"id": "t-new", "items": 0}})
    out = await hass.services.async_call(
        DOMAIN, "ajouter_tache", {"id": "t-new", "titre": "New"}, blocking=True, return_response=True
    )
    assert out == {"rev": 8, "reponse": {"id": "t-new", "items": 0}}
    sent = [c for c in aioclient_mock.mock_calls if str(c[1]).endswith("/service")][-1]
    assert sent[2] == {"action": "ajouter_tache", "donnees": {"id": "t-new", "titre": "New"}}

    aioclient_mock.clear_requests()
    mock_hub(aioclient_mock)
    aioclient_mock.post(f"{API}/service", json={"rev": 7, "reponse": DATA})
    out = await hass.services.async_call(DOMAIN, "exporter", {}, blocking=True, return_response=True)
    assert out == DATA


async def test_action_refused(hass: HomeAssistant, loaded, aioclient_mock) -> None:
    aioclient_mock.post(f"{API}/service", status=400, json={"erreur": "Champ inconnu : x.", "code": "invalid"})
    with pytest.raises(ServiceValidationError, match="Champ inconnu"):
        await hass.services.async_call(DOMAIN, "ajouter_tache", {"id": "t", "x": 1}, blocking=True)


async def test_action_hub_down(hass: HomeAssistant, loaded, aioclient_mock) -> None:
    aioclient_mock.post(f"{API}/service", status=502, json={"erreur": "Bad gateway"})
    with pytest.raises(HomeAssistantError):
        await hass.services.async_call(DOMAIN, "cocher", {"ids": ["a1"]}, blocking=True)


async def test_action_without_entry(hass: HomeAssistant) -> None:
    from homeassistant.setup import async_setup_component

    assert await async_setup_component(hass, DOMAIN, {})
    with pytest.raises(ServiceValidationError):
        await hass.services.async_call(DOMAIN, "exporter", {}, blocking=True, return_response=True)


async def test_unload(hass: HomeAssistant, loaded) -> None:
    assert await hass.config_entries.async_unload(loaded.entry_id)
    assert loaded.state is ConfigEntryState.NOT_LOADED


async def test_descriptions(hass: HomeAssistant, loaded) -> None:
    from homeassistant.helpers.service import async_get_all_descriptions

    desc = (await async_get_all_descriptions(hass))[DOMAIN]
    assert set(desc) == {
        "ajouter_tache", "ajouter_journal", "cocher", "repondre", "verifie", "decision_traitee", "supprimer", "exporter"
    }
    assert desc["ajouter_tache"]["fields"]["id"]["required"] is True
    from homeassistant.helpers.translation import async_get_translations

    for lang, name in (("en", "Add or update a task"), ("fr", "Ajouter ou modifier une tâche")):
        tr = await async_get_translations(hass, lang, "services", [DOMAIN])
        assert tr[f"component.{DOMAIN}.services.ajouter_tache.name"] == name
        assert all(f"component.{DOMAIN}.services.{s}.description" in tr for s in desc)
    tr = await async_get_translations(hass, "fr", "entity", [DOMAIN])
    assert tr[f"component.{DOMAIN}.entity.sensor.a_traiter.name"] == "À traiter"
