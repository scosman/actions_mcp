import asyncio
import tempfile
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from hooks_mcp.config import (
    Action,
    ActionParameter,
    ConfigError,
    HooksMCPConfig,
    ParameterType,
)
from hooks_mcp.config import (
    Prompt as ConfigPrompt,
)
from hooks_mcp.config import (
    PromptArgument as ConfigPromptArgument,
)
from hooks_mcp.executor import ExecutionError
from hooks_mcp.server import (
    create_prompt_definitions,
    create_tool_definitions,
    get_prompt_content,
    main,
    serve,
)


class TestCreateToolDefinitions:
    """Test the create_tool_definitions function."""

    def test_empty_config(self):
        """Test creating tool definitions from empty config."""
        config = HooksMCPConfig(
            server_name="TestServer", server_description="Test Description", actions=[]
        )

        tools = create_tool_definitions(config)

        assert tools == []

    def test_single_action_no_parameters(self):
        """Test creating tool definition for single action without parameters."""
        action = Action(
            name="test_action",
            description="Test action description",
            command="echo hello",
        )
        config = HooksMCPConfig(
            server_name="TestServer",
            server_description="Test Description",
            actions=[action],
        )

        tools = create_tool_definitions(config)

        assert len(tools) == 1
        tool = tools[0]
        assert tool.name == "test_action"
        assert tool.description == "Test action description"
        assert tool.inputSchema == {"type": "object", "properties": {}, "required": []}

    def test_action_with_client_parameters(self):
        """Test creating tool definition for action with client parameters."""
        parameters = [
            ActionParameter(
                "FILE_PATH", ParameterType.PROJECT_FILE_PATH, "Path to file"
            ),
            ActionParameter(
                "MESSAGE",
                ParameterType.INSECURE_STRING,
                "Message to display",
                "default_msg",
            ),
        ]
        action = Action(
            name="test_action",
            description="Test action description",
            command="echo $MESSAGE",
            parameters=parameters,
        )
        config = HooksMCPConfig(
            server_name="TestServer",
            server_description="Test Description",
            actions=[action],
        )

        tools = create_tool_definitions(config)

        assert len(tools) == 1
        tool = tools[0]
        assert tool.name == "test_action"
        assert tool.description == "Test action description"

        expected_properties = {
            "FILE_PATH": {"type": "string", "description": "Path to file"},
            "MESSAGE": {"type": "string", "description": "Message to display"},
        }
        assert tool.inputSchema["properties"] == expected_properties
        assert tool.inputSchema["required"] == [
            "FILE_PATH"
        ]  # MESSAGE has default, so not required

    def test_action_filters_env_var_parameters(self):
        """Test that env var parameters are filtered out from tool definition."""
        parameters = [
            ActionParameter(
                "FILE_PATH", ParameterType.PROJECT_FILE_PATH, "Path to file"
            ),
            ActionParameter("API_KEY", ParameterType.REQUIRED_ENV_VAR, "API key"),
            ActionParameter(
                "OPTIONAL_VAR", ParameterType.OPTIONAL_ENV_VAR, "Optional variable"
            ),
            ActionParameter(
                "MESSAGE", ParameterType.INSECURE_STRING, "Message to display"
            ),
        ]
        action = Action(
            name="test_action",
            description="Test action description",
            command="echo $MESSAGE",
            parameters=parameters,
        )
        config = HooksMCPConfig(
            server_name="TestServer",
            server_description="Test Description",
            actions=[action],
        )

        tools = create_tool_definitions(config)

        assert len(tools) == 1
        tool = tools[0]

        # Should only include non-env-var parameters
        expected_properties = {
            "FILE_PATH": {"type": "string", "description": "Path to file"},
            "MESSAGE": {"type": "string", "description": "Message to display"},
        }
        assert tool.inputSchema["properties"] == expected_properties
        assert tool.inputSchema["required"] == [
            "FILE_PATH",
            "MESSAGE",
        ]  # Both have no defaults

    def test_multiple_actions(self):
        """Test creating tool definitions for multiple actions."""
        action1 = Action(
            name="action1", description="First action", command="echo hello"
        )
        action2 = Action(
            name="action2",
            description="Second action",
            command="ls -la",
            parameters=[
                ActionParameter("PATH", ParameterType.PROJECT_FILE_PATH, "Path to list")
            ],
        )
        config = HooksMCPConfig(
            server_name="TestServer",
            server_description="Test Description",
            actions=[action1, action2],
        )

        tools = create_tool_definitions(config)

        assert len(tools) == 2

        # Check first tool
        assert tools[0].name == "action1"
        assert tools[0].description == "First action"
        assert tools[0].inputSchema["properties"] == {}

        # Check second tool
        assert tools[1].name == "action2"
        assert tools[1].description == "Second action"
        assert "PATH" in tools[1].inputSchema["properties"]

    def test_create_tool_definitions_with_prompts(self):
        """Test creating tool definitions when prompts are present."""
        prompt1 = ConfigPrompt(
            name="code_review",
            description="Review code for best practices",
            prompt_text="Please review this code for best practices and potential bugs.",
        )
        prompt2 = ConfigPrompt(
            name="test_generation",
            description="Generate unit tests for code",
            prompt_text="Generate unit tests for the following code:\n$CODE_SNIPPET",
        )
        action = Action(
            name="test_action",
            description="Test action description",
            command="echo hello",
        )
        config = HooksMCPConfig(
            server_name="TestServer",
            server_description="Test Description",
            actions=[action],
            prompts=[prompt1, prompt2],
        )

        tools = create_tool_definitions(config)

        # Should have the action tool plus the get_prompt tool
        assert len(tools) == 2

        # First tool should be the action
        assert tools[0].name == "test_action"
        assert tools[0].description == "Test action description"

        # Second tool should be get_prompt
        get_prompt_tool = tools[1]
        assert get_prompt_tool.name == "get_prompt"
        assert get_prompt_tool.description is not None
        assert "Review code for best practices" in get_prompt_tool.description
        assert "Generate unit tests for code" in get_prompt_tool.description

        # Check that the input schema has the correct properties
        assert "prompt_name" in get_prompt_tool.inputSchema["properties"]
        assert (
            get_prompt_tool.inputSchema["properties"]["prompt_name"]["type"] == "string"
        )
        assert "enum" in get_prompt_tool.inputSchema["properties"]["prompt_name"]
        assert set(
            get_prompt_tool.inputSchema["properties"]["prompt_name"]["enum"]
        ) == {"code_review", "test_generation"}
        assert get_prompt_tool.inputSchema["required"] == ["prompt_name"]

    def test_create_tool_definitions_with_prompt_filter(self):
        """Test creating tool definitions with get_prompt_tool_filter."""
        prompt1 = ConfigPrompt(
            name="code_review",
            description="Review code for best practices",
            prompt_text="Please review this code for best practices and potential bugs.",
        )
        prompt2 = ConfigPrompt(
            name="test_generation",
            description="Generate unit tests for code",
            prompt_text="Generate unit tests for the following code:\n$CODE_SNIPPET",
        )
        action = Action(
            name="test_action",
            description="Test action description",
            command="echo hello",
        )
        config = HooksMCPConfig(
            server_name="TestServer",
            server_description="Test Description",
            actions=[action],
            prompts=[prompt1, prompt2],
            get_prompt_tool_filter=["code_review"],
        )

        tools = create_tool_definitions(config)

        # Should have the action tool plus the get_prompt tool
        assert len(tools) == 2

        # Second tool should be get_prompt
        get_prompt_tool = tools[1]
        assert get_prompt_tool.name == "get_prompt"
        assert get_prompt_tool.description is not None
        assert "Review code for best practices" in get_prompt_tool.description
        assert "Generate unit tests for code" not in get_prompt_tool.description

        # Check that the input schema has the correct properties
        assert "prompt_name" in get_prompt_tool.inputSchema["properties"]
        assert (
            get_prompt_tool.inputSchema["properties"]["prompt_name"]["type"] == "string"
        )
        assert "enum" in get_prompt_tool.inputSchema["properties"]["prompt_name"]
        assert get_prompt_tool.inputSchema["properties"]["prompt_name"]["enum"] == [
            "code_review"
        ]
        assert get_prompt_tool.inputSchema["required"] == ["prompt_name"]

    def test_create_tool_definitions_with_empty_prompt_filter(self):
        """Test creating tool definitions with empty get_prompt_tool_filter."""
        prompt1 = ConfigPrompt(
            name="code_review",
            description="Review code for best practices",
            prompt_text="Please review this code for best practices and potential bugs.",
        )
        action = Action(
            name="test_action",
            description="Test action description",
            command="echo hello",
        )
        config = HooksMCPConfig(
            server_name="TestServer",
            server_description="Test Description",
            actions=[action],
            prompts=[prompt1],
            get_prompt_tool_filter=[],
        )

        tools = create_tool_definitions(config)

        # Should only have the action tool, not the get_prompt tool
        assert len(tools) == 1
        assert tools[0].name == "test_action"


class TestServe:
    """Test the serve function."""

    @pytest.fixture
    def mock_config(self):
        """Create a mock configuration for testing."""
        action = Action(
            name="test_action", description="Test action", command="echo hello"
        )
        return HooksMCPConfig(
            server_name="TestServer",
            server_description="Test Description",
            actions=[action],
        )

    @patch("hooks_mcp.server.stdio_server")
    @patch("hooks_mcp.server.Server")
    @patch("hooks_mcp.server.CommandExecutor")
    def test_serve_setup(
        self, mock_executor_class, mock_server_class, mock_stdio_server, mock_config
    ):
        """Test that serve function sets up components correctly."""
        # Mock the context manager and server
        mock_read_stream = MagicMock()
        mock_write_stream = MagicMock()
        mock_stdio_server.return_value.__aenter__.return_value = (
            mock_read_stream,
            mock_write_stream,
        )

        mock_server = MagicMock()
        mock_server.create_initialization_options.return_value = {"test": "options"}
        mock_server.run = AsyncMock()
        mock_server_class.return_value = mock_server

        mock_executor = MagicMock()
        mock_executor_class.return_value = mock_executor

        # Create a mock config path
        mock_config_path = Path(".")

        # Run the serve function
        asyncio.run(serve(mock_config, mock_config_path))

        # Verify server was created with correct name
        mock_server_class.assert_called_once_with("TestServer")

        # Verify executor was created
        mock_executor_class.assert_called_once()

        # Verify server.run was called with correct parameters
        mock_server.run.assert_called_once_with(
            mock_read_stream,
            mock_write_stream,
            {"test": "options"},
            raise_exceptions=True,
        )

    @patch("hooks_mcp.server.stdio_server")
    @patch("hooks_mcp.server.Server")
    @patch("hooks_mcp.server.CommandExecutor")
    def test_list_tools_handler(
        self, mock_executor_class, mock_server_class, mock_stdio_server, mock_config
    ):
        """Test that the list_tools handler returns correct tools."""
        # Setup mocks
        mock_stdio_server.return_value.__aenter__.return_value = (
            MagicMock(),
            MagicMock(),
        )
        mock_server = MagicMock()
        mock_server.create_initialization_options.return_value = {}
        mock_server.run = AsyncMock()
        mock_server_class.return_value = mock_server

        # Capture the registered handlers
        registered_handlers = {}

        def capture_list_tools():
            def decorator(func):
                registered_handlers["list_tools"] = func
                return func

            return decorator

        def capture_call_tool():
            def decorator(func):
                registered_handlers["call_tool"] = func
                return func

            return decorator

        mock_server.list_tools = capture_list_tools
        mock_server.call_tool = capture_call_tool

        # Create a mock config path
        mock_config_path = Path(".")

        # Run serve to register handlers
        asyncio.run(serve(mock_config, mock_config_path))

        # Test the list_tools handler
        tools = asyncio.run(registered_handlers["list_tools"]())

        assert len(tools) == 1
        assert tools[0].name == "test_action"
        assert tools[0].description == "Test action"

    @patch("hooks_mcp.server.stdio_server")
    @patch("hooks_mcp.server.Server")
    @patch("hooks_mcp.server.CommandExecutor")
    def test_call_tool_handler_success(
        self, mock_executor_class, mock_server_class, mock_stdio_server, mock_config
    ):
        """Test successful tool execution via call_tool handler."""
        # Setup mocks
        mock_stdio_server.return_value.__aenter__.return_value = (
            MagicMock(),
            MagicMock(),
        )
        mock_server = MagicMock()
        mock_server.create_initialization_options.return_value = {}
        mock_server.run = AsyncMock()
        mock_server_class.return_value = mock_server

        mock_executor = MagicMock()
        mock_executor.execute_action.return_value = {
            "status_code": 0,
            "stdout": "Hello World",
            "stderr": "",
        }
        mock_executor_class.return_value = mock_executor

        # Capture handlers
        registered_handlers = {}

        def capture_list_tools():
            def decorator(func):
                registered_handlers["list_tools"] = func
                return func

            return decorator

        def capture_call_tool():
            def decorator(func):
                registered_handlers["call_tool"] = func
                return func

            return decorator

        mock_server.list_tools = capture_list_tools
        mock_server.call_tool = capture_call_tool

        # Create a mock config path
        mock_config_path = Path(".")

        # Run serve to register handlers
        asyncio.run(serve(mock_config, mock_config_path))

        # Test the call_tool handler
        result = asyncio.run(
            registered_handlers["call_tool"]("test_action", {"test": "args"})
        )

        # Verify executor was called correctly
        mock_executor.execute_action.assert_called_once_with(
            mock_config.actions[0], {"test": "args"}
        )

        # Verify result format
        assert len(result) == 1
        assert result[0].type == "text"
        assert "Command executed: echo hello" in result[0].text
        assert "Exit code: 0" in result[0].text
        assert "STDOUT:\nHello World" in result[0].text

    @patch("hooks_mcp.server.stdio_server")
    @patch("hooks_mcp.server.Server")
    @patch("hooks_mcp.server.CommandExecutor")
    def test_call_tool_handler_action_not_found(
        self, mock_executor_class, mock_server_class, mock_stdio_server, mock_config
    ):
        """Test call_tool handler with non-existent action."""
        # Setup mocks
        mock_stdio_server.return_value.__aenter__.return_value = (
            MagicMock(),
            MagicMock(),
        )
        mock_server = MagicMock()
        mock_server.create_initialization_options.return_value = {}
        mock_server.run = AsyncMock()
        mock_server_class.return_value = mock_server

        # Capture handlers
        registered_handlers = {}

        def capture_list_tools():
            def decorator(func):
                registered_handlers["list_tools"] = func
                return func

            return decorator

        def capture_call_tool():
            def decorator(func):
                registered_handlers["call_tool"] = func
                return func

            return decorator

        mock_server.list_tools = capture_list_tools
        mock_server.call_tool = capture_call_tool

        # Create a mock config path
        mock_config_path = Path(".")

        # Run serve to register handlers
        asyncio.run(serve(mock_config, mock_config_path))

        # Test the call_tool handler with non-existent action
        with pytest.raises(ExecutionError) as exc_info:
            asyncio.run(registered_handlers["call_tool"]("nonexistent_action", {}))

        assert "Action 'nonexistent_action' not found" in str(exc_info.value)

    @patch("hooks_mcp.server.stdio_server")
    @patch("hooks_mcp.server.Server")
    @patch("hooks_mcp.server.CommandExecutor")
    def test_call_tool_handler_execution_error(
        self, mock_executor_class, mock_server_class, mock_stdio_server, mock_config
    ):
        """Test call_tool handler when executor raises ExecutionError."""
        # Setup mocks
        mock_stdio_server.return_value.__aenter__.return_value = (
            MagicMock(),
            MagicMock(),
        )
        mock_server = MagicMock()
        mock_server.create_initialization_options.return_value = {}
        mock_server.run = AsyncMock()
        mock_server_class.return_value = mock_server

        mock_executor = MagicMock()
        mock_executor.execute_action.side_effect = ExecutionError(
            "Test execution error"
        )
        mock_executor_class.return_value = mock_executor

        # Capture handlers
        registered_handlers = {}

        def capture_list_tools():
            def decorator(func):
                registered_handlers["list_tools"] = func
                return func

            return decorator

        def capture_call_tool():
            def decorator(func):
                registered_handlers["call_tool"] = func
                return func

            return decorator

        mock_server.list_tools = capture_list_tools
        mock_server.call_tool = capture_call_tool

        # Create a mock config path
        mock_config_path = Path(".")

        # Run serve to register handlers
        asyncio.run(serve(mock_config, mock_config_path))

        # Test the call_tool handler
        with pytest.raises(ExecutionError) as exc_info:
            asyncio.run(registered_handlers["call_tool"]("test_action", {}))

        assert "Test execution error" in str(exc_info.value)

    @patch("hooks_mcp.server.stdio_server")
    @patch("hooks_mcp.server.Server")
    @patch("hooks_mcp.server.CommandExecutor")
    def test_call_tool_handler_unexpected_error(
        self, mock_executor_class, mock_server_class, mock_stdio_server, mock_config
    ):
        """Test call_tool handler when executor raises unexpected error."""
        # Setup mocks
        mock_stdio_server.return_value.__aenter__.return_value = (
            MagicMock(),
            MagicMock(),
        )
        mock_server = MagicMock()
        mock_server.create_initialization_options.return_value = {}
        mock_server.run = AsyncMock()
        mock_server_class.return_value = mock_server

        mock_executor = MagicMock()
        mock_executor.execute_action.side_effect = ValueError("Unexpected error")
        mock_executor_class.return_value = mock_executor

        # Capture handlers
        registered_handlers = {}

        def capture_list_tools():
            def decorator(func):
                registered_handlers["list_tools"] = func
                return func

            return decorator

        def capture_call_tool():
            def decorator(func):
                registered_handlers["call_tool"] = func
                return func

            return decorator

        mock_server.list_tools = capture_list_tools
        mock_server.call_tool = capture_call_tool

        # Create a mock config path
        mock_config_path = Path(".")

        # Run serve to register handlers
        asyncio.run(serve(mock_config, mock_config_path))

        # Test the call_tool handler
        with pytest.raises(ExecutionError) as exc_info:
            asyncio.run(registered_handlers["call_tool"]("test_action", {}))

        assert (
            "Unexpected error executing action 'test_action': Unexpected error"
            in str(exc_info.value)
        )

    @patch("hooks_mcp.server.stdio_server")
    @patch("hooks_mcp.server.Server")
    @patch("hooks_mcp.server.CommandExecutor")
    def test_list_prompts_handler(
        self, mock_executor_class, mock_server_class, mock_stdio_server, mock_config
    ):
        """Test that the list_prompts handler returns correct prompts."""
        # Add prompts to the mock config
        prompt1 = ConfigPrompt(
            name="test_prompt1",
            description="Test prompt 1 description",
            prompt_text="Test prompt 1 content",
        )
        prompt2 = ConfigPrompt(
            name="test_prompt2",
            description="Test prompt 2 description",
            prompt_file="./test_file.md",
        )
        mock_config.prompts = [prompt1, prompt2]

        # Setup mocks
        mock_stdio_server.return_value.__aenter__.return_value = (
            MagicMock(),
            MagicMock(),
        )
        mock_server = MagicMock()
        mock_server.create_initialization_options.return_value = {}
        mock_server.run = AsyncMock()
        mock_server_class.return_value = mock_server

        # Capture the registered handlers
        registered_handlers = {}

        def capture_list_tools():
            def decorator(func):
                registered_handlers["list_tools"] = func
                return func

            return decorator

        def capture_call_tool():
            def decorator(func):
                registered_handlers["call_tool"] = func
                return func

            return decorator

        def capture_list_prompts():
            def decorator(func):
                registered_handlers["list_prompts"] = func
                return func

            return decorator

        def capture_get_prompt():
            def decorator(func):
                registered_handlers["get_prompt"] = func
                return func

            return decorator

        mock_server.list_tools = capture_list_tools
        mock_server.call_tool = capture_call_tool
        mock_server.list_prompts = capture_list_prompts
        mock_server.get_prompt = capture_get_prompt

        # Create a mock config path
        mock_config_path = Path(".")

        # Run serve to register handlers
        asyncio.run(serve(mock_config, mock_config_path))

        # Test the list_prompts handler
        prompts = asyncio.run(registered_handlers["list_prompts"]())

        assert len(prompts) == 2
        assert prompts[0].name == "test_prompt1"
        assert prompts[1].name == "test_prompt2"

    @patch("hooks_mcp.server.stdio_server")
    @patch("hooks_mcp.server.Server")
    @patch("hooks_mcp.server.CommandExecutor")
    def test_get_prompt_handler_success(
        self, mock_executor_class, mock_server_class, mock_stdio_server, mock_config
    ):
        """Test successful prompt retrieval via get_prompt handler."""
        # Add a prompt to the mock config
        prompt = ConfigPrompt(
            name="test_prompt",
            description="Test prompt description",
            prompt_text="Test prompt content",
        )
        mock_config.prompts = [prompt]

        # Setup mocks
        mock_stdio_server.return_value.__aenter__.return_value = (
            MagicMock(),
            MagicMock(),
        )
        mock_server = MagicMock()
        mock_server.create_initialization_options.return_value = {}
        mock_server.run = AsyncMock()
        mock_server_class.return_value = mock_server

        # Capture handlers
        registered_handlers = {}

        def capture_list_tools():
            def decorator(func):
                registered_handlers["list_tools"] = func
                return func

            return decorator

        def capture_call_tool():
            def decorator(func):
                registered_handlers["call_tool"] = func
                return func

            return decorator

        def capture_list_prompts():
            def decorator(func):
                registered_handlers["list_prompts"] = func
                return func

            return decorator

        def capture_get_prompt():
            def decorator(func):
                registered_handlers["get_prompt"] = func
                return func

            return decorator

        mock_server.list_tools = capture_list_tools
        mock_server.call_tool = capture_call_tool
        mock_server.list_prompts = capture_list_prompts
        mock_server.get_prompt = capture_get_prompt

        # Create a mock config path
        mock_config_path = Path(".")

        # Run serve to register handlers
        asyncio.run(serve(mock_config, mock_config_path))

        # Test the get_prompt handler
        result = asyncio.run(registered_handlers["get_prompt"]("test_prompt"))

        assert result.description == "Test prompt description"
        assert len(result.messages) == 1
        # Access the PromptMessage object properly
        prompt_message = result.messages[0]
        assert prompt_message.role == "user"
        assert prompt_message.content.type == "text"
        assert prompt_message.content.text == "Test prompt content"

    @patch("hooks_mcp.server.stdio_server")
    @patch("hooks_mcp.server.Server")
    @patch("hooks_mcp.server.CommandExecutor")
    def test_get_prompt_handler_prompt_not_found(
        self, mock_executor_class, mock_server_class, mock_stdio_server, mock_config
    ):
        """Test get_prompt handler with non-existent prompt."""
        # Add a prompt to the mock config
        prompt = ConfigPrompt(
            name="test_prompt",
            description="Test prompt description",
            prompt_text="Test prompt content",
        )
        mock_config.prompts = [prompt]

        # Setup mocks
        mock_stdio_server.return_value.__aenter__.return_value = (
            MagicMock(),
            MagicMock(),
        )
        mock_server = MagicMock()
        mock_server.create_initialization_options.return_value = {}
        mock_server.run = AsyncMock()
        mock_server_class.return_value = mock_server

        # Capture handlers
        registered_handlers = {}

        def capture_list_tools():
            def decorator(func):
                registered_handlers["list_tools"] = func
                return func

            return decorator

        def capture_call_tool():
            def decorator(func):
                registered_handlers["call_tool"] = func
                return func

            return decorator

        def capture_list_prompts():
            def decorator(func):
                registered_handlers["list_prompts"] = func
                return func

            return decorator

        def capture_get_prompt():
            def decorator(func):
                registered_handlers["get_prompt"] = func
                return func

            return decorator

        mock_server.list_tools = capture_list_tools
        mock_server.call_tool = capture_call_tool
        mock_server.list_prompts = capture_list_prompts
        mock_server.get_prompt = capture_get_prompt

        # Create a mock config path
        mock_config_path = Path(".")

        # Run serve to register handlers
        asyncio.run(serve(mock_config, mock_config_path))

        # Test the get_prompt handler with non-existent prompt
        with pytest.raises(ExecutionError) as exc_info:
            asyncio.run(registered_handlers["get_prompt"]("nonexistent_prompt"))

        assert "Prompt 'nonexistent_prompt' not found" in str(exc_info.value)

    @patch("hooks_mcp.server.stdio_server")
    @patch("hooks_mcp.server.Server")
    @patch("hooks_mcp.server.CommandExecutor")
    def test_get_prompt_handler_with_argument_substitution(
        self, mock_executor_class, mock_server_class, mock_stdio_server, mock_config
    ):
        """Test prompt retrieval with argument substitution via MCP protocol."""
        # Add a prompt with template variables to the mock config
        prompt_arg = ConfigPromptArgument(
            name="CODE_SNIPPET",
            description="Code to analyze",
            required=True,
        )
        prompt = ConfigPrompt(
            name="code_analysis",
            description="Analyze code",
            prompt_text="Please analyze the following code:\n{{CODE_SNIPPET}}\nProvide feedback.",
            arguments=[prompt_arg],
        )
        mock_config.prompts = [prompt]

        # Setup mocks
        mock_stdio_server.return_value.__aenter__.return_value = (
            MagicMock(),
            MagicMock(),
        )
        mock_server = MagicMock()
        mock_server.create_initialization_options.return_value = {}
        mock_server.run = AsyncMock()
        mock_server_class.return_value = mock_server

        # Capture handlers
        registered_handlers = {}

        def capture_list_tools():
            def decorator(func):
                registered_handlers["list_tools"] = func
                return func

            return decorator

        def capture_call_tool():
            def decorator(func):
                registered_handlers["call_tool"] = func
                return func

            return decorator

        def capture_list_prompts():
            def decorator(func):
                registered_handlers["list_prompts"] = func
                return func

            return decorator

        def capture_get_prompt():
            def decorator(func):
                registered_handlers["get_prompt"] = func
                return func

            return decorator

        mock_server.list_tools = capture_list_tools
        mock_server.call_tool = capture_call_tool
        mock_server.list_prompts = capture_list_prompts
        mock_server.get_prompt = capture_get_prompt

        # Create a mock config path
        mock_config_path = Path(".")

        # Run serve to register handlers
        asyncio.run(serve(mock_config, mock_config_path))

        # Test the get_prompt handler with arguments - this should now work correctly
        result = asyncio.run(
            registered_handlers["get_prompt"](
                "code_analysis",
                {"CODE_SNIPPET": "def hello_world():\n    print('Hello, World!')"},
            )
        )

        # Verify that the prompt content has been properly substituted
        assert "{{CODE_SNIPPET}}" not in result.messages[0].content.text
        assert (
            "def hello_world():\n    print('Hello, World!')"
            in result.messages[0].content.text
        )
        assert (
            result.messages[0].content.text
            == "Please analyze the following code:\ndef hello_world():\n    print('Hello, World!')\nProvide feedback."
        )

    @patch("hooks_mcp.server.stdio_server")
    @patch("hooks_mcp.server.Server")
    @patch("hooks_mcp.server.CommandExecutor")
    def test_call_tool_handler_get_prompt_with_filter_success(
        self, mock_executor_class, mock_server_class, mock_stdio_server
    ):
        """Test successful get_prompt tool execution with filter."""
        # Setup config with prompts and filter
        prompt1 = ConfigPrompt(
            name="allowed_prompt",
            description="An allowed prompt",
            prompt_text="This prompt is allowed",
        )
        prompt2 = ConfigPrompt(
            name="filtered_prompt",
            description="A filtered out prompt",
            prompt_text="This prompt is filtered out",
        )
        action = Action(
            name="test_action", description="Test action", command="echo hello"
        )
        config = HooksMCPConfig(
            server_name="TestServer",
            server_description="Test Description",
            actions=[action],
            prompts=[prompt1, prompt2],
            get_prompt_tool_filter=["allowed_prompt"],
        )

        # Setup mocks
        mock_stdio_server.return_value.__aenter__.return_value = (
            MagicMock(),
            MagicMock(),
        )
        mock_server = MagicMock()
        mock_server.create_initialization_options.return_value = {}
        mock_server.run = AsyncMock()
        mock_server_class.return_value = mock_server

        mock_executor = MagicMock()
        mock_executor_class.return_value = mock_executor

        # Capture handlers
        registered_handlers = {}

        def capture_list_tools():
            def decorator(func):
                registered_handlers["list_tools"] = func
                return func

            return decorator

        def capture_call_tool():
            def decorator(func):
                registered_handlers["call_tool"] = func
                return func

            return decorator

        def capture_list_prompts():
            def decorator(func):
                registered_handlers["list_prompts"] = func
                return func

            return decorator

        def capture_get_prompt():
            def decorator(func):
                registered_handlers["get_prompt"] = func
                return func

            return decorator

        mock_server.list_tools = capture_list_tools
        mock_server.call_tool = capture_call_tool
        mock_server.list_prompts = capture_list_prompts
        mock_server.get_prompt = capture_get_prompt

        # Create a mock config path
        mock_config_path = Path(".")

        # Run serve to register handlers
        asyncio.run(serve(config, mock_config_path))

        # Test the call_tool handler with get_prompt for an allowed prompt
        result = asyncio.run(
            registered_handlers["call_tool"](
                "get_prompt", {"prompt_name": "allowed_prompt"}
            )
        )

        # Verify result format
        assert len(result) == 1
        assert result[0].type == "text"
        assert result[0].text == "This prompt is allowed"

    @patch("hooks_mcp.server.stdio_server")
    @patch("hooks_mcp.server.Server")
    @patch("hooks_mcp.server.CommandExecutor")
    def test_call_tool_handler_get_prompt_filtered_out(
        self, mock_executor_class, mock_server_class, mock_stdio_server
    ):
        """Test get_prompt tool execution with filtered out prompt."""
        # Setup config with prompts and filter
        prompt1 = ConfigPrompt(
            name="allowed_prompt",
            description="An allowed prompt",
            prompt_text="This prompt is allowed",
        )
        prompt2 = ConfigPrompt(
            name="filtered_prompt",
            description="A filtered out prompt",
            prompt_text="This prompt is filtered out",
        )
        action = Action(
            name="test_action", description="Test action", command="echo hello"
        )
        config = HooksMCPConfig(
            server_name="TestServer",
            server_description="Test Description",
            actions=[action],
            prompts=[prompt1, prompt2],
            get_prompt_tool_filter=["allowed_prompt"],
        )

        # Setup mocks
        mock_stdio_server.return_value.__aenter__.return_value = (
            MagicMock(),
            MagicMock(),
        )
        mock_server = MagicMock()
        mock_server.create_initialization_options.return_value = {}
        mock_server.run = AsyncMock()
        mock_server_class.return_value = mock_server

        mock_executor = MagicMock()
        mock_executor_class.return_value = mock_executor

        # Capture handlers
        registered_handlers = {}

        def capture_list_tools():
            def decorator(func):
                registered_handlers["list_tools"] = func
                return func

            return decorator

        def capture_call_tool():
            def decorator(func):
                registered_handlers["call_tool"] = func
                return func

            return decorator

        def capture_list_prompts():
            def decorator(func):
                registered_handlers["list_prompts"] = func
                return func

            return decorator

        def capture_get_prompt():
            def decorator(func):
                registered_handlers["get_prompt"] = func
                return func

            return decorator

        mock_server.list_tools = capture_list_tools
        mock_server.call_tool = capture_call_tool
        mock_server.list_prompts = capture_list_prompts
        mock_server.get_prompt = capture_get_prompt

        # Create a mock config path
        mock_config_path = Path(".")

        # Run serve to register handlers
        asyncio.run(serve(config, mock_config_path))

        # Test the call_tool handler with get_prompt for a filtered out prompt
        with pytest.raises(ExecutionError) as exc_info:
            asyncio.run(
                registered_handlers["call_tool"](
                    "get_prompt", {"prompt_name": "filtered_prompt"}
                )
            )

        assert (
            "Prompt 'filtered_prompt' is not available through get_prompt tool"
            in str(exc_info.value)
        )
        assert "allowed_prompt" in str(
            exc_info.value
        )  # Should mention available prompts

    @patch("hooks_mcp.server.stdio_server")
    @patch("hooks_mcp.server.Server")
    @patch("hooks_mcp.server.CommandExecutor")
    def test_call_tool_handler_get_prompt_empty_filter(
        self, mock_executor_class, mock_server_class, mock_stdio_server
    ):
        """Test get_prompt tool execution when filter is empty."""
        # Setup config with prompts and empty filter
        prompt1 = ConfigPrompt(
            name="any_prompt",
            description="Any prompt",
            prompt_text="This prompt should not be accessible",
        )
        action = Action(
            name="test_action", description="Test action", command="echo hello"
        )
        config = HooksMCPConfig(
            server_name="TestServer",
            server_description="Test Description",
            actions=[action],
            prompts=[prompt1],
            get_prompt_tool_filter=[],
        )

        # Setup mocks
        mock_stdio_server.return_value.__aenter__.return_value = (
            MagicMock(),
            MagicMock(),
        )
        mock_server = MagicMock()
        mock_server.create_initialization_options.return_value = {}
        mock_server.run = AsyncMock()
        mock_server_class.return_value = mock_server

        mock_executor = MagicMock()
        mock_executor_class.return_value = mock_executor

        # Capture handlers
        registered_handlers = {}

        def capture_list_tools():
            def decorator(func):
                registered_handlers["list_tools"] = func
                return func

            return decorator

        def capture_call_tool():
            def decorator(func):
                registered_handlers["call_tool"] = func
                return func

            return decorator

        def capture_list_prompts():
            def decorator(func):
                registered_handlers["list_prompts"] = func
                return func

            return decorator

        def capture_get_prompt():
            def decorator(func):
                registered_handlers["get_prompt"] = func
                return func

            return decorator

        mock_server.list_tools = capture_list_tools
        mock_server.call_tool = capture_call_tool
        mock_server.list_prompts = capture_list_prompts
        mock_server.get_prompt = capture_get_prompt

        # Create a mock config path
        mock_config_path = Path(".")

        # Run serve to register handlers
        asyncio.run(serve(config, mock_config_path))

        # Test the call_tool handler with get_prompt (should fail since filter is empty)
        with pytest.raises(ExecutionError) as exc_info:
            asyncio.run(
                registered_handlers["call_tool"](
                    "get_prompt", {"prompt_name": "any_prompt"}
                )
            )

        assert "No prompts are available through get_prompt tool" in str(exc_info.value)


class TestMain:
    """Test the main function."""

    def test_main_default_config_path(self):
        """Test main function with default config path."""
        test_args = ["test_program"]

        with (
            patch("sys.argv", test_args),
            patch("hooks_mcp.server.Path") as mock_path,
            patch("hooks_mcp.server.HooksMCPConfig") as mock_config_class,
            patch("asyncio.run") as mock_asyncio_run,
        ):
            # Mock path exists check
            mock_path_obj = MagicMock()
            mock_path_obj.exists.return_value = True
            mock_path.return_value = mock_path_obj

            # Mock config loading
            mock_config = MagicMock()
            mock_config.validate_required_env_vars.return_value = []
            mock_config_class.from_yaml.return_value = mock_config

            main()

            # Verify config path was constructed correctly
            mock_path.assert_called_with("./hooks_mcp.yaml")
            mock_config_class.from_yaml.assert_called_once()
            mock_asyncio_run.assert_called_once()

    def test_main_custom_config_path(self):
        """Test main function with custom config path."""
        test_args = ["test_program", "/custom/config.yaml"]

        with (
            patch("sys.argv", test_args),
            patch("hooks_mcp.server.Path") as mock_path,
            patch("hooks_mcp.server.HooksMCPConfig") as mock_config_class,
            patch("asyncio.run"),
        ):
            # Mock path exists check
            mock_path_obj = MagicMock()
            mock_path_obj.exists.return_value = True
            mock_path.return_value = mock_path_obj

            # Mock config loading
            mock_config = MagicMock()
            mock_config.validate_required_env_vars.return_value = []
            mock_config_class.from_yaml.return_value = mock_config

            main()

            # Verify custom config path was used
            mock_path.assert_called_with("/custom/config.yaml")

    def test_main_with_working_directory(self):
        """Test main function with working directory argument."""
        test_args = ["test_program", "config.yaml", "-wd", "/custom/workdir"]

        with (
            patch("sys.argv", test_args),
            patch("hooks_mcp.server.Path") as mock_path,
            patch("hooks_mcp.server.HooksMCPConfig") as mock_config_class,
            patch("hooks_mcp.server.os.chdir") as mock_chdir,
            patch("asyncio.run"),
        ):
            # Mock path exists check
            mock_path_obj = MagicMock()
            mock_path_obj.exists.return_value = True
            mock_path.return_value = mock_path_obj

            # Mock config loading
            mock_config = MagicMock()
            mock_config.validate_required_env_vars.return_value = []
            mock_config_class.from_yaml.return_value = mock_config

            main()

            # Verify working directory was changed
            mock_chdir.assert_called_once_with("/custom/workdir")

    def test_main_working_directory_change_fails(self):
        """Test main function when working directory change fails."""
        test_args = ["test_program", "config.yaml", "-wd", "/invalid/workdir"]

        with (
            patch("sys.argv", test_args),
            patch("hooks_mcp.server.os.chdir") as mock_chdir,
            patch("builtins.print") as mock_print,
            patch("sys.exit") as mock_exit,
        ):
            # Mock chdir to raise exception
            mock_chdir.side_effect = OSError("Directory not found")
            # Mock sys.exit to raise SystemExit to stop execution
            mock_exit.side_effect = SystemExit(1)

            with pytest.raises(SystemExit):
                main()

            # Verify error was printed and exit was called
            mock_print.assert_called_once()
            assert "Failed to change working directory" in mock_print.call_args[0][0]
            mock_exit.assert_called_once_with(1)

    def test_main_config_file_not_found(self):
        """Test main function when config file doesn't exist."""
        test_args = ["test_program", "missing_config.yaml"]

        with (
            patch("sys.argv", test_args),
            patch("hooks_mcp.server.Path") as mock_path,
            patch("builtins.print") as mock_print,
            patch("sys.exit") as mock_exit,
        ):
            # Mock path exists check to return False
            mock_path_obj = MagicMock()
            mock_path_obj.exists.return_value = False
            mock_path.return_value = mock_path_obj
            # Mock sys.exit to raise SystemExit to stop execution
            mock_exit.side_effect = SystemExit(1)

            with pytest.raises(SystemExit):
                main()

            # Verify error was printed and exit was called
            mock_print.assert_called_once()
            assert "Configuration file" in mock_print.call_args[0][0]
            assert "not found" in mock_print.call_args[0][0]
            mock_exit.assert_called_once_with(1)

    def test_main_config_error(self):
        """Test main function when config loading raises ConfigError."""
        test_args = ["test_program", "config.yaml"]

        with (
            patch("sys.argv", test_args),
            patch("hooks_mcp.server.Path") as mock_path,
            patch("hooks_mcp.server.HooksMCPConfig") as mock_config_class,
            patch("builtins.print") as mock_print,
            patch("sys.exit") as mock_exit,
        ):
            # Mock path exists check
            mock_path_obj = MagicMock()
            mock_path_obj.exists.return_value = True
            mock_path.return_value = mock_path_obj

            # Mock config loading to raise ConfigError
            mock_config_class.from_yaml.side_effect = ConfigError("Invalid config")
            # Mock sys.exit to raise SystemExit to stop execution
            mock_exit.side_effect = SystemExit(1)

            with pytest.raises(SystemExit):
                main()

            # Verify error was printed and exit was called
            mock_print.assert_called_once_with("Invalid config")
            mock_exit.assert_called_once_with(1)

    def test_main_missing_required_env_vars(self):
        """Test main function when required environment variables are missing."""
        test_args = ["test_program", "config.yaml"]

        with (
            patch("sys.argv", test_args),
            patch("hooks_mcp.server.Path") as mock_path,
            patch("hooks_mcp.server.HooksMCPConfig") as mock_config_class,
            patch("builtins.print") as mock_print,
            patch("sys.exit") as mock_exit,
        ):
            # Mock path exists check
            mock_path_obj = MagicMock()
            mock_path_obj.exists.return_value = True
            mock_path.return_value = mock_path_obj

            # Mock config loading
            mock_config = MagicMock()
            mock_config.validate_required_env_vars.return_value = ["API_KEY", "SECRET"]
            mock_config_class.from_yaml.return_value = mock_config
            # Mock sys.exit to raise SystemExit to stop execution
            mock_exit.side_effect = SystemExit(1)

            with pytest.raises(SystemExit):
                main()

            # Verify error messages were printed and exit was called
            assert mock_print.call_count >= 2
            error_calls = [call[0][0] for call in mock_print.call_args_list]
            assert any(
                "Required environment variables not set" in call for call in error_calls
            )
            assert any("Please set these variables" in call for call in error_calls)
            mock_exit.assert_called_once_with(1)

    def test_main_with_env_file(self):
        """Test main function loads .env file when present."""
        test_args = ["test_program", "config.yaml"]

        with (
            patch("sys.argv", test_args),
            patch("hooks_mcp.server.Path") as mock_path,
            patch("hooks_mcp.server.HooksMCPConfig") as mock_config_class,
            patch("asyncio.run"),
            patch("dotenv.load_dotenv") as mock_load_dotenv,
        ):
            # Mock path exists check for both config and .env
            mock_config_path = MagicMock()
            mock_config_path.exists.return_value = True
            mock_env_path = MagicMock()
            mock_env_path.exists.return_value = True
            mock_config_path.parent = MagicMock()
            mock_config_path.parent.__truediv__ = lambda self, other: mock_env_path
            mock_path.return_value = mock_config_path

            # Mock config loading
            mock_config = MagicMock()
            mock_config.validate_required_env_vars.return_value = []
            mock_config_class.from_yaml.return_value = mock_config

            main()

            # Verify .env file was loaded
            mock_load_dotenv.assert_called_once_with(mock_env_path)

    def test_main_keyboard_interrupt(self):
        """Test main function handles KeyboardInterrupt gracefully."""
        test_args = ["test_program", "config.yaml"]

        with (
            patch("sys.argv", test_args),
            patch("hooks_mcp.server.Path") as mock_path,
            patch("hooks_mcp.server.HooksMCPConfig") as mock_config_class,
            patch("asyncio.run") as mock_asyncio_run,
            patch("builtins.print") as mock_print,
            patch("sys.exit") as mock_exit,
        ):
            # Mock path exists check
            mock_path_obj = MagicMock()
            mock_path_obj.exists.return_value = True
            mock_path.return_value = mock_path_obj

            # Mock config loading
            mock_config = MagicMock()
            mock_config.validate_required_env_vars.return_value = []
            mock_config_class.from_yaml.return_value = mock_config

            # Mock asyncio.run to raise KeyboardInterrupt
            mock_asyncio_run.side_effect = KeyboardInterrupt()
            # Mock sys.exit to raise SystemExit to stop execution
            mock_exit.side_effect = SystemExit(0)

            with pytest.raises(SystemExit):
                main()

            # Verify graceful shutdown message and exit
            mock_print.assert_called_once_with("HooksMCP server stopped by user")
            mock_exit.assert_called_once_with(0)

    def test_main_server_start_error(self):
        """Test main function when server fails to start."""
        test_args = ["test_program", "config.yaml"]

        with (
            patch("sys.argv", test_args),
            patch("hooks_mcp.server.Path") as mock_path,
            patch("hooks_mcp.server.HooksMCPConfig") as mock_config_class,
            patch("asyncio.run") as mock_asyncio_run,
            patch("builtins.print") as mock_print,
            patch("sys.exit") as mock_exit,
        ):
            # Mock path exists check
            mock_path_obj = MagicMock()
            mock_path_obj.exists.return_value = True
            mock_path.return_value = mock_path_obj

            # Mock config loading
            mock_config = MagicMock()
            mock_config.validate_required_env_vars.return_value = []
            mock_config_class.from_yaml.return_value = mock_config

            # Mock asyncio.run to raise exception
            mock_asyncio_run.side_effect = RuntimeError("Server failed to start")
            # Mock sys.exit to raise SystemExit to stop execution
            mock_exit.side_effect = SystemExit(1)

            with pytest.raises(SystemExit):
                main()

            # Verify error was printed and exit was called
            mock_print.assert_called_once()
            assert "Failed to start server" in mock_print.call_args[0][0]
            assert "Server failed to start" in mock_print.call_args[0][0]
            mock_exit.assert_called_once_with(1)


class TestCreatePromptDefinitions:
    """Test the create_prompt_definitions function."""

    def test_empty_config(self):
        """Test creating prompt definitions from empty config."""
        config = HooksMCPConfig(
            server_name="TestServer",
            server_description="Test Description",
            actions=[],
            prompts=[],
        )

        prompts = create_prompt_definitions(config)

        assert prompts == []

    def test_single_prompt_no_arguments(self):
        """Test creating prompt definition for single prompt without arguments."""
        prompt = ConfigPrompt(
            name="test_prompt",
            description="Test prompt description",
            prompt_text="Test prompt content",
        )
        config = HooksMCPConfig(
            server_name="TestServer",
            server_description="Test Description",
            actions=[],
            prompts=[prompt],
        )

        prompts = create_prompt_definitions(config)

        assert len(prompts) == 1
        mcp_prompt = prompts[0]
        assert mcp_prompt.name == "test_prompt"
        assert mcp_prompt.description == "Test prompt description"
        assert mcp_prompt.arguments is None

    def test_single_prompt_with_arguments(self):
        """Test creating prompt definition for single prompt with arguments."""
        prompt_arg = ConfigPromptArgument(
            name="test_arg",
            description="Test argument description",
            required=True,
        )
        prompt = ConfigPrompt(
            name="test_prompt",
            description="Test prompt description",
            prompt_text="Test prompt content with $test_arg",
            arguments=[prompt_arg],
        )
        config = HooksMCPConfig(
            server_name="TestServer",
            server_description="Test Description",
            actions=[],
            prompts=[prompt],
        )

        prompts = create_prompt_definitions(config)

        assert len(prompts) == 1
        mcp_prompt = prompts[0]
        assert mcp_prompt.name == "test_prompt"
        assert mcp_prompt.description == "Test prompt description"
        assert mcp_prompt.arguments is not None
        assert len(mcp_prompt.arguments) == 1

        arg = mcp_prompt.arguments[0]
        assert arg.name == "test_arg"
        assert arg.description == "Test argument description"
        assert arg.required

    def test_multiple_prompts(self):
        """Test creating prompt definitions for multiple prompts."""
        prompt1 = ConfigPrompt(
            name="prompt1",
            description="First prompt",
            prompt_text="Content of first prompt",
        )
        prompt2 = ConfigPrompt(
            name="prompt2",
            description="Second prompt",
            prompt_file="./test_file.md",
        )
        config = HooksMCPConfig(
            server_name="TestServer",
            server_description="Test Description",
            actions=[],
            prompts=[prompt1, prompt2],
        )

        prompts = create_prompt_definitions(config)

        assert len(prompts) == 2
        assert prompts[0].name == "prompt1"
        assert prompts[1].name == "prompt2"


class TestGetPromptContent:
    """Test the get_prompt_content function."""

    def test_get_prompt_content_inline(self):
        """Test getting prompt content from inline text."""
        prompt = ConfigPrompt(
            name="test_prompt",
            description="Test prompt description",
            prompt_text="Test prompt content",
        )
        config_path = Path(".")

        content = get_prompt_content(prompt, config_path)

        assert content == "Test prompt content"

    def test_get_prompt_content_from_file(self):
        """Test getting prompt content from a file."""
        # Create a temporary file with prompt content
        with tempfile.NamedTemporaryFile(mode="w", suffix=".md", delete=False) as f:
            f.write("# Test Prompt\n\nThis is test prompt content.")
            f.flush()
            prompt_file_path = Path(f.name)

        prompt = ConfigPrompt(
            name="test_prompt",
            description="Test prompt description",
            prompt_file=str(prompt_file_path),
        )
        config_path = prompt_file_path.parent

        content = get_prompt_content(prompt, config_path)

        assert content == "# Test Prompt\n\nThis is test prompt content."

        # Clean up
        prompt_file_path.unlink()

    def test_get_prompt_content_file_not_found(self):
        """Test getting prompt content from a non-existent file."""
        prompt = ConfigPrompt(
            name="test_prompt",
            description="Test prompt description",
            prompt_file="./nonexistent_file.md",
        )
        config_path = Path(".")

        with pytest.raises(ExecutionError) as exc_info:
            get_prompt_content(prompt, config_path)

        assert "Failed to read prompt file" in str(exc_info.value)
        assert "./nonexistent_file.md" in str(exc_info.value)
