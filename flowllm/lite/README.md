# FlowLLM Lite

`flowllm.lite` is a tiny local CLI flow runner. It is intentionally separate from the full FlowLLM application framework.

It keeps only four concepts:

- `BaseConfig`: define input parameters with Pydantic.
- `BaseFlow`: hold `config` and `context`, then execute steps in order.
- `register`: bind an action name to a flow class.
- `fl`: read an action and CLI arguments, run the flow, and print JSON output.

## Usage

```shell
fl --list
fl --demo --x 1 --y 2
DEFAULT_PROXY_HOST_ENV=example.com fl --proxy
fl --proxy --host example.com --port 12345
fl --remote-server --host 0.0.0.0 --port 8765
DEFAULT_REMOTE_HOST_ENV=example.com fl --remote-client --action ping
fl --remote-client --action exec --command "pwd"
```

Output:

```json
{"result": 3}
```

The command format is:

```shell
fl --action --field value --another-field value
```

Rules:

- The first argument is the action and must look like `--action`.
- The remaining arguments must appear in pairs: `--field value`.
- `-` in CLI argument names is converted to `_` in Python field names.
- Values are read as strings first, then converted by Pydantic through `BaseConfig`.
- The final result only includes fields declared in `output_keys`.

The built-in `proxy` flow starts an SSH SOCKS5 proxy. Its `host` config defaults
to the `DEFAULT_PROXY_HOST_ENV` environment variable, so no server IP is hard-coded.

The built-in `remote_server` and `remote_client` flows provide the remote command
executor. The client `host` config defaults to `DEFAULT_REMOTE_HOST_ENV`.

## Writing a Flow

```python
from flowllm.lite import BaseConfig, BaseFlow, register


class AddConfig(BaseConfig):
    x: int
    y: int


@register("add")
class AddFlow(BaseFlow[AddConfig]):
    output_keys = ["result"]

    def build_steps(self):
        return [self.add]

    def add(self):
        self.context["result"] = self.config.x + self.config.y
```

Run it:

```shell
fl --add --x 1 --y 2
```

## Design Constraints

Lite flow is designed to be direct to read and easy to change:

- One flow class maps to one action.
- One step is a zero-argument method that reads from `self.config`.
- Steps pass intermediate values through `self.context`.
- `build_steps()` declares execution order explicitly.
- `output_keys` declares final output explicitly.

This implementation does not handle service startup, remote calls, plugin orchestration, complex dependency injection, or streaming protocols. Use the full FlowLLM framework when those capabilities are needed.
