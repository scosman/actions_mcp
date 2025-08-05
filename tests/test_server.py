import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from hooks_mcp.config import (
    Action,
    ActionParameter,
    ConfigError,
    HooksMCPConfig,
    ParameterType,
)
from hooks_mcp.executor import ExecutionError
from hooks_mcp.server import create_tool_definitions, main, serve


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

        # Run the serve function
        asyncio.run(serve(mock_config))

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

        # Run serve to register handlers
        asyncio.run(serve(mock_config))

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

        # Run serve to register handlers
        asyncio.run(serve(mock_config))

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

        # Run serve to register handlers
        asyncio.run(serve(mock_config))

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

        # Run serve to register handlers
        asyncio.run(serve(mock_config))

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

        # Run serve to register handlers
        asyncio.run(serve(mock_config))

        # Test the call_tool handler
        with pytest.raises(ExecutionError) as exc_info:
            asyncio.run(registered_handlers["call_tool"]("test_action", {}))

        assert (
            "Unexpected error executing action 'test_action': Unexpected error"
            in str(exc_info.value)
        )


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
