---
name: remote-client
description: FlowLLM lite remote client operation guide. Use when a user asks Codex to run, inspect, monitor, or terminate commands through flowllm/lite/flow/remote_client_flow.py or the `fl --remote-client` CLI, including remote exec, ping, tasks, kill, kill_all, command files, Python files, timeout, host, port, and remote server troubleshooting.
---

# Remote Client

## Overview

Use the FlowLLM lite `remote_client` flow to call a running `remote_server` over HTTP. Prefer it when work should execute on a configured remote project host instead of the local Codex shell.

The implementation lives in `flowllm/lite/flow/remote_client_flow.py`; the paired server endpoints live in `flowllm/lite/flow/remote_server_flow.py`.

## Before Running

Confirm the target host and port before launching remote work:

```bash
fl --remote-client --action ping
```

If `--host` is omitted, `remote_client_flow.py` reads `DEFAULT_REMOTE_HOST_ENV`. If neither is set, it raises `Remote host is required. Set DEFAULT_REMOTE_HOST_ENV or pass --host.`

Use `--host` only when overriding `DEFAULT_REMOTE_HOST_ENV`. Use `--port` only when the server is not on the default `8765`.

## Actions

Run a shell command remotely and stream stdout/stderr back to the local terminal:

```bash
fl --remote-client --action exec --command "pytest tests/unit"
```

Run a command stored in a local file:

```bash
fl --remote-client --action exec --command-file /path/to/command.sh
```

Upload and run a local Python file on the remote server:

```bash
fl --remote-client --action exec --python-file /path/to/script.py
```

Inspect tracked remote tasks:

```bash
fl --remote-client --action tasks
fl --remote-client --action tasks --status running --tail 80
```

Terminate a task or all running tasks:

```bash
fl --remote-client --action kill --task-id 12
fl --remote-client --action kill_all
```

## Parameters

- `--action`: one of `exec`, `ping`, `tasks`, `kill`, `kill_all`; default is `exec`.
- `--host`: remote host. Falls back to `DEFAULT_REMOTE_HOST_ENV`.
- `--port`: remote server port; default is `8765`.
- `--timeout`: command timeout in seconds; default is `3600`.
- `--command`: shell command string for `exec`.
- `--command-file`: local text file whose contents become the remote shell command.
- `--python-file`: local Python file uploaded as code and run by the remote Python interpreter.
- `--status`: optional task status filter for `tasks`, commonly `running`, `finished`, or `killed`.
- `--tail`: output lines to include per task for `tasks`; default is `30`.
- `--task-id`: required for `kill`.

For `exec`, provide exactly one of `--command`, `--command-file`, or `--python-file`.

## Remote Server Assumptions

The client expects the server to expose:

- `GET /ping`
- `GET /tasks`
- `POST /exec`
- `POST /tasks/{task_id}/kill`
- `POST /tasks/kill-all`

The remote server executes shell commands with `cwd` set to `FLOWLLM_REMOTE_PROJECT_DIR` when that environment variable is set, otherwise the server process working directory. Python-file execution prepends that project directory to `PYTHONPATH`.

## Troubleshooting

When connection fails, verify `fl --remote-client --action ping` first, then check that `DEFAULT_REMOTE_HOST_ENV` is set and `remote_server` is running and reachable from the local machine.

If a streamed command disconnects, inspect remote state with:

```bash
fl --remote-client --action tasks --status running
```

For long or multi-line commands, prefer `--python-file` or `--command-file` over complex shell quoting.

After a timeout, the server writes `[TIMEOUT]` to the stream and attempts to terminate the remote process group.
