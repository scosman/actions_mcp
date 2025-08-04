import subprocess
import os
import shlex
from pathlib import Path
from typing import Dict, Any, Optional, List
from .config import Action, ParameterType, ConfigError
from .utils import validate_project_path, process_terminal_output


class ExecutionError(Exception):
    """Exception raised for errors during command execution."""
    pass


class CommandExecutor:
    """Handles secure execution of commands defined in ActionsMCP configuration."""
    
    def __init__(self, project_root: Path):
        self.project_root = project_root
    
    def execute_action(self, action: Action, parameters: Dict[str, Any]) -> Dict[str, Any]:
        """
        Execute an action with the given parameters.
        
        Args:
            action: The action to execute
            parameters: Parameters provided by the MCP client
            
        Returns:
            Dictionary containing stdout, stderr, and status code
        """
        # Validate and prepare parameters
        env_vars = self._prepare_parameters(action, parameters)
        
        # Substitute parameters in command string
        command = action.command
        for param_name, param_value in env_vars.items():
            # Only substitute parameters that are not required_env_var or optional_env_var
            # These should already be available in the environment
            if param_name not in [p.name for p in action.parameters 
                                  if p.type in [ParameterType.REQUIRED_ENV_VAR, ParameterType.OPTIONAL_ENV_VAR]]:
                command = command.replace(f"${param_name}", str(param_value))
        
        # Determine execution directory
        execution_dir = self.project_root
        if action.run_path:
            execution_dir = self.project_root / action.run_path
            # Validate run_path is within project boundaries
            if not validate_project_path(action.run_path, self.project_root):
                raise ExecutionError(
                    f"ActionsMCP Error: Invalid run_path '{action.run_path}' for action '{action.name}'. "
                    f"Path must be within project boundaries and not contain directory traversal sequences."
                )
        
        # Execute command
        try:
            # Use subprocess.run with shell=False for security
            # Pass environment variables separately to avoid shell injection
            result = subprocess.run(
                shlex.split(command),
                cwd=execution_dir,
                env={**os.environ, **env_vars},
                capture_output=True,
                text=True,
                timeout=300  # 5 minute timeout
            )
            
            return {
                "stdout": process_terminal_output(result.stdout),
                "stderr": process_terminal_output(result.stderr),
                "status_code": result.returncode
            }
        except subprocess.TimeoutExpired:
            raise ExecutionError(f"ActionsMCP Error: Command for action '{action.name}' timed out after 5 minutes")
        except Exception as e:
            raise ExecutionError(f"ActionsMCP Error: Failed to execute command for action '{action.name}': {str(e)}")
    
    def _prepare_parameters(self, action: Action, provided_parameters: Dict[str, Any]) -> Dict[str, str]:
        """
        Validate and prepare environment variables for command execution.
        
        Args:
            action: The action being executed
            provided_parameters: Parameters provided by the MCP client
            
        Returns:
            Dictionary of environment variables to inject
        """
        env_vars = {}
        
        # Process each parameter defined in the action
        for param in action.parameters:
            # Handle required and optional environment variables
            if param.type in [ParameterType.REQUIRED_ENV_VAR, ParameterType.OPTIONAL_ENV_VAR]:
                # These parameters are not provided by the client but should be in the environment
                env_value = os.environ.get(param.name)
                if env_value is not None:
                    env_vars[param.name] = env_value
                elif param.type == ParameterType.REQUIRED_ENV_VAR:
                    raise ExecutionError(
                        f"ActionsMCP Error: Required environment variable '{param.name}' not set for action '{action.name}'"
                    )
                continue
            
            # Handle project file paths
            elif param.type == ParameterType.PROJECT_FILE_PATH:
                # Get the value from provided parameters or use default
                value = provided_parameters.get(param.name, param.default)
                
                # If no value and no default, it's required
                if value is None:
                    raise ExecutionError(
                        f"ActionsMCP Error: Required parameter '{param.name}' not provided for action '{action.name}'"
                    )
                
                # Validate the path
                if not validate_project_path(value, self.project_root):
                    raise ExecutionError(
                        f"ActionsMCP Error: Invalid path '{value}' for parameter '{param.name}' in action '{action.name}'. "
                        f"Path must be within project boundaries and not contain directory traversal sequences."
                    )
                
                # Check if file exists for project_file_path parameters
                full_path = self.project_root / value
                if not full_path.exists():
                    raise ExecutionError(
                        f"ActionsMCP Error: Path '{value}' for parameter '{param.name}' in action '{action.name}' does not exist"
                    )
                
                env_vars[param.name] = value
            
            # Handle insecure strings
            elif param.type == ParameterType.INSECURE_STRING:
                # Get the value from provided parameters or use default
                value = provided_parameters.get(param.name, param.default)
                
                # If no value and no default, it's required
                if value is None:
                    raise ExecutionError(
                        f"ActionsMCP Error: Required parameter '{param.name}' not provided for action '{action.name}'"
                    )
                
                # Convert to string if needed
                env_vars[param.name] = str(value)
        
        return env_vars
