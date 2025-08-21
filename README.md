<p align="center">
  <picture>
    <img width="302" height="79" alt="hooksMCP" src="https://github.com/user-attachments/assets/555412a4-70a3-4a9c-89f7-579b7a3d4205" />
  </picture>
</p>
<h3 align="center">
  One YAML to create a MCP server for your lint/test/build commands and prompts
</h3>

## Overview

1. **Simple setup:** one YAML file is all it takes to create a custom MCP server for your coding agents. Similar to package.json scripts or Github Actions workflows, but commands are triggered by MCP functions. 
2. **Tool discovery:** coding agents know which dev-tools are available and the exact arguments they require. No more guessing CLI strings.
3. **Improved security:** limit which commands agents can run. Validate the arguments agents generate (e.g. ensure a file path is inside the project).
4. **Works anywhere MCP works:** Cursor, Windsurf, Cline, etc
5. **Prompt Library** provide access to shared prompts in a standard way. Solves that Cursor/Cline/Codex all have different search paths/filenames.
6. **Speed:** using MCP unlocks parallel execution, requires fewer tokens for generating commands, and eliminates errors in commands requiring iteration.
7. **Collaboration**: Check in the YAML file to share with your team.
8. **And more:** strip ANSI codes/control characters, `.env` file loading, define required secrets without checking them in, supports exit codes/stdout/stderr, etc

<p align="center">
<img width="293" height="299" alt="Screenshot 2025-08-05 at 12 08 20 AM" src="https://github.com/user-attachments/assets/b7352ab4-d212-45f0-8267-67bc7209eb5b" />
</p>

[![All Checks](https://github.com/scosman/hooks_mcp/actions/workflows/all-checks.yml/badge.svg)](https://github.com/scosman/hooks_mcp/actions/workflows/all-checks.yml)

## Quick Start

1. Install with [uv](https://docs.astral.sh/uv/concepts/tools/):

```bash
uv tool install hooks-mcp
```

2. Create an [`hooks_mcp.yaml`](#configuration-file-specification) file in your project root defining your tools and prompts. For example:

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

prompts:
  - name: "test_guide.md"
    description: "Guide for testing best practices in this library"
    prompt-file: "agents/test_guide.md"

```

3. Run the server:

```bash
uvx hooks-mcp
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
 - `--disable-prompt-tool`: Disable the `get_prompt` tool entirely, similar to setting `get_prompt_tool_filter` to an empty array.
 - The last argument is the path to the `hooks_mcp.yaml` file, if not using the default `./hooks_mcp.yaml`

### Running with Coding Assistants

#### Cursor

[![Install MCP Server](https://cursor.com/deeplink/mcp-install-dark.svg)](https://cursor.com/en/install-mcp?name=HooksMCP&config=eyJjb21tYW5kIjoidXZ4IGhvb2tzLW1jcCAtLXdvcmtpbmctZGlyZWN0b3J5IC4ifQ%3D%3D)

Or open [this cursor deeplink](cursor://anysphere.cursor-deeplink/mcp/install?name=HooksMCP&config=eyJjb21tYW5kIjoidXZ4IGhvb2tzLW1jcCAtLXdvcmtpbmctZGlyZWN0b3J5IC4ifQ).

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

## Configuration File Specification

The `hooks_mcp.yaml` file defines the tools that will be exposed through the MCP server.

See this project's [hooks_mcp.yaml](./hooks_mcp.yaml) as an example.

### Top-level Fields

- `server_name` (optional): Name of the MCP server (default: "HooksMCP")
- `server_description` (optional): Description of the MCP server (default: "Project-specific development tools and prompts exposed via MCP")
- [`actions`](#action-fields) (optional): Array of action definitions. If not provided, only prompts will be available.
- [`prompts`](#prompt-fields) (optional): Array of prompt definitions
- [`get_prompt_tool_filter`](#how-prompts-are-exposed-via-mcp) (optional): Array of prompt names to expose via the `get_prompt` tool. If unset, all prompts are exposed. If empty, the `get_prompt` tool is not exposed.

### Action Fields

Each action in the `actions` array can have the following fields:

- `name` (required): Unique identifier for the tool
- `description` (required): Human-readable description of what the tool does
- `command` (required): The CLI command to execute. May include dynamic parameters like `$TEST_FILE_PATH`.
- [`parameters`](#action-parameter-fields) (optional): Definitions of each parameter used in the command.
- `run_path` (optional): Relative path from project root where the command should be executed. Useful for mono-repos.
- `timeout` (optional): Timeout in seconds for command execution (default: 60 seconds)

### Action Parameter Fields

Each parameter in an action's `parameters` array can have the following fields:

- `name` (required): The parameter name to substitute into the command. For example `TEST_FILE_PATH`.
- `type` (required): One of the following parameter types:
  - [`project_file_path`](#project_file_path): A local path within the project, relative to project root.
  - [`insecure_string`](#insecure_string): Any string from the model. No validation. Use with caution. 
  - [`required_env_var`](#required_env_var): An environment variable that must be set before the server starts. 
  - [`optional_env_var`](#optional_env_var) : An optional environment variable. Not specified by the calling model.
- `description` (optional): description of the parameter
- `default` (optional): Default value for the parameter if not passed

### Tool Parameter Examples

#### project_file_path

This parameter type ensures security by validating that the path parameter is within the project boundaries:

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

#### insecure_string

Allows any string input from the agent without validation. Use with caution:

```yaml
- name: "grep_code"
  description: "Search code for pattern"
  command: "grep -r $PATTERN src/"
  parameters:
    - name: "PATTERN"
      type: "insecure_string"
      description: "Pattern to search for"
```

#### required_env_var

This is a tool parameter expected to exist as an environment variable. The server will fail to start if the environment is missing this var.

This is useful for specifying that a secret (e.g., API key) is needed, without checking the value into your repository. Typically set up when you configure your MCP server (in `mcp.json` and similar). When trying to set up the MCP server, it will output a user‑friendly message informing the user they need to add the env var to continue.

HooksMCP will load env vars from the environment, and any set in a `.env` file in your working directory.

This cannot be passed by the calling model.

```yaml
- name: "deploy"
  description: "Deploy the application"
  command: "deploy-tool --key=$DEPLOY_KEY"
  parameters:
    - name: "DEPLOY_KEY"
      type: "required_env_var"
      description: "Deployment key for the service"
```

#### optional_env_var

Similar to `required_env_var` but optional. The server will not error on startup if this is missing.

```yaml
- name: "build"
  description: "Build the application"
  command: "build-tool"
  parameters:
    - name: "BUILD_FLAGS"
      type: "optional_env_var"
      description: "Additional build flags"
```

### Prompt Fields

HooksMCP can be used to share prompts. For example, a "test_guide" prompt explaining preferred test libraries and best practices for tests.

Each prompt in the `prompts` array can have the following fields:

- `name` (required): Unique identifier for the prompt (max 32 characters)
- `description` (required): description of what the prompt does (max 256 characters)
- `prompt` (optional): Inline prompt text content. Either `prompt` or `prompt-file` must be specified.
- `prompt-file` (optional): Relative path to a file containing the prompt text content. Either `prompt` or `prompt-file` must be specified.
- [`arguments`](#prompt-argument-fields) (optional): Definitions of each argument used in the prompt.

#### Prompt Argument Fields

Each argument in a prompt's `arguments` array can have the following fields:

- `name` (required): The argument name
- `description` (optional): description of the argument
- `required` (optional): Boolean indicating if the argument is required (default: false)

To add a prompt in your template, include it in double curly brackets: `{{CODE_SNIPPET}}`

#### Prompt Examples

Prompts can be defined inline or loaded from files:

```yaml
prompts:
  - name: "code_review"
    description: "Review code for best practices and potential bugs"
    prompt: "Please review this code for best practices and potential bugs:\n\n$CODE_SNIPPET"
    arguments:
      - name: "CODE_SNIPPET"
        description: "The code to review"
        required: true

  - name: "architecture_review"
    description: "Review system architecture decisions"
    prompt-file: "./prompts/architecture_review.md"
```

#### How Prompts are Exposed via MCP

The MCP protocol supports prompts natively; HooksMCP will provide prompts through the official protocol.

However, many clients only support MCP for tool calls. They either completely ignore prompts, or only expose prompts via a dropdown requiring manual human selection. For these clients, we also expose a MCP tool called `get_prompt`. This tool automatically enabled when prompts are defined, allowing coding agents to retrieve prompt content by name. **Note**: the get_prompt tool does not support argument substitution. The model will have to infer how to use the prompt from it's template.

To disable the `get_prompt` tool you can set:
1. Use the `--disable-prompt-tool` CLI argument. This is local to each user.
2. set `get_prompt_tool_filter` in the yaml to limit which prompts are exposed, with an empty list disabling the tool. This is for all users.

```yaml
get_prompt_tool_filter:
  - "code_review"
  - "architecture_review"
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
