# Security policy

## Supported versions

Only the latest release receives fixes.

## Reporting a vulnerability

Please **do not open a public issue** for a security problem. Use GitHub's
private reporting instead: *Security* tab → *Report a vulnerability*.

Include the version, what you observed and, if possible, how to reproduce
it. You should get an answer within a week.

## Scope

- How the integration stores and sends the hub token.
- TLS handling (certificate verification, custom CA file).
- Anything that could leak Backlog content outside Home Assistant and the
  hub.

The AI Hub itself is a separate project.
