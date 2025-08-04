import tempfile
import pytest
from pathlib import Path
from actions_mcp.config import Action, ActionParameter, ParameterType
from actions_mcp.executor import CommandExecutor, ExecutionError


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
            name="echo_test",
            description="Echo test",
            command="echo Hello World"
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
                ActionParameter("TEST_FILE", ParameterType.PROJECT_FILE_PATH, "Test file to cat")
            ]
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
                ActionParameter("MESSAGE", ParameterType.INSECURE_STRING, "Message to echo")
            ]
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
                ActionParameter("MESSAGE", ParameterType.INSECURE_STRING, "Message to echo", "Default Message")
            ]
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
                ActionParameter("MESSAGE", ParameterType.INSECURE_STRING, "Message to echo")
            ]
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
            run_path="subdir"
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
            run_path="../outside"
        )
        
        with pytest.raises(ExecutionError) as context:
            self.executor.execute_action(action, {})
        
        assert "Invalid run_path" in str(context.value)
