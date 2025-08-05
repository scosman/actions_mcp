import tempfile
from pathlib import Path

import pytest

from hooks_mcp.config import Action, ActionParameter, ParameterType
from hooks_mcp.executor import CommandExecutor, ExecutionError


class TestExecutor:
    """Test command execution functionality."""

    @pytest.fixture(autouse=True)
    def setup_teardown(self):
        """Set up and tear down test environment."""
        # Create a temporary directory for testing
        self.temp_dir = tempfile.TemporaryDirectory()
        self.project_root = Path(self.temp_dir.name)

        # Create some test files and directories
        (self.project_root / "tests").mkdir()
        (self.project_root / "tests" / "test1.py").touch()
        (self.project_root / "src").mkdir()
        (self.project_root / "src" / "main.py").touch()

        self.executor = CommandExecutor()
        self.executor.project_root = self.project_root

        # This will run after each test
        yield

        # Clean up test environment
        self.temp_dir.cleanup()

    def test_execute_simple_command(self):
        """Test executing a simple command without parameters."""
        action = Action(
            name="echo_test", description="Echo test", command="echo Hello World"
        )

        result = self.executor.execute_action(action, {})

        assert result["status_code"] == 0
        assert "Hello World" in result["stdout"]
        assert result["stderr"] == ""

    def test_execute_command_with_project_file_path(self):
        """Test executing a command with a project file path parameter."""
        action = Action(
            name="cat_test",
            description="Cat test file",
            command="cat $TEST_FILE",
            parameters=[
                ActionParameter(
                    "TEST_FILE", ParameterType.PROJECT_FILE_PATH, "Test file to cat"
                )
            ],
        )

        # This should work with a valid path
        result = self.executor.execute_action(action, {"TEST_FILE": "tests/test1.py"})

        assert result["status_code"] == 0
        assert result["stdout"] == ""
        assert result["stderr"] == ""

    def test_execute_command_with_insecure_string(self):
        """Test executing a command with an insecure string parameter."""
        action = Action(
            name="echo_insecure",
            description="Echo insecure string",
            command="echo $MESSAGE",
            parameters=[
                ActionParameter(
                    "MESSAGE", ParameterType.INSECURE_STRING, "Message to echo"
                )
            ],
        )

        result = self.executor.execute_action(action, {"MESSAGE": "Hello World"})

        assert result["status_code"] == 0
        assert "Hello World" in result["stdout"]
        assert result["stderr"] == ""

    def test_execute_command_with_default_parameters(self):
        """Test executing a command with default parameter values."""
        action = Action(
            name="echo_default",
            description="Echo with default",
            command="echo $MESSAGE",
            parameters=[
                ActionParameter(
                    "MESSAGE",
                    ParameterType.INSECURE_STRING,
                    "Message to echo",
                    "Default Message",
                )
            ],
        )

        # Execute without providing the parameter, should use default
        result = self.executor.execute_action(action, {})

        assert result["status_code"] == 0
        assert "Default Message" in result["stdout"]
        assert result["stderr"] == ""

    def test_execute_command_missing_required_parameter(self):
        """Test that executing a command without a required parameter raises an error."""
        action = Action(
            name="echo_required",
            description="Echo with required parameter",
            command="echo $MESSAGE",
            parameters=[
                ActionParameter(
                    "MESSAGE", ParameterType.INSECURE_STRING, "Message to echo"
                )
            ],
        )

        with pytest.raises(ExecutionError) as context:
            self.executor.execute_action(action, {})

        assert "Required parameter 'MESSAGE' not provided" in str(context.value)

    def test_execute_command_with_run_path(self):
        """Test executing a command with a run_path."""
        # Create a subdirectory for testing
        (self.project_root / "subdir").mkdir()
        (self.project_root / "subdir" / "file.txt").touch()

        action = Action(
            name="pwd_test",
            description="Print working directory",
            command="pwd",
            run_path="subdir",
        )

        result = self.executor.execute_action(action, {})

        assert result["status_code"] == 0
        # The output should contain the subdir path
        assert "subdir" in result["stdout"]

    def test_execute_command_invalid_run_path(self):
        """Test that executing a command with an invalid run_path raises an error."""
        action = Action(
            name="echo_test",
            description="Echo test",
            command="echo Hello World",
            run_path="../outside",
        )

        with pytest.raises(ExecutionError) as context:
            self.executor.execute_action(action, {})

        assert "Invalid run_path" in str(context.value)

    def test_execute_command_with_insecure_string_prevents_command_injection(self):
        """Test that insecure string parameters don't allow command injection."""
        action = Action(
            name="echo_insecure",
            description="Echo insecure string",
            command="echo $MESSAGE",
            parameters=[
                ActionParameter(
                    "MESSAGE", ParameterType.INSECURE_STRING, "Message to echo"
                )
            ],
        )

        # This test checks that the command doesn't execute the second part of the string as a separate command
        # If vulnerable to injection, this would execute both "echo 123" and "echo 456"
        result = self.executor.execute_action(action, {"MESSAGE": "123 && echo 456"})

        assert result["status_code"] == 0
        # The output should contain the full string "123 && echo 456" and not just "123"
        # It should not contain "456" on a separate line
        assert "123 && echo 456" in result["stdout"]
        assert "456" not in result["stdout"].split("\n")

    def test_execute_command_with_insecure_string_prevents_semicolon_injection(self):
        """Test that insecure string parameters don't allow semicolon command injection."""
        action = Action(
            name="echo_insecure",
            description="Echo insecure string",
            command="echo $MESSAGE",
            parameters=[
                ActionParameter(
                    "MESSAGE", ParameterType.INSECURE_STRING, "Message to echo"
                )
            ],
        )

        # Test semicolon command injection
        result = self.executor.execute_action(action, {"MESSAGE": "123; echo 456"})

        assert result["status_code"] == 0
        # The output should contain the full string "123; echo 456" and not just "123"
        # It should not contain "456" on a separate line
        assert "123; echo 456" in result["stdout"]
        assert "456" not in result["stdout"].split("\n")

    def test_execute_command_with_insecure_string_prevents_pipe_injection(self):
        """Test that insecure string parameters don't allow pipe command injection."""
        action = Action(
            name="echo_insecure",
            description="Echo insecure string",
            command="echo $MESSAGE",
            parameters=[
                ActionParameter(
                    "MESSAGE", ParameterType.INSECURE_STRING, "Message to echo"
                )
            ],
        )

        # Test pipe command injection
        result = self.executor.execute_action(action, {"MESSAGE": "123 | echo 456"})

        assert result["status_code"] == 0
        # The output should contain the full string "123 | echo 456"
        assert "123 | echo 456" in result["stdout"]

    def test_execute_command_with_insecure_string_prevents_redirect_injection(self):
        """Test that insecure string parameters don't allow redirect command injection."""
        action = Action(
            name="echo_insecure",
            description="Echo insecure string",
            command="echo $MESSAGE",
            parameters=[
                ActionParameter(
                    "MESSAGE", ParameterType.INSECURE_STRING, "Message to echo"
                )
            ],
        )

        # Test redirect command injection
        result = self.executor.execute_action(action, {"MESSAGE": "123 > test.txt"})

        assert result["status_code"] == 0
        # The output should contain the full string "123 > test.txt"
        assert "123 > test.txt" in result["stdout"]

    def test_execute_command_with_insecure_string_prevents_subshell_injection(self):
        """Test that insecure string parameters don't allow subshell command injection."""
        action = Action(
            name="echo_insecure",
            description="Echo insecure string",
            command="echo $MESSAGE",
            parameters=[
                ActionParameter(
                    "MESSAGE", ParameterType.INSECURE_STRING, "Message to echo"
                )
            ],
        )

        # Test subshell command injection
        result = self.executor.execute_action(action, {"MESSAGE": "123 $(echo 456)"})

        assert result["status_code"] == 0
        # The output should contain the full string "123 $(echo 456)"
        assert "123 $(echo 456)" in result["stdout"]

    def test_execute_command_with_insecure_string_prevents_backtick_injection(self):
        """Test that insecure string parameters don't allow backtick command injection."""
        action = Action(
            name="echo_insecure",
            description="Echo insecure string",
            command="echo $MESSAGE",
            parameters=[
                ActionParameter(
                    "MESSAGE", ParameterType.INSECURE_STRING, "Message to echo"
                )
            ],
        )

        # Test backtick command injection
        result = self.executor.execute_action(action, {"MESSAGE": "123 `echo 456`"})

        assert result["status_code"] == 0
        # The output should contain the full string "123 `echo 456`"
        assert "123 `echo 456`" in result["stdout"]

    def test_execute_command_with_required_env_var_substitution(self):
        """Test that required_env_var parameters get substituted in commands.

        This test demonstrates a bug: env vars are not substituted because the
        substitution line is commented out and env vars are skipped in the loop.
        """
        import os

        # Set up environment variable
        original_value = os.environ.get("TEST_MESSAGE")
        os.environ["TEST_MESSAGE"] = "Hello from env var"

        try:
            action = Action(
                name="echo_env_var",
                description="Echo environment variable",
                command="echo $TEST_MESSAGE",
                parameters=[
                    ActionParameter(
                        "TEST_MESSAGE",
                        ParameterType.REQUIRED_ENV_VAR,
                        "Test message from environment",
                    )
                ],
            )

            result = self.executor.execute_action(action, {})

            assert result["status_code"] == 0
            # This should pass if env var substitution works, but will fail with current code
            assert "Hello from env var" in result["stdout"]
            # This assertion shows what actually happens - literal $TEST_MESSAGE
            assert "$TEST_MESSAGE" not in result["stdout"]

        finally:
            # Clean up environment
            if original_value is None:
                os.environ.pop("TEST_MESSAGE", None)
            else:
                os.environ["TEST_MESSAGE"] = original_value

    def test_execute_command_with_timeout(self):
        """Test that the timeout parameter is respected."""
        # Create an action with a short timeout (1 second)
        action = Action(
            name="sleep_test",
            description="Sleep test",
            command="sleep 5",  # This will take longer than the timeout
            timeout=1,  # 1 second timeout
        )

        # Execute the action and expect a timeout error
        with pytest.raises(ExecutionError) as context:
            self.executor.execute_action(action, {})

        # Verify the error message contains the correct timeout value
        assert "timed out after 1 seconds" in str(context.value)

    def test_execute_command_with_default_timeout(self):
        """Test that the default timeout is used when not specified."""
        # Create an action without specifying timeout (should default to 60 seconds)
        action = Action(
            name="sleep_test_default",
            description="Sleep test with default timeout",
            command="sleep 1",  # This will complete within the default timeout
        )

        # Execute the action - it should complete successfully
        result = self.executor.execute_action(action, {})

        assert result["status_code"] == 0
        assert result["stderr"] == ""
