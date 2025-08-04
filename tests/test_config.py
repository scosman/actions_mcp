import tempfile
import pytest
from pathlib import Path
from actions_mcp.config import ActionsMCPConfig, ConfigError


class TestConfig:
    """Test configuration parsing functionality."""
    
    def test_valid_config_minimal(self):
        """Test parsing a minimal valid configuration."""
        yaml_content = """
actions:
  - name: "test"
    description: "Run tests"
    command: "python -m pytest"
"""
        
        with tempfile.NamedTemporaryFile(mode='w', suffix='.yaml', delete=False) as f:
            f.write(yaml_content)
            f.flush()
            
            config = ActionsMCPConfig.from_yaml(f.name)
            
            # Clean up
            Path(f.name).unlink()
        
        assert config.server_name == "ActionsMCP"
        assert config.server_description == "Project-specific development tools exposed via MCP"
        assert len(config.actions) == 1
        
        action = config.actions[0]
        assert action.name == "test"
        assert action.description == "Run tests"
        assert action.command == "python -m pytest"
        assert action.run_path is None
        assert len(action.parameters) == 0
    
    def test_valid_config_full(self):
        """Test parsing a full valid configuration."""
        yaml_content = """
server_name: "MyProjectTools"
server_description: "Development tools for MyProject"

actions:
  - name: "all_tests"
    description: "Run all tests"
    command: "python -m pytest"
    run_path: "tests"
    
  - name: "test_file"
    description: "Run tests in a specific file"
    command: "python -m pytest $TEST_FILE"
    parameters:
      - name: "TEST_FILE"
        type: "project_file_path"
        description: "Path to test file"
        default: "./tests"
        
  - name: "lint"
    description: "Lint the code"
    command: "flake8 src"
    parameters:
      - name: "SKIP_CHECKS"
        type: "insecure_string"
        description: "Checks to skip"
        
  - name: "typecheck"
    description: "Typecheck the code"
    command: "mypy src"
    parameters:
      - name: "MY_API_KEY"
        type: "required_env_var"
        description: "API key for my service"
        
      - name: "VERBOSE"
        type: "optional_env_var"
        description: "Enable verbose output"
"""
        
        with tempfile.NamedTemporaryFile(mode='w', suffix='.yaml', delete=False) as f:
            f.write(yaml_content)
            f.flush()
            
            config = ActionsMCPConfig.from_yaml(f.name)
            
            # Clean up
            Path(f.name).unlink()
        
        assert config.server_name == "MyProjectTools"
        assert config.server_description == "Development tools for MyProject"
        assert len(config.actions) == 4
        
        # Check first action
        action1 = config.actions[0]
        assert action1.name == "all_tests"
        assert action1.description == "Run all tests"
        assert action1.command == "python -m pytest"
        assert action1.run_path == "tests"
        assert len(action1.parameters) == 0
        
        # Check second action
        action2 = config.actions[1]
        assert action2.name == "test_file"
        assert action2.description == "Run tests in a specific file"
        assert action2.command == "python -m pytest $TEST_FILE"
        assert len(action2.parameters) == 1
        
        param1 = action2.parameters[0]
        assert param1.name == "TEST_FILE"
        assert param1.type == "project_file_path"
        assert param1.description == "Path to test file"
        assert param1.default == "./tests"
        
        # Check third action
        action3 = config.actions[2]
        assert action3.name == "lint"
        assert action3.description == "Lint the code"
        assert action3.command == "flake8 src"
        assert len(action3.parameters) == 1
        
        param2 = action3.parameters[0]
        assert param2.name == "SKIP_CHECKS"
        assert param2.type == "insecure_string"
        assert param2.description == "Checks to skip"
        assert param2.default is None
        
        # Check fourth action
        action4 = config.actions[3]
        assert action4.name == "typecheck"
        assert action4.description == "Typecheck the code"
        assert action4.command == "mypy src"
        assert len(action4.parameters) == 2
        
        param3 = action4.parameters[0]
        assert param3.name == "MY_API_KEY"
        assert param3.type == "required_env_var"
        assert param3.description == "API key for my service"
        assert param3.default is None
        
        param4 = action4.parameters[1]
        assert param4.name == "VERBOSE"
        assert param4.type == "optional_env_var"
        assert param4.description == "Enable verbose output"
        assert param4.default is None
    
    def test_invalid_config_missing_actions(self):
        """Test that config without actions raises an error."""
        yaml_content = """
server_name: "MyProjectTools"
server_description: "Development tools for MyProject"
"""
        
        with tempfile.NamedTemporaryFile(mode='w', suffix='.yaml', delete=False) as f:
            f.write(yaml_content)
            f.flush()
            
            with pytest.raises(ConfigError) as context:
                ActionsMCPConfig.from_yaml(f.name)
            
            # Clean up
            Path(f.name).unlink()
        
        assert "'actions' array is required" in str(context.value)
    
    def test_invalid_config_invalid_parameter_type(self):
        """Test that config with invalid parameter type raises an error."""
        yaml_content = """
actions:
  - name: "test"
    description: "Run tests"
    command: "python -m pytest"
    parameters:
      - name: "TEST_FILE"
        type: "invalid_type"
        description: "Path to test file"
"""
        
        with tempfile.NamedTemporaryFile(mode='w', suffix='.yaml', delete=False) as f:
            f.write(yaml_content)
            f.flush()
            
            with pytest.raises(ConfigError) as context:
                ActionsMCPConfig.from_yaml(f.name)
            
            # Clean up
            Path(f.name).unlink()
        
        assert "Invalid parameter type" in str(context.value)
        assert "invalid_type" in str(context.value)
    
    def test_invalid_config_missing_required_fields(self):
        """Test that config with missing required fields raises an error."""
        yaml_content = """
actions:
  - description: "Run tests"
    command: "python -m pytest"
"""
        
        with tempfile.NamedTemporaryFile(mode='w', suffix='.yaml', delete=False) as f:
            f.write(yaml_content)
            f.flush()
            
            with pytest.raises(ConfigError) as context:
                ActionsMCPConfig.from_yaml(f.name)
            
            # Clean up
            Path(f.name).unlink()
        
        assert "'name' is required" in str(context.value)
    
    def test_config_validate_required_env_vars(self):
        """Test validation of required environment variables."""
        yaml_content = """
actions:
  - name: "test"
    description: "Run tests"
    command: "python -m pytest"
    parameters:
      - name: "API_KEY"
        type: "required_env_var"
        description: "API key"
        
      - name: "OPTIONAL_VAR"
        type: "optional_env_var"
        description: "Optional variable"
"""
        
        with tempfile.NamedTemporaryFile(mode='w', suffix='.yaml', delete=False) as f:
            f.write(yaml_content)
            f.flush()
            
            config = ActionsMCPConfig.from_yaml(f.name)
            
            # Clean up
            Path(f.name).unlink()
        
        # Initially, no env vars are set, so API_KEY should be missing
        missing_vars = config.validate_required_env_vars()
        assert "API_KEY" in missing_vars
        assert "OPTIONAL_VAR" not in missing_vars
        
        # Set the required env var and check again
        import os
        os.environ["API_KEY"] = "test_key"
        
        missing_vars = config.validate_required_env_vars()
        assert "API_KEY" not in missing_vars
        
        # Clean up
        del os.environ["API_KEY"]
