import argparse
import os
import sys
from pathlib import Path
from typing import Any, Dict, List

import tomllib
from mcp.server import Server
from mcp.server.stdio import stdio_server
from mcp.types import (
    GetPromptResult,
    Prompt,
    PromptArgument,
    PromptMessage,
    TextContent,
    Tool,
)

from .config import (
    ActionParameter,
    ConfigError,
    HooksMCPConfig,
    ParameterType,
)
from .config import (
    Prompt as ConfigPrompt,
)
from .executor import CommandExecutor, ExecutionError


def create_prompt_definitions(config: HooksMCPConfig) -> List[Prompt]:
    """
    Create MCP prompt definitions from the HooksMCP configuration.

    Args:
        config: The HooksMCP configuration

    Returns:
        List of MCP Prompt definitions
    """
    prompts = []

    for prompt in config.prompts:
        # Convert prompt arguments to MCP prompt arguments
        arguments = [
            PromptArgument(
                name=arg.name,
                description=arg.description,
                required=arg.required,
            )
            for arg in prompt.arguments
        ]

        mcp_prompt = Prompt(
            name=prompt.name,
            description=prompt.description,
            arguments=arguments or None,
        )
        prompts.append(mcp_prompt)

    return prompts


def create_tool_definitions(
    config: HooksMCPConfig, disable_prompt_tool: bool = False
) -> List[Tool]:
    """
    Create MCP tool definitions from the HooksMCP configuration.

    Args:
        config: The HooksMCP configuration
        disable_prompt_tool: If True, don't expose the get_prompt tool

    Returns:
        List of MCP Tool definitions
    """
    tools = []

    for action in config.actions:
        # Convert action parameters to MCP tool parameters
        parameters: List[ActionParameter] = []
        for param in action.parameters:
            # Skip required_env_var and optional_env_var as they're not provided by the client
            if param.type in [
                ParameterType.REQUIRED_ENV_VAR,
                ParameterType.OPTIONAL_ENV_VAR,
            ]:
                continue

            parameters.append(param)

        tool = Tool(
            name=action.name,
            description=action.description,
            inputSchema={
                "type": "object",
                "properties": {
                    param.name: {
                        "type": "string",
                        "description": param.description,
                    }
                    for param in parameters
                },
                "required": [
                    param.name for param in parameters if param.default is None
                ],
            },
        )
        tools.append(tool)

    # Add get_prompt tool if there are prompts and it should be exposed
    if config.prompts and not disable_prompt_tool:
        # Determine which prompts to expose based on get_prompt_tool_filter
        exposed_prompts = config.prompts
        if config.get_prompt_tool_filter is not None:
            # If filter is empty, don't expose the tool at all
            if not config.get_prompt_tool_filter:
                return tools
            # Otherwise, filter prompts by name
            filter_set = set(config.get_prompt_tool_filter)
            exposed_prompts = [p for p in config.prompts if p.name in filter_set]

        # Only add the tool if there are prompts to expose
        if exposed_prompts:
            # Build tool description with list of prompts
            prompt_list_desc = "\n".join(
                [f"- {prompt.name}: {prompt.description}" for prompt in exposed_prompts]
            )
            tool_description = (
                "Get a prompt designed for this codebase. The prompts include:\n"
                f"{prompt_list_desc}"
            )

            # Create enum of prompt names for the tool parameter
            prompt_names = [prompt.name for prompt in exposed_prompts]

            get_prompt_tool = Tool(
                name="get_prompt",
                description=tool_description,
                inputSchema={
                    "type": "object",
                    "properties": {
                        "prompt_name": {
                            "type": "string",
                            "description": "The name of the prompt to retrieve",
                            "enum": prompt_names,
                        }
                    },
                    "required": ["prompt_name"],
                },
            )
            tools.append(get_prompt_tool)

    return tools


def get_prompt_content(config_prompt: ConfigPrompt, config_path: Path) -> str:
    """
    Get the content of a prompt from either the inline text or file.

    Args:
        config_prompt: The prompt configuration
        config_path: Path to the configuration file (used for resolving relative paths)

    Returns:
        The prompt content as a string
    """
    if config_prompt.prompt_text:
        return config_prompt.prompt_text
    elif config_prompt.prompt_file:
        prompt_file_path = config_path.parent / config_prompt.prompt_file
        try:
            with open(prompt_file_path, "r") as f:
                return f.read()
        except Exception as e:
            raise ExecutionError(
                f"HooksMCP Error: Failed to read prompt file '{config_prompt.prompt_file}': {str(e)}"
            )
    else:
        raise ExecutionError(
            f"HooksMCP Error: Prompt '{config_prompt.name}' has no content"
        )


async def serve(
    hooks_mcp_config: HooksMCPConfig,
    config_path: Path,
    disable_prompt_tool: bool = False,
) -> None:
    """
    Run the HooksMCP server.

    Args:
        hooks_mcp_config: The HooksMCP configuration
    """
    # Create tool definitions
    tools = create_tool_definitions(hooks_mcp_config, disable_prompt_tool)

    # Create prompt definitions
    prompts = create_prompt_definitions(hooks_mcp_config)

    # Create command executor
    executor = CommandExecutor()

    # Create MCP server
    server = Server(hooks_mcp_config.server_name)

    # Register tools
    @server.list_tools()
    async def list_tools() -> List[Tool]:
        return tools

    @server.call_tool()
    async def call_tool(name: str, arguments: Dict[str, Any]) -> List[TextContent]:
        # Handle get_prompt tool specially
        if name == "get_prompt":
            prompt_name = arguments.get("prompt_name")
            if not prompt_name:
                raise ExecutionError(
                    "HooksMCP Error: 'prompt_name' argument is required for get_prompt tool"
                )

            # Enforce get_prompt_tool_filter if present
            if hooks_mcp_config.get_prompt_tool_filter is not None:
                # If filter is empty, don't allow any prompts (shouldn't happen since tool isn't exposed)
                if not hooks_mcp_config.get_prompt_tool_filter:
                    raise ExecutionError(
                        "HooksMCP Error: No prompts are available through get_prompt tool"
                    )
                # Otherwise, check if prompt is in the filter list
                if prompt_name not in hooks_mcp_config.get_prompt_tool_filter:
                    available_prompts = ", ".join(
                        hooks_mcp_config.get_prompt_tool_filter
                    )
                    raise ExecutionError(
                        f"HooksMCP Error: Prompt '{prompt_name}' is not available through get_prompt tool. "
                        f"Available prompts: {available_prompts}"
                    )

            # Find the prompt by name
            config_prompt = next(
                (p for p in hooks_mcp_config.prompts if p.name == prompt_name), None
            )
            if not config_prompt:
                raise ExecutionError(
                    f"HooksMCP Error: Prompt '{prompt_name}' not found"
                )

            # Get prompt content
            prompt_content = get_prompt_content(config_prompt, config_path)

            # Return the prompt content as text
            return [TextContent(type="text", text=prompt_content)]

        # Find the action by name
        action = next((a for a in hooks_mcp_config.actions if a.name == name), None)
        if not action:
            raise ExecutionError(f"HooksMCP Error: Action '{name}' not found")

        try:
            # Execute the action
            result = executor.execute_action(action, arguments)

            # Format the result
            output = f"Command executed: {action.command}\n"
            output += f"Exit code: {result['status_code']}\n"
            if result["stdout"]:
                output += f"STDOUT:\n{result['stdout']}\n"
            if result["stderr"]:
                output += f"STDERR:\n{result['stderr']}\n"

            return [TextContent(type="text", text=output)]
        except ExecutionError:
            raise
        except Exception as e:
            raise ExecutionError(
                f"HooksMCP Error: Unexpected error executing action '{name}': {str(e)}"
            )

    # Register prompts if any exist
    if prompts:

        @server.list_prompts()
        async def list_prompts() -> List[Prompt]:
            return prompts

        @server.get_prompt()
        async def get_prompt(
            name: str, arguments: Dict[str, Any] | None = None
        ) -> GetPromptResult:
            # Find the prompt by name
            config_prompt = next(
                (p for p in hooks_mcp_config.prompts if p.name == name), None
            )
            if not config_prompt:
                raise ExecutionError(f"HooksMCP Error: Prompt '{name}' not found")

            # Get prompt content
            prompt_content = get_prompt_content(config_prompt, config_path)

            # Substitute arguments if provided
            if arguments:
                # Use simple string replacement for {{variable}} templates
                for arg_name, arg_value in arguments.items():
                    template_var = f"{{{{{arg_name}}}}}"
                    prompt_content = prompt_content.replace(
                        template_var, str(arg_value)
                    )

            # Return as GetPromptResult
            return GetPromptResult(
                description=config_prompt.description,
                messages=[
                    PromptMessage(
                        role="user",
                        content=TextContent(type="text", text=prompt_content),
                    )
                ],
            )

    # Set up server capabilities
    server_capabilities = server.create_initialization_options(
        experimental_capabilities={
            "tools": {"listChanged": True},
            "prompts": {"listChanged": True},
        }
    )

    # Run the server
    async with stdio_server() as (read_stream, write_stream):
        await server.run(
            read_stream, write_stream, server_capabilities, raise_exceptions=True
        )


def get_version() -> str:
    """Get the version from pyproject.toml file."""
    try:
        with open("pyproject.toml", "rb") as f:
            data = tomllib.load(f)
            version = data["project"]["version"]
            return f"hooks-mcp {version}"
    except Exception:
        # Fallback to a default version if we can't read it
        return "hooks-mcp: cannot load version"


def main() -> None:
    """Main entry point for the HooksMCP server."""
    parser = argparse.ArgumentParser(
        description="HooksMCP - MCP server for project-specific development tools and prompts",
        epilog="For more information, visit: https://github.com/scosman/hooks_mcp",
    )
    parser.add_argument(
        "-v",
        "--version",
        action="version",
        version=get_version(),
        help="Show the library version",
    )
    parser.add_argument(
        "config_path",
        nargs="?",
        default="./hooks_mcp.yaml",
        help="Path to the HooksMCP configuration file (default: ./hooks_mcp.yaml)",
    )
    parser.add_argument(
        "-wd",
        "--working-directory",
        help="Working directory to use for the server (default: current directory)",
    )
    parser.add_argument(
        "--disable-prompt-tool",
        action="store_true",
        help="Disable the get_prompt tool entirely, similar to setting get_prompt_tool_filter to an empty array",
    )

    args = parser.parse_args()

    # Change working directory if specified
    if args.working_directory:
        try:
            os.chdir(args.working_directory)
        except Exception as e:
            print(
                f"HooksMCP Error: Failed to change working directory to '{args.working_directory}': {str(e)}"
            )
            sys.exit(1)

    # Load configuration
    config_path = Path(args.config_path)
    if not config_path.exists():
        print(f"HooksMCP Error: Configuration file '{config_path}' not found")
        sys.exit(1)

    try:
        config = HooksMCPConfig.from_yaml(str(config_path))
    except ConfigError as e:
        print(str(e))
        sys.exit(1)

    # Validate required environment variables
    missing_vars = config.validate_required_env_vars()
    if missing_vars:
        print(
            f"HooksMCP Error: Required environment variables not set: {', '.join(missing_vars)}"
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

        asyncio.run(serve(config, config_path, args.disable_prompt_tool))
    except KeyboardInterrupt:
        print("HooksMCP server stopped by user")
        sys.exit(0)
    except Exception as e:
        print(f"HooksMCP Error: Failed to start server: {str(e)}")
        sys.exit(1)


if __name__ == "__main__":
    main()
