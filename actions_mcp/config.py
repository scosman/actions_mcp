import os
from typing import Any, Dict, List, Optional

import yaml


class ConfigError(Exception):
    """Exception raised for errors in the ActionsMCP configuration."""

    pass


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
            raise ConfigError("ActionsMCP Error: 'name' is required for each action")
        if not description:
            raise ConfigError(
                "ActionsMCP Error: 'description' is required for each action"
            )
        if not command:
            raise ConfigError("ActionsMCP Error: 'command' is required for each action")

        parameters = []
        if "parameters" in data:
            for param_data in data["parameters"]:
                param_name = param_data.get("name")
                param_type = param_data.get("type")
                param_description = param_data.get("description")
                param_default = param_data.get("default")

                if not param_name:
                    raise ConfigError(
                        f"ActionsMCP Error: 'name' is required for each parameter in action '{name}'"
                    )
                if not param_type:
                    raise ConfigError(
                        f"ActionsMCP Error: 'type' is required for parameter '{param_name}' in action '{name}'"
                    )

                if param_type not in [
                    ParameterType.PROJECT_FILE_PATH,
                    ParameterType.REQUIRED_ENV_VAR,
                    ParameterType.OPTIONAL_ENV_VAR,
                    ParameterType.INSECURE_STRING,
                ]:
                    raise ConfigError(
                        f"ActionsMCP Error: Invalid parameter type '{param_type}' for parameter '{param_name}' in action '{name}'. "
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


class ActionsMCPConfig:
    """Main configuration class for ActionsMCP."""

    def __init__(
        self,
        actions: List[Action],
        server_name: Optional[str] = None,
        server_description: Optional[str] = None,
    ):
        self.actions = actions
        self.server_name = server_name or "ActionsMCP"
        self.server_description = (
            server_description or "Project-specific development tools exposed via MCP"
        )

    @classmethod
    def from_yaml(cls, yaml_path: str) -> "ActionsMCPConfig":
        """Load configuration from a YAML file."""
        if not os.path.exists(yaml_path):
            raise ConfigError(
                f"ActionsMCP Error: Configuration file '{yaml_path}' not found"
            )

        try:
            with open(yaml_path, "r") as f:
                data = yaml.safe_load(f)
        except yaml.YAMLError as e:
            raise ConfigError(
                f"ActionsMCP Error: Failed to parse YAML file '{yaml_path}': {str(e)}"
            )
        except Exception as e:
            raise ConfigError(
                f"ActionsMCP Error: Failed to read configuration file '{yaml_path}': {str(e)}"
            )

        if not isinstance(data, dict):
            raise ConfigError(
                "ActionsMCP Error: Configuration file must contain a YAML object"
            )

        actions_data = data.get("actions")
        if not actions_data:
            raise ConfigError(
                "ActionsMCP Error: 'actions' array is required in configuration file"
            )

        if not isinstance(actions_data, list):
            raise ConfigError("ActionsMCP Error: 'actions' must be an array")

        actions = []
        for i, action_data in enumerate(actions_data):
            if not isinstance(action_data, dict):
                raise ConfigError(
                    f"ActionsMCP Error: Each action must be an object (action[{i}])"
                )
            try:
                action = Action.from_dict(action_data)
                actions.append(action)
            except ConfigError:
                # Re-raise config errors as-is
                raise
            except Exception as e:
                raise ConfigError(
                    f"ActionsMCP Error: Failed to parse action[{i}]: {str(e)}"
                )

        return cls(
            actions=actions,
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
