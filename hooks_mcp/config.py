import os
from pathlib import Path
from typing import Any, Dict, List, Optional

import yaml


class ConfigError(Exception):
    """Exception raised for errors in the HooksMCP configuration."""

    pass


class PromptArgument:
    """Represents an argument for a prompt template."""

    def __init__(
        self,
        name: str,
        description: Optional[str] = None,
        required: bool = False,
    ):
        self.name = name
        self.description = description
        self.required = required

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "PromptArgument":
        """Create a PromptArgument from a dictionary."""
        name = data.get("name")
        description = data.get("description")
        required = data.get("required", False)

        if not name:
            raise ConfigError(
                "HooksMCP Error: 'name' is required for each prompt argument"
            )

        return cls(name, description, required)


class Prompt:
    """Represents a prompt template."""

    def __init__(
        self,
        name: str,
        description: str,
        prompt_text: Optional[str] = None,
        prompt_file: Optional[str] = None,
        arguments: Optional[List[PromptArgument]] = None,
    ):
        self.name = name
        self.description = description
        self.prompt_text = prompt_text
        self.prompt_file = prompt_file
        self.arguments = arguments or []

        # Validate that exactly one of prompt_text or prompt_file is provided
        if prompt_text is None and prompt_file is None:
            raise ConfigError(
                f"HooksMCP Error: Prompt '{name}' must specify either 'prompt' or 'prompt-file'"
            )
        if prompt_text is not None and prompt_file is not None:
            raise ConfigError(
                f"HooksMCP Error: Prompt '{name}' cannot specify both 'prompt' and 'prompt-file'"
            )

    @classmethod
    def from_dict(cls, data: Dict[str, Any], config_dir: Path) -> "Prompt":
        """Create a Prompt from a dictionary."""
        name = data.get("name")
        description = data.get("description")
        prompt_text = data.get("prompt")
        prompt_file = data.get("prompt-file")
        arguments_data = data.get("arguments")

        if not name:
            raise ConfigError("HooksMCP Error: 'name' is required for each prompt")
        if not description:
            raise ConfigError(
                "HooksMCP Error: 'description' is required for each prompt"
            )

        # Validate name and description length limits
        if len(name) > 32:
            raise ConfigError(
                f"HooksMCP Error: Prompt name '{name}' exceeds 32 character limit"
            )
        if len(description) > 256:
            raise ConfigError(
                f"HooksMCP Error: Prompt description for '{name}' exceeds 256 character limit"
            )

        arguments = []
        if arguments_data:
            if not isinstance(arguments_data, list):
                raise ConfigError(
                    f"HooksMCP Error: 'arguments' must be a list for prompt '{name}'"
                )

            for i, arg_data in enumerate(arguments_data):
                if not isinstance(arg_data, dict):
                    raise ConfigError(
                        f"HooksMCP Error: Each prompt argument must be an object (prompt '{name}', argument[{i}])"
                    )
                try:
                    argument = PromptArgument.from_dict(arg_data)
                    arguments.append(argument)
                except ConfigError:
                    # Re-raise config errors as-is
                    raise
                except Exception as e:
                    raise ConfigError(
                        f"HooksMCP Error: Failed to parse argument[{i}] for prompt '{name}': {str(e)}"
                    )

        prompt = cls(name, description, prompt_text, prompt_file, arguments)

        # If prompt-file is specified, verify the file exists
        if prompt.prompt_file:
            prompt_file_path = config_dir / prompt.prompt_file
            if not prompt_file_path.exists():
                raise ConfigError(
                    f"HooksMCP Error: Prompt file '{prompt.prompt_file}' for prompt '{name}' not found at {prompt_file_path}"
                )

        return prompt


class ParameterType:
    """Enumeration of parameter types."""

    PROJECT_FILE_PATH = "project_file_path"
    REQUIRED_ENV_VAR = "required_env_var"
    OPTIONAL_ENV_VAR = "optional_env_var"
    INSECURE_STRING = "insecure_string"


class ActionParameter:
    """Represents a parameter for an action."""

    def __init__(
        self,
        name: str,
        param_type: str,
        description: Optional[str] = None,
        default: Optional[str] = None,
    ):
        self.name = name
        self.type = param_type
        self.description = description
        self.default = default

    def to_dict(self) -> Dict[str, Any]:
        """Convert parameter to dictionary for MCP tool definition."""
        result = {
            "name": self.name,
            "type": self.type,
            "description": self.description or f"Parameter {self.name}",
        }
        if self.default is not None:
            result["default"] = self.default
        return result


class Action:
    """Represents a single action defined in the configuration."""

    def __init__(
        self,
        name: str,
        description: str,
        command: str,
        parameters: Optional[List[ActionParameter]] = None,
        run_path: Optional[str] = None,
        timeout: int = 60,
    ):
        self.name = name
        self.description = description
        self.command = command
        self.parameters = parameters or []
        self.run_path = run_path
        self.timeout = timeout

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "Action":
        """Create an Action from a dictionary."""
        name = data.get("name")
        description = data.get("description")
        command = data.get("command")

        if not name:
            raise ConfigError("HooksMCP Error: 'name' is required for each action")
        if not description:
            raise ConfigError(
                "HooksMCP Error: 'description' is required for each action"
            )
        if not command:
            raise ConfigError("HooksMCP Error: 'command' is required for each action")

        parameters = []
        if "parameters" in data:
            for param_data in data["parameters"]:
                param_name = param_data.get("name")
                param_type = param_data.get("type")
                param_description = param_data.get("description")
                param_default = param_data.get("default")

                if not param_name:
                    raise ConfigError(
                        f"HooksMCP Error: 'name' is required for each parameter in action '{name}'"
                    )
                if not param_type:
                    raise ConfigError(
                        f"HooksMCP Error: 'type' is required for parameter '{param_name}' in action '{name}'"
                    )

                if param_type not in [
                    ParameterType.PROJECT_FILE_PATH,
                    ParameterType.REQUIRED_ENV_VAR,
                    ParameterType.OPTIONAL_ENV_VAR,
                    ParameterType.INSECURE_STRING,
                ]:
                    raise ConfigError(
                        f"HooksMCP Error: Invalid parameter type '{param_type}' for parameter '{param_name}' in action '{name}'. "
                        f"Valid types are: project_file_path, required_env_var, optional_env_var, insecure_string"
                    )

                parameters.append(
                    ActionParameter(
                        param_name, param_type, param_description, param_default
                    )
                )

        return cls(
            name,
            description,
            command,
            parameters,
            data.get("run_path"),
            data.get("timeout", 60),
        )


class HooksMCPConfig:
    """Main configuration class for HooksMCP."""

    def __init__(
        self,
        actions: List[Action],
        prompts: Optional[List[Prompt]] = None,
        get_prompt_tool_filter: Optional[List[str]] = None,
        server_name: Optional[str] = None,
        server_description: Optional[str] = None,
    ):
        self.actions = actions
        self.prompts = prompts or []
        self.get_prompt_tool_filter = get_prompt_tool_filter
        self.server_name = server_name or "HooksMCP"
        self.server_description = (
            server_description
            or "Project-specific development tools and prompts exposed via MCP"
        )

        # Validate get_prompt_tool_filter if provided
        if self.get_prompt_tool_filter is not None:
            prompt_names = {prompt.name for prompt in self.prompts}
            for filter_name in self.get_prompt_tool_filter:
                if filter_name not in prompt_names:
                    raise ConfigError(
                        f"HooksMCP Error: Prompt '{filter_name}' in get_prompt_tool_filter not found in prompts list"
                    )

    @classmethod
    def from_yaml(cls, yaml_path: str) -> "HooksMCPConfig":
        """Load configuration from a YAML file."""
        if not os.path.exists(yaml_path):
            raise ConfigError(
                f"HooksMCP Error: Configuration file '{yaml_path}' not found"
            )

        try:
            with open(yaml_path, "r") as f:
                data = yaml.safe_load(f)
        except yaml.YAMLError as e:
            raise ConfigError(
                f"HooksMCP Error: Failed to parse YAML file '{yaml_path}': {str(e)}"
            )
        except Exception as e:
            raise ConfigError(
                f"HooksMCP Error: Failed to read configuration file '{yaml_path}': {str(e)}"
            )

        if not isinstance(data, dict):
            raise ConfigError(
                "HooksMCP Error: Configuration file must contain a YAML object"
            )

        actions_data = data.get("actions", [])
        if not isinstance(actions_data, list):
            raise ConfigError("HooksMCP Error: 'actions' must be an array")

        actions = []
        for i, action_data in enumerate(actions_data):
            if not isinstance(action_data, dict):
                raise ConfigError(
                    f"HooksMCP Error: Each action must be an object (action[{i}])"
                )
            try:
                action = Action.from_dict(action_data)
                actions.append(action)
            except ConfigError:
                # Re-raise config errors as-is
                raise
            except Exception as e:
                raise ConfigError(
                    f"HooksMCP Error: Failed to parse action[{i}]: {str(e)}"
                )

        # Parse prompts if present
        prompts = []
        prompts_data = data.get("prompts")
        if prompts_data:
            if not isinstance(prompts_data, list):
                raise ConfigError("HooksMCP Error: 'prompts' must be an array")

            config_dir = Path(yaml_path).parent
            for i, prompt_data in enumerate(prompts_data):
                if not isinstance(prompt_data, dict):
                    raise ConfigError(
                        f"HooksMCP Error: Each prompt must be an object (prompt[{i}])"
                    )
                try:
                    prompt = Prompt.from_dict(prompt_data, config_dir)
                    prompts.append(prompt)
                except ConfigError:
                    # Re-raise config errors as-is
                    raise
                except Exception as e:
                    raise ConfigError(
                        f"HooksMCP Error: Failed to parse prompt[{i}]: {str(e)}"
                    )

        return cls(
            actions=actions,
            prompts=prompts,
            get_prompt_tool_filter=data.get("get_prompt_tool_filter"),
            server_name=data.get("server_name"),
            server_description=data.get("server_description"),
        )

    def validate_required_env_vars(self) -> List[str]:
        """Check which required environment variables are not set and return their names."""
        missing_vars = []
        for action in self.actions:
            for param in action.parameters:
                if param.type == ParameterType.REQUIRED_ENV_VAR:
                    if not os.environ.get(param.name):
                        missing_vars.append(param.name)
        return missing_vars
