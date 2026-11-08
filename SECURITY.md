# Security

This project is a local analysis pack. It does not ship credentials, and the demo does not need any.

## Reporting a vulnerability

Use GitHub private vulnerability reporting on this repository. Do not open a public issue that includes a secret, a connection string, or a customer record.

## What the read-only guard is

The helper scripts open a DuckDB file read-only and reject a statement that is not a single `SELECT` or `WITH`. That rejection is a keyword filter. It is not a database privilege. Against any other engine, use a role that cannot write, and do not paste production secrets into a prompt.

The CI workflow runs gitleaks 8.30.1 over the git history. Turning on the host's own secret scanning is a repository setting and is not changed by the workflow file.
