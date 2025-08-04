import argparse
import os
import sys
from pathlib import Path
from typing import Any, Dict, List

from mcp.server import Server
from mcp.server.stdio import stdio_server
from mcp.types import Tool

from .config import ActionsMCPConfig, ConfigError, ParameterType
from .executor import CommandExecutor, ExecutionError


def create_tool_definitions(config: ActionsMCPConfig) -> List[Tool]:
    """
    Create MCP tool definitions from the ActionsMCP configuration.

    Args:
        config: The ActionsMCP configuration

    Returns:
        List of MCP Tool definitions
    """
    tools = []

    for action in config.actions:
        # Convert action parameters to MCP tool parameters
        parameters = []
        for param in action.parameters:
            # Skip required_env_var and optional_env_var as they're not provided by the client
            if param.type in [
                ParameterType.REQUIRED_ENV_VAR,
                ParameterType.OPTIONAL_ENV_VAR,
            ]:
                continue

            parameters.append(param.to_dict())

        tool = Tool(
            name=action.name,
            description=action.description,
            inputSchema={
                "type": "object",
                "properties": {
                    param["name"]: {
                        "type": "string",
                        "description": param["description"],
                    }
                    for param in parameters
                },
                "required": [
                    param["name"] for param in parameters if "default" not in param
                ],
            },
        )
        tools.append(tool)

    return tools


async def serve(ActionsMCP_config: ActionsMCPConfig) -> None:
    """
    Run the ActionsMCP server.

    Args:
        ActionsMCP_config: The ActionsMCP configuration
    """
    # Create tool definitions
    tools = create_tool_definitions(ActionsMCP_config)

    # Create command executor
    executor = CommandExecutor()

    # Create MCP server
    server = Server(ActionsMCP_config.server_name)

    # Register tools
    @server.list_tools()
    async def list_tools() -> List[Tool]:
        return tools

    @server.call_tool()
    async def call_tool(name: str, arguments: Dict[str, Any]) -> List[Dict[str, Any]]:
        # Find the action by name
        action = next((a for a in ActionsMCP_config.actions if a.name == name), None)
        if not action:
            raise ExecutionError(f"ActionsMCP Error: Action '{name}' not found")

        try:
            # Execute the action
            result = executor.execute_action(action, arguments)

            # Format the result
            output = f"Command executed: {action.command}\n"
            output += f"Status code: {result['status_code']}\n"
            if result["stdout"]:
                output += f"Output:\n{result['stdout']}\n"
            if result["stderr"]:
                output += f"Errors:\n{result['stderr']}\n"

            return [{"type": "text", "text": output}]
        except ExecutionError:
            raise
        except Exception as e:
            raise ExecutionError(
                f"ActionsMCP Error: Unexpected error executing action '{name}': {str(e)}"
            )

    # Set up server capabilities
    server_capabilities = server.create_initialization_options(
        experimental_capabilities={"tools": {"listChanged": True}}
    )

    # Run the server
    async with stdio_server() as (read_stream, write_stream):
        await server.run(
            read_stream, write_stream, server_capabilities, raise_exceptions=True
        )


def main() -> None:
    """Main entry point for the ActionsMCP server."""
    parser = argparse.ArgumentParser(
        description="ActionsMCP - MCP server for project-specific development tools"
    )
    parser.add_argument(
        "config_path",
        nargs="?",
        default="./actions_mcp.yaml",
        help="Path to the ActionsMCP configuration file (default: ./actions_mcp.yaml)",
    )
    parser.add_argument(
        "-wd",
        "--working-directory",
        help="Working directory to use for the server (default: current directory)",
    )

    args = parser.parse_args()

    # Change working directory if specified
    if args.working_directory:
        try:
            os.chdir(args.working_directory)
        except Exception as e:
            print(
                f"ActionsMCP Error: Failed to change working directory to '{args.working_directory}': {str(e)}"
            )
            sys.exit(1)

    # Load configuration
    config_path = Path(args.config_path)
    if not config_path.exists():
        print(f"ActionsMCP Error: Configuration file '{config_path}' not found")
        sys.exit(1)

    try:
        config = ActionsMCPConfig.from_yaml(str(config_path))
    except ConfigError as e:
        print(str(e))
        sys.exit(1)

    # Validate required environment variables
    missing_vars = config.validate_required_env_vars()
    if missing_vars:
        print(
            f"ActionsMCP Error: Required environment variables not set: {', '.join(missing_vars)}"
        )
        print("Please set these variables before running the server.")
        sys.exit(1)

    # Load .env file if it exists
    env_path = config_path.parent / ".env"
    if env_path.exists():
        from dotenv import load_dotenv

        load_dotenv(env_path)

    # Run the server
    try:
        import asyncio

        asyncio.run(serve(config))
    except KeyboardInterrupt:
        print("ActionsMCP server stopped by user")
        sys.exit(0)
    except Exception as e:
        print(f"ActionsMCP Error: Failed to start server: {str(e)}")
        sys.exit(1)


if __name__ == "__main__":
    main()
