# Contributing

Thanks for your interest! Issues and pull requests are welcome.

## Before you open a pull request

1. Open an issue first for anything bigger than a small fix, so we can agree
   on the approach.
2. Work on a branch, never directly on `main`.
3. Keep the integration a thin relay: the Backlog lives in the AI Hub, and
   this integration must not keep its own copy.
4. Run both test suites (see *Development* in the [README](README.md)) and
   `ruff check .`.
5. Update the [README](README.md), the [changelog](CHANGELOG.md) and both
   translation files (`translations/en.json`, `translations/fr.json`, and
   `strings.json`) when you change a user-facing text.
6. Bump `version` in `custom_components/backlog_aihub/manifest.json` for a
   release.

## Privacy

This repository is public. Never commit a real hub address, domain name,
public IP address, token, certificate, or personal name. Use
`hub.example` and documentation IP ranges (`192.0.2.0/24`) in tests and
examples.
