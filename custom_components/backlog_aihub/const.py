"""Constants of the Backlog AI Hub integration."""

from __future__ import annotations

from datetime import timedelta

DOMAIN = "backlog_aihub"

CONF_CA_CERT = "ca_cert"

SCAN_INTERVAL = timedelta(minutes=2)

# Actions that write: they answer {"rev", "reponse"}; the answer can be read with response_variable.
WRITE_ACTIONS = (
    "ajouter_tache",
    "ajouter_journal",
    "cocher",
    "repondre",
    "verifie",
    "decision_traitee",
    "supprimer",
)
EXPORT_ACTION = "exporter"
