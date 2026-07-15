# Usage Guide

[简体中文](usage.zh-CN.md) | [README](../README.md) | [Integration](integration.md)

Metadata MCP models application management as `task + action + context +
payload + options`. Discovery responses stay compact; fetch the exact action
schema only when an action is selected.

## Discover Tasks

List groups:

```json
{}
```

Call `yeelight_metadata.list_groups`, then browse tasks in a group:

```json
{
  "group": "family_space",
  "limit": 20
}
```

Call `yeelight_metadata.list_tasks` with an exact task to get its action summary:

```json
{
  "task": "family_space.manage_room"
}
```

Use `yeelight_metadata.list_actions` to filter by task, group, status,
side-effect level, or execution mode.

## List and Switch Homes

Call `yeelight_metadata.list_houses` with `{}` to list Pro homes available to
the current Authorization and Region. To switch homes, select a stable
`houseId` and pass it explicitly in each later request:

```json
{
  "request": {
    "task": "family_space.manage_house",
    "action": "get_house_detail",
    "context": {"houseId": "<TARGET_HOUSE_ID>"},
    "options": {"dryRun": false}
  }
}
```

The server does not persist a global current home. If an action needs a home,
selection precedence is `context.houseId` -> `House-Id` -> first Pro home.

## Read an Action Schema

Call `yeelight_metadata.get_action_schema`:

```json
{
  "task": "family_space.manage_room",
  "action": "create"
}
```

The response describes required global headers, local context, payload, options,
side effects, execution mode, and status.

## Generate a Dry-Run Plan

Call `yeelight_metadata.execute_task`:

```json
{
  "request": {
    "task": "family_space.manage_room",
    "action": "create",
    "payload": {"name": "Temporary Test Room"},
    "options": {"dryRun": true}
  }
}
```

A dry run validates the request and returns `plan.httpRequest` without calling
the business API.

## Execute a Read

```json
{
  "request": {
    "task": "family_space.manage_house",
    "action": "get_house_detail",
    "options": {"dryRun": false}
  }
}
```

Successful live calls include a normalized `ok`, `code`, `message`, and `data`
shape.

## Execute a Confirmed Write

```json
{
  "request": {
    "task": "family_space.manage_room",
    "action": "create",
    "payload": {"name": "Temporary Test Room"},
    "options": {
      "dryRun": false,
      "confirmSideEffect": true
    }
  }
}
```

Only add `allowCandidate=true` when a candidate action has been reviewed and the
runtime environment explicitly permits candidate execution.

## Acceptance CLI

The repository includes a protocol-level client:

```bash
export METADATA_MCP_ACCESS_TOKEN='<YOUR_AUTHORIZATION>'
export METADATA_MCP_REGION='cn'
export METADATA_MCP_HOUSE_ID='<YOUR_HOUSE_ID>'

PYTHONPATH=src .venv/bin/python scripts/mcp_acceptance_cli.py tools
PYTHONPATH=src .venv/bin/python scripts/mcp_acceptance_cli.py houses
PYTHONPATH=src .venv/bin/python scripts/mcp_acceptance_cli.py groups
PYTHONPATH=src .venv/bin/python scripts/mcp_acceptance_cli.py tasks --group family_space
PYTHONPATH=src .venv/bin/python scripts/mcp_acceptance_cli.py actions --task family_space.manage_room
PYTHONPATH=src .venv/bin/python scripts/mcp_acceptance_cli.py schema family_space.manage_room create
PYTHONPATH=src .venv/bin/python scripts/mcp_acceptance_cli.py dryrun family_space.manage_room create \
  --payload '{"name":"Temporary Test Room"}'
PYTHONPATH=src .venv/bin/python scripts/mcp_acceptance_cli.py smoke
```

Useful options include `--url`, `--token`, `--region`, `--house-id`, `--timeout`, `--full`,
and `--context`. `smoke` includes a live read-only account request in addition to
a dry run, so use it only with an endpoint and credential intended for testing.

## Full Action Matrix

This command validates every registered action and builds dry-run plans without
calling the cloud by default:

```bash
PYTHONPATH=src .venv/bin/python scripts/action_acceptance_matrix.py
```

Live modes and `scripts/live_write_acceptance.py` can modify cloud data. Use a
non-production home and make sure every fixture can be queried and cleaned up.

## Operating Rules

- Resolve names to real IDs before writes or controls.
- Refresh action schemas after a validation failure.
- Keep tokens, home IDs, and payload data out of logs and reports.
- Use dry-run plans for all writes and destructive actions.
- Verify writes with a follow-up query when the API supports it.
- Do not retry delete, unbind, transfer, login, or binding actions blindly.
