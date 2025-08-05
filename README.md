<p align="center">
  <picture>
    <img width="302" height="79" alt="hooksMCP" src="https://github.com/user-attachments/assets/555412a4-70a3-4a9c-89f7-579b7a3d4205" />
  </picture>
</p>
<h3 align="center">
  Give coding agents safe MCP access to linting, testing, formatting, and more. All with one YAML file.
</h3>

<a href="https://glama.ai/mcp/servers/@scosman/actions_mcp">
  <img width="380" height="200" src="https://glama.ai/mcp/servers/@scosman/actions_mcp/badge" alt="ActionsMCP MCP server" />
</a>

## Overview

1. **Simple setup:** one YAML file is all it takes to create a custom MCP server for your coding agents. Similar to package.json scripts or Github Actions workflows, but commands run as MCP server functions. Add the YAML to your repo to share with your team.
2. **Tool discovery:** coding agents know which dev-tools are available and the exact arguments they require. No more guessing CLI strings.
3. **Improved security:** limit the commands agents can run. Add extra validation of the arguments agents generate (e.g. ensure a file path is inside the project).
4. **Works anywhere MCP works:** Cursor, Windsurf, Cline, etc
5. **And more:** strip ANSI codes/control characters, `.env` file loading, define required secrets without checking them in, supports exit codes/stdout/stderr, etc

<p align="center">
<img width="293" height="299" alt="Screenshot 2025-08-05 at 12 08 20 AM" src="https://github.com/user-attachments/assets/b7352ab4-d212-45f0-8267-67bc7209eb5b" />
</p>

[![All Checks](https://github.com/scosman/hooks_mcp/actions/workflows/all-checks.yml/badge.svg)](https://github.com/scosman/hooks_mcp/actions/workflows/all-checks.yml)

## Quick Start

1. Install with [uv](https://docs.astral.sh/uv/concepts/tools/):

```bash
uv tool install hooks-mcp
```

2. Create an [`hooks_mcp.yaml`](#configuration-file-specification) file in your project root defining your tools. For example:

```yaml
actions:
  - name: "all_tests"
    description: "Run all tests in the project"
    command: "uv run python -m pytest ./tests"
    
  - name: "check_format"
    description: "Check if the source code is formatted correctly"
    command: "uvx ruff format --check ."
    
  - name: "typecheck"
    description: "Typecheck the source code"
    command: "uv run pyright ."

  - name: "test_file"
    description: "Run tests in a specific file or directory"
    command: "python -m pytest $TEST_PATH"
    parameters:
      - name: "TEST_PATH"
        type: "project_file_path"
        description: "Path to test file or directory"
```

3. Run the server:

```bash
uvx hooks-mcp
```

See [running HooksMCP](#running-hooksmcp) for more runtime options.

## Configuration File Specification

The `hooks_mcp.yaml` file defines the tools that will be exposed through the MCP server.

See this project's [hooks_mcp.yaml](./hooks_mcp.yaml) as an example.

### Top-level Fields

- `server_name` (optional): Name of the MCP server (default: "HooksMCP")
- `server_description` (optional): Description of the MCP server (default: "Project-specific development tools exposed via MCP")
- `actions` (required): Array of action definitions

### Action Fields

Each action in the `actions` array can have the following fields:

- `name` (required): Unique identifier for the tool
- `description` (required): Human-readable description of what the tool does
- `command` (required): The CLI command to execute. May include dynamic parameters like `$TEST_FILE_PATH`.
- `parameters` (optional): Definitions of each parameter used in the command. 
- `run_path` (optional): Relative path from project root where the command should be executed. Useful for mono-repos.
- `timeout` (optional): Timeout in seconds for command execution (default: 60 seconds)

### Parameter Fields

Each parameter in an action's `parameters` array can have the following fields:

- `name` (required): The parameter name to substitute into the command. For example `TEST_FILE_PATH`.
- `type` (required): One of the following parameter types:
  - `project_file_path`: A local path within the project, relative to project root. Validated to ensure it's within project boundaries and exists.
  - `required_env_var`: An environment variable that must be set before the server starts. Not specified by the calling model. 
  - `optional_env_var`: An optional environment variable. Not specified by the calling model.
  - `insecure_string`: Any string from the model. No validation. Use with caution.
- `description` (optional): Human-readable description of the parameter
- `default` (optional): Default value for the parameter

## Parameter Types Explained

### project_file_path

This parameter type ensures security by validating that paths are within the project boundaries:

```yaml
- name: "test_file"
  description: "Run tests in a specific file"
  command: "python -m pytest $TEST_FILE"
  parameters:
    - name: "TEST_FILE"
      type: "project_file_path"
      description: "Path to test file"
      default: "./tests"
```

The server will validate that `TEST_FILE` is within the project and exists.

### required_env_var

These parameters must be set in the environment before starting the server. If they are not set, the server will fail on startup asking the user to set the variables.

```yaml
- name: "deploy"
  description: "Deploy the application"
  command: "deploy-tool --key=$DEPLOY_KEY"
  parameters:
    - name: "DEPLOY_KEY"
      type: "required_env_var"
      description: "Deployment key for the service"
```

HooksMCP will load env vars from the environment, and any set in a `.env` file in your working directory.

### optional_env_var

Similar to `required_env_var` but optional:

```yaml
- name: "build"
  description: "Build the application"
  command: "build-tool"
  parameters:
    - name: "BUILD_FLAGS"
      type: "optional_env_var"
      description: "Additional build flags"
```

### insecure_string

Allows any string input from the coding assistant without validation. Use with caution:

```yaml
- name: "grep_code"
  description: "Search code for pattern"
  command: "grep -r $PATTERN src/"
  parameters:
    - name: "PATTERN"
      type: "insecure_string"
      description: "Pattern to search for"
```

## Running HooksMCP

We recommend running HooksMCP with [uvx](https://docs.astral.sh/uv/concepts/tools/):

```bash
# Install
uv tool install hooks-mcp
# Run
uvx hooks-mcp 
```

Optional command line arguments include:
 - `--working-directory`/`-wd`: Typically the path to your project root. Set if not running from project root.
 - The last argument is the path to the `hooks_mcp.yaml` file, if not using the default `./hooks_mcp.yaml`

### Running with Coding Assistants

#### Cursor

[![Install MCP Server](https://cursor.com/deeplink/mcp-install-dark.svg)](https://cursor.com/install-mcp?name=HooksMCP&config=eyJjb21tYW5kIjoidXZ4IGhvb2tzLW1jcCAtLXdvcmtpbmctZGlyZWN0b3J5IC4ifQ)

Or open this [cursor deeplink](cursor://anysphere.cursor-deeplink/mcp/install?name=HooksMCP&config=eyJjb21tYW5kIjoidXZ4IGhvb2tzLW1jcCAtLXdvcmtpbmctZGlyZWN0b3J5IC4ifQ).

#### Windsurf/VSCode/etc

Most other IDEs use a variant of [mcp.json](https://code.visualstudio.com/docs/copilot/chat/mcp-servers#_add-an-mcp-server-to-your-workspace). Create an entry for HooksMCP.

**Note:** Be sure it's run from the root of your project, or manually pass the working directory on startup:

```json
{
  "HooksMCP": {
    "command": "uvx",
    "args": [
      "hooks-mcp",
      "--working-directory",
      "."
    ]
  }
}
```

## Security Features

### Security Benefits

HooksMCP implements several security measures to help improve security of giving agents access to terminal commands:

1. **Allow List of Commands**: Your agents can only run the commands you give it access to in your `hooks_mcp.yaml`, not arbitrary terminal commands.

2. **Path Parameter Validation** All `project_file_path` parameters are validated to ensure they:
   - Are within the project directory
   - Actually exist in the project

3. **Environment Variable Controls**: 
   - `required_env_var` and `optional_env_var` parameters are managed by the developer, not the coding assistant. This prevents coding assistants from accessing sensitive variables.

3. **Safe Command Execution**:
   - Uses Python `subprocess.run` with `shell=False` to prevent shell injection
   - Uses `shlex.split` to properly separate command arguments
   - Implements timeouts to prevent infinite running commands

### Security Risks

There are some risks to using HooksMCP:

1. If your agent can edit your `hooks_mcp.yaml`, it can add commands which it can then run via MCP
 
2. If your agent can add code to your project and any of your actions will invoke arbitrary code (like a test runner), the agent can use this pattern to run arbitrary code

3. HooksMCP may contain bugs or security issues

We don't promise it's perfect, but it's probably better than giving an agent unfettered terminal access. Running inside a container is always recommended for agents.

## Origin Story

I built this for my own use building [Kiln](https://getkiln.ai). The first draft was written by Qwen-Coder-405b, and then it was edited by me. See the [initial commit](https://github.com/scosman/hooks_mcp/commit/62fdd5917a1469b64e9dbad73fd713cb0f2454a5) for the prompt.

## License

MIT