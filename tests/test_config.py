import tempfile
from pathlib import Path

import pytest

from hooks_mcp.config import ConfigError, HooksMCPConfig


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

        with tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False) as f:
            f.write(yaml_content)
            f.flush()

            config = HooksMCPConfig.from_yaml(f.name)

            # Clean up
            Path(f.name).unlink()

        assert config.server_name == "HooksMCP"
        assert (
            config.server_description
            == "Project-specific development tools and prompts exposed via MCP"
        )
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

        with tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False) as f:
            f.write(yaml_content)
            f.flush()

            config = HooksMCPConfig.from_yaml(f.name)

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

    def test_valid_config_missing_actions(self):
        """Test that config without actions is valid."""
        yaml_content = """
server_name: "MyProjectTools"
server_description: "Development tools for MyProject"
"""

        with tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False) as f:
            f.write(yaml_content)
            f.flush()

            config = HooksMCPConfig.from_yaml(f.name)

            # Clean up
            Path(f.name).unlink()

        assert config.server_name == "MyProjectTools"
        assert config.server_description == "Development tools for MyProject"
        assert len(config.actions) == 0

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

        with tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False) as f:
            f.write(yaml_content)
            f.flush()

            with pytest.raises(ConfigError) as context:
                HooksMCPConfig.from_yaml(f.name)

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

        with tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False) as f:
            f.write(yaml_content)
            f.flush()

            with pytest.raises(ConfigError) as context:
                HooksMCPConfig.from_yaml(f.name)

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

        with tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False) as f:
            f.write(yaml_content)
            f.flush()

            config = HooksMCPConfig.from_yaml(f.name)

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

    def test_config_with_timeout(self):
        """Test parsing a configuration with timeout parameter."""
        yaml_content = """
actions:
  - name: "test_with_timeout"
    description: "Test action with custom timeout"
    command: "sleep 10"
    timeout: 30
    
  - name: "test_without_timeout"
    description: "Test action without timeout"
    command: "echo Hello"
"""

        with tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False) as f:
            f.write(yaml_content)
            f.flush()

            config = HooksMCPConfig.from_yaml(f.name)

            # Clean up
            Path(f.name).unlink()

        assert len(config.actions) == 2

        # Check action with timeout
        action1 = config.actions[0]
        assert action1.name == "test_with_timeout"
        assert action1.description == "Test action with custom timeout"
        assert action1.command == "sleep 10"
        assert action1.timeout == 30

        # Check action without timeout (should use default)
        action2 = config.actions[1]
        assert action2.name == "test_without_timeout"
        assert action2.description == "Test action without timeout"
        assert action2.command == "echo Hello"
        assert action2.timeout == 60  # Default timeout

    def test_valid_config_with_prompts_inline(self):
        """Test parsing a configuration with inline prompts."""
        yaml_content = """
actions:
  - name: "test"
    description: "Run tests"
    command: "python -m pytest"

prompts:
  - name: "code_review"
    description: "Review code for best practices"
    prompt: "Please review this code for best practices and potential bugs."
    
  - name: "test_generation"
    description: "Generate unit tests for code"
    prompt: "Generate unit tests for the following code:\n$CODE_SNIPPET"
    arguments:
      - name: "CODE_SNIPPET"
        description: "The code to generate tests for"
        required: true
"""

        with tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False) as f:
            f.write(yaml_content)
            f.flush()
            temp_path = Path(f.name)

        try:
            config = HooksMCPConfig.from_yaml(str(temp_path))
        finally:
            # Clean up
            temp_path.unlink()

        assert len(config.prompts) == 2

        # Check first prompt
        prompt1 = config.prompts[0]
        assert prompt1.name == "code_review"
        assert prompt1.description == "Review code for best practices"
        assert (
            prompt1.prompt_text
            == "Please review this code for best practices and potential bugs."
        )
        assert prompt1.prompt_file is None
        assert len(prompt1.arguments) == 0

        # Check second prompt
        prompt2 = config.prompts[1]
        assert prompt2.name == "test_generation"
        assert prompt2.description == "Generate unit tests for code"
        # Check that the prompt text contains the expected content (exact formatting may vary)
        assert prompt2.prompt_text is not None
        assert "Generate unit tests for the following code:" in prompt2.prompt_text
        assert "$CODE_SNIPPET" in prompt2.prompt_text
        assert prompt2.prompt_file is None
        assert len(prompt2.arguments) == 1

        arg1 = prompt2.arguments[0]
        assert arg1.name == "CODE_SNIPPET"
        assert arg1.description == "The code to generate tests for"
        assert arg1.required

    def test_valid_config_with_prompts_file(self):
        """Test parsing a configuration with file-based prompts."""
        # Create a temporary directory for both files
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_dir_path = Path(temp_dir)

            # Create the prompt file
            prompt_file_path = temp_dir_path / "test_prompt.md"
            with open(prompt_file_path, "w") as prompt_file:
                prompt_file.write(
                    "# Code Analysis Prompt\n\nAnalyze the following code snippet."
                )

            # Create the config file
            yaml_content = """
actions:
  - name: "test"
    description: "Run tests"
    command: "python -m pytest"

prompts:
  - name: "code_analysis"
    description: "Analyze code for quality and security"
    prompt-file: "test_prompt.md"

  - name: "architecture_review"
    description: "Review system architecture"
    prompt-file: "test_prompt.md"
    arguments:
      - name: "SYSTEM_COMPONENT"
        description: "The system component to review"
        required: false
"""

            config_file_path = temp_dir_path / "test_config.yaml"
            with open(config_file_path, "w") as config_file:
                config_file.write(yaml_content)

            try:
                config = HooksMCPConfig.from_yaml(str(config_file_path))
            finally:
                # Clean up
                config_file_path.unlink()

        assert len(config.prompts) == 2

        # Check first prompt
        prompt1 = config.prompts[0]
        assert prompt1.name == "code_analysis"
        assert prompt1.description == "Analyze code for quality and security"
        assert prompt1.prompt_text is None
        assert prompt1.prompt_file == "test_prompt.md"
        assert len(prompt1.arguments) == 0

        # Check second prompt
        prompt2 = config.prompts[1]
        assert prompt2.name == "architecture_review"
        assert prompt2.description == "Review system architecture"
        assert prompt2.prompt_text is None
        assert prompt2.prompt_file == "test_prompt.md"
        assert len(prompt2.arguments) == 1

        arg1 = prompt2.arguments[0]
        assert arg1.name == "SYSTEM_COMPONENT"
        assert arg1.description == "The system component to review"
        assert not arg1.required

    def test_invalid_config_prompt_missing_required_fields(self):
        """Test that prompts with missing required fields raise an error."""
        yaml_content = """
actions:
  - name: "test"
    description: "Run tests"
    command: "python -m pytest"

prompts:
  - description: "A prompt without a name"
    prompt: "Some prompt content"
"""

        with tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False) as f:
            f.write(yaml_content)
            f.flush()

            with pytest.raises(ConfigError) as context:
                HooksMCPConfig.from_yaml(f.name)

            # Clean up
            Path(f.name).unlink()

        assert "'name' is required for each prompt" in str(context.value)

    def test_invalid_config_prompt_no_content(self):
        """Test that prompts without content raise an error."""
        yaml_content = """
actions:
  - name: "test"
    description: "Run tests"
    command: "python -m pytest"

prompts:
  - name: "invalid_prompt"
    description: "A prompt with no content"
"""

        with tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False) as f:
            f.write(yaml_content)
            f.flush()

            with pytest.raises(ConfigError) as context:
                HooksMCPConfig.from_yaml(f.name)

            # Clean up
            Path(f.name).unlink()

        assert "must specify either 'prompt' or 'prompt-file'" in str(context.value)

    def test_invalid_config_prompt_both_content_types(self):
        """Test that prompts with both content types raise an error."""
        yaml_content = """
actions:
  - name: "test"
    description: "Run tests"
    command: "python -m pytest"

prompts:
  - name: "invalid_prompt"
    description: "A prompt with both content types"
    prompt: "Inline prompt content"
    prompt-file: "./some_file.md"
"""

        with tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False) as f:
            f.write(yaml_content)
            f.flush()

            with pytest.raises(ConfigError) as context:
                HooksMCPConfig.from_yaml(f.name)

            # Clean up
            Path(f.name).unlink()

        assert "cannot specify both 'prompt' and 'prompt-file'" in str(context.value)

    def test_invalid_config_prompt_name_too_long(self):
        """Test that prompts with names exceeding 32 characters raise an error."""
        long_name = "a" * 33  # 33 characters, exceeds limit of 32
        yaml_content = f"""
actions:
  - name: "test"
    description: "Run tests"
    command: "python -m pytest"

prompts:
  - name: "{long_name}"
    description: "A prompt with a very long name"
    prompt: "Some prompt content"
"""

        with tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False) as f:
            f.write(yaml_content)
            f.flush()

            with pytest.raises(ConfigError) as context:
                HooksMCPConfig.from_yaml(f.name)

            # Clean up
            Path(f.name).unlink()

        assert "exceeds 32 character limit" in str(context.value)

    def test_invalid_config_prompt_description_too_long(self):
        """Test that prompts with descriptions exceeding 256 characters raise an error."""
        long_description = "A" * 257  # 257 characters, exceeds limit of 256
        yaml_content = f"""
actions:
  - name: "test"
    description: "Run tests"
    command: "python -m pytest"

prompts:
  - name: "test_prompt"
    description: "{long_description}"
    prompt: "Some prompt content"
"""

        with tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False) as f:
            f.write(yaml_content)
            f.flush()

            with pytest.raises(ConfigError) as context:
                HooksMCPConfig.from_yaml(f.name)

            # Clean up
            Path(f.name).unlink()

        assert "exceeds 256 character limit" in str(context.value)

    def test_invalid_config_prompt_file_not_found(self):
        """Test that prompts with non-existent files raise an error."""
        yaml_content = """
actions:
  - name: "test"
    description: "Run tests"
    command: "python -m pytest"

prompts:
  - name: "missing_file_prompt"
    description: "A prompt referencing a missing file"
    prompt-file: "./non_existent_file.md"
"""

        with tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False) as f:
            f.write(yaml_content)
            f.flush()

            with pytest.raises(ConfigError) as context:
                HooksMCPConfig.from_yaml(f.name)

            # Clean up
            Path(f.name).unlink()

        assert (
            "Prompt file './non_existent_file.md' for prompt 'missing_file_prompt' not found"
            in str(context.value)
        )

    def test_invalid_config_prompt_argument_missing_name(self):
        """Test that prompt arguments without names raise an error."""
        yaml_content = """
actions:
  - name: "test"
    description: "Run tests"
    command: "python -m pytest"

prompts:
  - name: "test_prompt"
    description: "A prompt with invalid arguments"
    prompt: "Some content with $ARG"
    arguments:
      - description: "Argument without name"
        required: true
"""

        with tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False) as f:
            f.write(yaml_content)
            f.flush()

            with pytest.raises(ConfigError) as context:
                HooksMCPConfig.from_yaml(f.name)

            # Clean up
            Path(f.name).unlink()

        assert "'name' is required for each prompt argument" in str(context.value)

    def test_valid_config_get_prompt_tool_filter(self):
        """Test parsing a configuration with get_prompt_tool_filter."""
        yaml_content = """
actions:
  - name: "test"
    description: "Run tests"
    command: "python -m pytest"

prompts:
  - name: "prompt1"
    description: "First prompt"
    prompt: "Content of first prompt"
    
  - name: "prompt2"
    description: "Second prompt"
    prompt: "Content of second prompt"

get_prompt_tool_filter:
  - "prompt1"
"""

        with tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False) as f:
            f.write(yaml_content)
            f.flush()

            config = HooksMCPConfig.from_yaml(f.name)

            # Clean up
            Path(f.name).unlink()

        assert len(config.prompts) == 2
        assert config.get_prompt_tool_filter == ["prompt1"]

    def test_invalid_config_get_prompt_tool_filter_invalid_name(self):
        """Test that get_prompt_tool_filter with invalid prompt names raises an error."""
        yaml_content = """
actions:
  - name: "test"
    description: "Run tests"
    command: "python -m pytest"

prompts:
  - name: "prompt1"
    description: "First prompt"
    prompt: "Content of first prompt"

get_prompt_tool_filter:
  - "nonexistent_prompt"
"""

        with tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False) as f:
            f.write(yaml_content)
            f.flush()

            with pytest.raises(ConfigError) as context:
                HooksMCPConfig.from_yaml(f.name)

            # Clean up
            Path(f.name).unlink()

        assert (
            "Prompt 'nonexistent_prompt' in get_prompt_tool_filter not found in prompts list"
            in str(context.value)
        )

    def test_config_get_prompt_tool_filter_empty_list(self):
        """Test that empty get_prompt_tool_filter list is handled correctly."""
        yaml_content = """
actions:
  - name: "test"
    description: "Run tests"
    command: "python -m pytest"

prompts:
  - name: "prompt1"
    description: "First prompt"
    prompt: "Content of first prompt"

get_prompt_tool_filter: []
"""

        with tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False) as f:
            f.write(yaml_content)
            f.flush()

            config = HooksMCPConfig.from_yaml(f.name)

            # Clean up
            Path(f.name).unlink()

        assert len(config.prompts) == 1
        assert config.get_prompt_tool_filter == []

    def test_valid_config_prompts_only(self):
        """Test parsing a configuration with only prompts and no actions."""
        yaml_content = """
prompts:
  - name: "code_review"
    description: "Review code for best practices"
    prompt: "Please review this code for best practices and potential bugs."
    
  - name: "test_generation"
    description: "Generate unit tests for code"
    prompt: "Generate unit tests for the following code:\n$CODE_SNIPPET"
    arguments:
      - name: "CODE_SNIPPET"
        description: "The code to generate tests for"
        required: true
"""

        with tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False) as f:
            f.write(yaml_content)
            f.flush()

            config = HooksMCPConfig.from_yaml(f.name)

            # Clean up
            Path(f.name).unlink()

        assert config.server_name == "HooksMCP"
        assert (
            config.server_description
            == "Project-specific development tools and prompts exposed via MCP"
        )
        assert len(config.actions) == 0
        assert len(config.prompts) == 2

        # Check first prompt
        prompt1 = config.prompts[0]
        assert prompt1.name == "code_review"
        assert prompt1.description == "Review code for best practices"
        assert (
            prompt1.prompt_text
            == "Please review this code for best practices and potential bugs."
        )
        assert prompt1.prompt_file is None
        assert len(prompt1.arguments) == 0

        # Check second prompt
        prompt2 = config.prompts[1]
        assert prompt2.name == "test_generation"
        assert prompt2.description == "Generate unit tests for code"
        assert prompt2.prompt_text is not None
        assert "$CODE_SNIPPET" in prompt2.prompt_text
        assert prompt2.prompt_file is None
        assert len(prompt2.arguments) == 1

        arg1 = prompt2.arguments[0]
        assert arg1.name == "CODE_SNIPPET"
        assert arg1.description == "The code to generate tests for"
        assert arg1.required
