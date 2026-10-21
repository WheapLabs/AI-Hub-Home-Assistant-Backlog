# Backlog AI Hub for Home Assistant

*[Version française](README.fr.md)*

A light Home Assistant integration that gives your automations and scripts
**actions to write to the Backlog of an [AI Hub](https://github.com/WheapLabs)**:
add a task when a battery is low, write to the journal when a backup fails,
check an item when a test passes…

It keeps **no copy** of the Backlog. Each action is relayed to the hub's
Backlog service (`POST /backlog-api/service`) and the hub's answer becomes the
action's response. The hub stays the only place where the Backlog lives.

## Requirements

- Home Assistant 2025.3 or newer.
- A running AI Hub with its Backlog service reachable from Home Assistant
  (`GET <hub>/backlog-api/sante` answers `{"ok": true}`).
- The hub's Backlog token.

Field names and values (`titre`, `prio`, `genre`…) are the hub's own, which
are French; each action's fields are described in the Home Assistant action
editor, in English and French.

## Features

- Actions (domain `backlog_aihub`), with the same fields and answers as the
  hub's `aihub-backlog` command line:

  | Action | What it does | Response |
  |---|---|---|
  | `backlog_aihub.ajouter_tache` | Create a task, or complete an existing one | `{rev, reponse: {id, items}}` |
  | `backlog_aihub.ajouter_journal` | Write a journal entry | `{rev, reponse: {id}}` |
  | `backlog_aihub.cocher` | Check / uncheck items (or `tache:<id>`) | `{rev, reponse: null}` |
  | `backlog_aihub.repondre` | Answer an item marked « not conclusive » | `{rev, reponse: {item}}` |
  | `backlog_aihub.verifie` | Give the result of a 🔍 « check it yourself » item | `{rev, reponse: {item, resultat}}` |
  | `backlog_aihub.decision_traitee` | Write the answer to a decision | `{rev, reponse: {cible}}` |
  | `backlog_aihub.supprimer` | Delete one entry of a collection | `{rev, reponse: {supprime}}` |
  | `backlog_aihub.exporter` | Return the whole Backlog (response only) | the collections |

  The hub checks every field. When it refuses an action (unknown field,
  unknown item…), the action fails with the hub's message.
- A sensor **To process** (`sensor.backlog_ai_hub_to_process`): the number of
  things waiting for the agents (requests, « not conclusive », 🔍 checks,
  decisions), with the details as attributes (`demandes`, `a_revoir`,
  `a_verifier`, `decisions`, `maintenant`, `taches_ouvertes`, `rev`). It reads
  the hub every 2 minutes and right after each action; the hub answers
  « 304 Not Modified » when nothing changed.
- Setup from the UI: the hub's address and its Backlog token are checked
  before the integration is added. Reconfigure and re-authentication are
  supported.

## Installation (HACS)

1. HACS → ⋮ → **Custom repositories** → add
   `https://github.com/WheapLabs/AI-Hub-Home-Assistant-Backlog`, type **Integration**.
2. Install **Backlog AI Hub**, then restart Home Assistant.
3. Settings → Devices & services → **Add integration** → *Backlog AI Hub*.

Manual installation: copy `custom_components/backlog_aihub` into your
`config/custom_components/` folder and restart.

## Configuration

| Field | Value |
|---|---|
| Address | The hub's Backlog API, e.g. `https://hub.example/backlog-api` (the hub's address alone also works: `/backlog-api` is added) |
| Backlog token | The token shown in the hub's console (or `aihub-backlog jeton` on the hub) |
| Verify the TLS certificate | Keep it on. Turn it off only on a trusted local network |
| CA certificate file | Optional: path of the hub's certificate authority (e.g. `/config/aihub-ca.crt`) when the hub uses its own CA |

## Examples

```yaml
# Add a task when a battery is low
- action: backlog_aihub.ajouter_tache
  data:
    id: "t-battery-{{ trigger.entity_id | replace('.', '-') }}"
    titre: "Replace the battery of {{ state_attr(trigger.entity_id, 'friendly_name') }}"
    prio: semaine
    type: reparer
    domaine: Appareils
    action: "Battery at {{ trigger.to_state.state }} %"

# Write to the journal and read the hub's answer
- action: backlog_aihub.ajouter_journal
  data:
    titre: Backup failed
    genre: constat
    domaine: Organisation
    pourquoi: "{{ trigger.event.data.message }}"
  response_variable: entry   # entry.reponse.id = the new entry's id

# Read everything
- action: backlog_aihub.exporter
  response_variable: backlog
```

## Coexisting with another Backlog integration

The domain is `backlog_aihub`, so it can run next to an older integration that
uses the `backlog` domain while automations are moved over.

## Later: the Backlog panel served by the hub

This integration does not add a panel yet. The hub already serves the panel
files (`GET /backlog-api/panneau/backlog-panel.js`) and applies the panel's
messages (`POST /backlog-api/action`, the same `backlog/<action>` messages
the panel sends over Home Assistant's WebSocket). A future version can:

1. register a sidebar panel (`panel_custom`) whose module is served through a
   small Home Assistant view that proxies `/backlog-api/panneau/*` (so the
   browser never sees the token);
2. register the panel's WebSocket commands (`backlog/subscribe`,
   `backlog/fait`, …) and relay each one to `POST /backlog-api/action`, with
   `backlog/subscribe` fed by the same polling of `GET /backlog-api/donnees`.

The panel code then stays in one place (the hub) and serves both the hub's
console and Home Assistant.

## Development

Two test suites:

```bash
# 1. The HTTP client and the counts (no Home Assistant needed)
python3 -m venv .venv && .venv/bin/pip install -r requirements_test.txt
.venv/bin/pytest
# Optional: contract test against the real hub service (run in a temporary folder)
AIHUB_BACKLOG_SERVICE=/path/to/AI-Hub/ct/bin/aihub-backlog .venv/bin/pytest

# 2. The integration in Home Assistant (config flow, actions, sensor), Python 3.14
python3.14 -m venv .venv-ha && .venv-ha/bin/pip install -r requirements_test_ha.txt
.venv-ha/bin/pytest tests_ha
```

The GitHub workflow runs both, plus HACS and hassfest validation.

## Security and privacy

- The token is stored in the integration's config entry, like any Home
  Assistant credential. It is only sent to the hub, as a Bearer token.
- Keep TLS verification on; give the hub's CA file when it uses its own CA.
- To report a vulnerability, see [SECURITY.md](SECURITY.md).

## Contributing

See [CONTRIBUTING.md](CONTRIBUTING.md) and the [changelog](CHANGELOG.md).

## License

MIT, see [LICENSE](LICENSE).
