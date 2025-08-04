import os
import tempfile
import pytest
from pathlib import Path
from actions_mcp.utils import validate_project_path
from actions_mcp.config import Action, ActionParameter, ParameterType
from actions_mcp.executor import CommandExecutor, ExecutionError


class TestSecurity:
    """Test security features of ActionsMCP."""
    
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
        
        self.executor = CommandExecutor(self.project_root)
        
        # This will run after each test
        yield
        
        # Clean up test environment
        self.temp_dir.cleanup()
    
    def test_validate_project_path_safe_paths(self):
        """Test that safe paths are validated correctly."""
        # Test valid paths
        assert validate_project_path("./tests/test1.py", self.project_root)
        assert validate_project_path("tests/test1.py", self.project_root)
        assert validate_project_path("./src/main.py", self.project_root)
        assert validate_project_path("src/main.py", self.project_root)
        assert validate_project_path("./", self.project_root)
        assert validate_project_path(".", self.project_root)
    
    def test_validate_project_path_dangerous_paths(self):
        """Test that dangerous paths are rejected."""
        # Test paths that break out of project root
        assert not validate_project_path("../outside.py", self.project_root)
        assert not validate_project_path("~/secret.py", self.project_root)
        assert not validate_project_path("$HOME/secret.py", self.project_root)
        assert not validate_project_path("./../outside.py", self.project_root)
        assert not validate_project_path("tests/../../outside.py", self.project_root)
    
    def test_validate_project_path_nonexistent_paths(self):
        """Test that nonexistent paths are still validated correctly."""
        # Nonexistent paths should still pass validation if they're within project boundaries
        assert validate_project_path("./tests/nonexistent.py", self.project_root)
        assert validate_project_path("tests/nonexistent.py", self.project_root)
        
        # But dangerous nonexistent paths should still be rejected
        assert not validate_project_path("../nonexistent.py", self.project_root)
    
    def test_command_executor_safe_path(self):
        """Test that command executor accepts safe paths."""
        action = Action(
            name="test_action",
            description="Test action",
            command="echo Testing",
            parameters=[
                ActionParameter("file_path", ParameterType.PROJECT_FILE_PATH, "A file path", "tests/test1.py")
            ]
        )
        
        # This should not raise an exception
        result = self.executor.execute_action(action, {"file_path": "tests/test1.py"})
        assert "Testing" in result["stdout"]
    
    def test_command_executor_dangerous_path(self):
        """Test that command executor rejects dangerous paths."""
        action = Action(
            name="test_action",
            description="Test action",
            command="echo Testing",
            parameters=[
                ActionParameter("file_path", ParameterType.PROJECT_FILE_PATH, "A file path")
            ]
        )
        
        # These should raise ExecutionError
        with pytest.raises(ExecutionError):
            self.executor.execute_action(action, {"file_path": "../outside.py"})
        
        with pytest.raises(ExecutionError):
            self.executor.execute_action(action, {"file_path": "~/secret.py"})
        
        with pytest.raises(ExecutionError):
            self.executor.execute_action(action, {"file_path": "$HOME/secret.py"})
    
    def test_command_executor_insecure_string(self):
        """Test that insecure strings are passed through without validation."""
        action = Action(
            name="test_action",
            description="Test action",
            command="echo $TEST_STRING",
            parameters=[
                ActionParameter("TEST_STRING", ParameterType.INSECURE_STRING, "An insecure string")
            ]
        )
        
        # This should work even with potentially dangerous content
        # (though the command itself won't do anything harmful)
        result = self.executor.execute_action(action, {"TEST_STRING": "123 && rm -r ~"})
        assert "123 && rm -r ~" in result["stdout"]
