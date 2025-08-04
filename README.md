# ActionsMCP

ActionsMCP is an MCP (Model Context Protocol) server that exposes project-specific development tools (tests, linters, typecheckers, etc.) as standardized functions through a simple YAML configuration file. This allows coding assistants like Cursor, Windsurf, and others to discover and use your project's development tools without requiring manual approval for each command execution.

## Features

- **Standardized Tool Access**: Expose your project's development tools to any MCP-compatible coding assistant
- **Security Focused**: Path validation, environment variable controls, and safe command execution
- **Flexible Configuration**: Define tools with parameters, default values, and execution paths
- **Environment Variable Support**: Load from existing environment or `.env` files
- **Smart Terminal Output**: Processes ANSI codes and control characters for clean responses
- **Easy Deployment**: Install and run with `uvx` for immediate use

## Quick Start

1. Install with uv:
   ```bash
   uv tool install actions-mcp
   ```

2. Create an `actions_mcp.yaml` file in your project root:
   ```yaml
   actions:
     - name: "all_tests"
       description: "Run all tests in the project"
       command: "python -m pytest tests/"
       
     - name: "lint"
       description: "Lint the source code"
       command: "flake8 src/"
       
     - name: "typecheck"
       description: "Typecheck the source code"
       command: "mypy src/"
   ```

3. Run the server:

From your project path:
```bash
uvx actions-mcp
```

From another path:
```bash
uvx actions-mcp --working-directory "/Path/to/your/project"
```

With a non-default config file name or path:
```bash
uvx actions-mcp ./tools/actions_mcp.yaml"
```

## Configuration File Specification

The `actions_mcp.yaml` file defines the tools that will be exposed through the MCP server.

See this project's [actions_mcp.yaml](./actions_mcp.yaml) as an example.

### Top-level Fields

- `server_name` (optional): Name of the MCP server (default: "ActionsMCP")
- `server_description` (optional): Description of the MCP server (default: "Project-specific development tools exposed via MCP")
- `actions` (required): Array of action definitions

### Action Fields

Each action in the `actions` array can have the following fields:

- `name` (required): Unique identifier for the tool
- `description` (required): Human-readable description of what the tool does
- `command` (required): The CLI command to execute. May include dynamic parameters like `$TEST_FILE_PATH`.
- `parameters` (optional): Definitions of each parameter used in the command. 
- `run_path` (optional): Relative path from project root where the command should be executed. Useful for mono-repos.

### Parameter Fields

Each parameter in an action's `parameters` array can have the following fields:

- `name` (required): Parameter name (used as environment variable name in commands)
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

These parameters must be set in the environment before starting the server:

```yaml
- name: "deploy"
  description: "Deploy the application"
  command: "deploy-tool --key=$DEPLOY_KEY"
  parameters:
    - name: "DEPLOY_KEY"
      type: "required_env_var"
      description: "Deployment key for the service"
```

If `DEPLOY_KEY` is not set in the environment, the server will fail to start with a clear error message.

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

Allows any string input from the coding assistant. Use with caution:

```yaml
- name: "grep_code"
  description: "Search code for pattern"
  command: "grep -r $PATTERN src/"
  parameters:
    - name: "PATTERN"
      type: "insecure_string"
      description: "Pattern to search for"
```

## Running with Coding Assistants

### Cursor

1. Open your project in Cursor
2. Go to Settings → Models → MCP Servers
3. Add a new server with the command: `uvx actions-mcp`
4. The coding assistant will now have access to your project's tools

### Windsurf

1. Open your project in Windsurf
2. Configure the MCP server to run: `uvx actions-mcp`
3. Use the tools directly from the coding assistant interface

## Security Features

ActionsMCP implements several security measures to protect your project:

1. **Path Validation**: All `project_file_path` parameters are validated to ensure they:
   - Are within the project boundaries
   - Don't contain directory traversal sequences (`..`, `~`, `$HOME`)
   - Actually exist in the project

2. **Environment Variable Controls**: 
   - `required_env_var` and `optional_env_var` parameters are managed by the developer, not the coding assistant
   - This prevents coding assistants from accessing sensitive variables

3. **Safe Command Execution**:
   - Uses `subprocess.run` with `shell=False` to prevent shell injection
   - Uses `shlex.split` to properly separate command arguments
   - Implements timeouts to prevent infinite running commands

4. **Insecure String Warnings**:
   - Documents the risks of using `insecure_string` parameters
   - Encourages developers to use more secure parameter types when possible

## Example Configuration

Here's a comprehensive example showing all features:

```yaml
server_name: "MyProject Tools"
server_description: "Development tools for MyProject"


actions:
  # Run all tests
  - name: "all_tests"
    description: "Run all tests in the project"
    command: "python -m pytest tests/"
    
  # Run specific tests with a file path parameter
  - name: "test_file"
    description: "Run tests in a specific file"
    command: "python -m pytest $TEST_FILE"
    parameters:
      - name: "TEST_FILE"
        type: "project_file_path"
        description: "Path to test file"
        default: "./tests"
    
  # Lint with optional flags
  - name: "lint"
    description: "Lint the source code"
    command: "flake8 $LINT_FLAGS src/"
    parameters:
      - name: "LINT_FLAGS"
        type: "insecure_string"
        description: "Additional flake8 flags"
        default: ""
    run_path: "src"
    
  # Typecheck that requires an API key
  - name: "typecheck"
    description: "Typecheck the source code"
    command: "mypy src/"
    parameters:
      - name: "MYPY_CACHE_DIR"
        type: "optional_env_var"
        description: "Custom cache directory for mypy"
```

## Development

To run tests:

```bash
uv run python -m unittest discover tests
```

To run the server locally:

```bash
uv run python -m actions_mcp.server
```

## License

MIT
