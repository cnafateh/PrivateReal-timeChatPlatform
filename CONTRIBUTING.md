# Contributing to Pulse

## Getting started

Follow the README's local setup, install `requirements-dev.txt`, and create a focused branch. Keep a change small enough to review, and include a clear reproduction for bug fixes.

## Before opening a pull request

- Explain the problem, observable behavior after the change and any compatibility impact.
- Add regression tests for new behavior and security boundaries.
- Run the server tests, migration checks and relevant browser tests described in `docs/TESTING.md`.
- Commit model migrations, but never database files, `.env` files, recordings, test uploads or credentials.
- Keep frontend user text safely escaped and preserve keyboard/mobile behavior in both themes.
- Update documentation when configuration, endpoints or operation changes.

Use ordinary Python/Django conventions, descriptive names and short functions. Keep authentication and membership checks on the server, even when a control is hidden in the interface. Avoid introducing a framework or dependency for a small change without explaining why it is needed.

## Reporting bugs

Include the operating system, browser version, steps to reproduce, expected result, actual result and sanitized logs. Screenshots are useful for layout problems. Do not include private conversation contents or tokens.

For vulnerabilities, follow `SECURITY.md` instead of opening a public issue.
