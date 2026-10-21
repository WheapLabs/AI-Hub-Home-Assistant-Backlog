# Changelog

All notable changes to this project are listed here. The format follows
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/) and versions follow
[Semantic Versioning](https://semver.org/).

## [Unreleased]

### Fixed

- Service field descriptions no longer contain brackets and braces, which
  hassfest rejects as invalid placeholders.

### Added

- Pull request template; the contributing guide describes the pull request
  title and the changelog entry.

## [0.1.0] - 2026-10-20

### Added

- Actions relayed to the hub's Backlog service: `ajouter_tache`,
  `ajouter_journal`, `cocher`, `repondre`, `verifie`, `decision_traitee`,
  `supprimer` and `exporter` (response only).
- Sensor **To process**: the number of items waiting for the agents, with the
  details as attributes; polled every 2 minutes with `ETag` / `304`.
- UI setup with address and token check, optional CA certificate,
  reconfigure and re-authentication.
- English and French translations.
- GitHub workflow: HACS validation, hassfest and both test suites.
