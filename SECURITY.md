# Security policy

## Reporting

Open a **private** security advisory: <https://github.com/Icefox12138/socratic-tutor/security/advisories/new>.
Please do not open a public issue for anything exploitable.

Expect a first reply within a week; this is a spare-time project.

## What is in scope

| Surface | Notes |
|---|---|
| `sidecar/app` HTTP API | Path traversal in `/v1/pages` (book names come from the client) and token handling |
| `plugin-socratic` | Error paths that could leak sidecar responses into the model context |
| `packages/*` | Anything that turns untrusted OCR text into a path |

## What is out of scope

- The tutor giving a wrong answer — that is a quality issue, not a vulnerability.
- Anything requiring the attacker to already run code on the host.
- Content of books in a user's own library.

## Deployment notes

The sidecar binds to `127.0.0.1` by default and has **no authentication unless
`SOCRATIC_TOKEN` is set**. Do not expose it to a network without setting a token.
