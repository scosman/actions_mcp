#!/usr/bin/env python3
"""
Test script to demonstrate potential security issues with parameter substitution approach.
"""

import tempfile
from pathlib import Path

from hooks_mcp.config import Action, ActionParameter, ParameterType
from hooks_mcp.executor import CommandExecutor


def test_parameter_name_collision():
    """Test what happens when parameter names collide (one is substring of another)."""

    # Create a temporary directory for testing
    temp_dir = tempfile.TemporaryDirectory()
    project_root = Path(temp_dir.name)

    executor = CommandExecutor()
    executor.project_root = project_root

    # Create action with parameters where one name is substring of another
    action = Action(
        name="collision_test",
        description="Test parameter name collision",
        command="echo $A and $AB",  # $A is substring of $AB
        parameters=[
            ActionParameter("A", ParameterType.INSECURE_STRING, "Parameter 1"),
            ActionParameter("AB", ParameterType.INSECURE_STRING, "Parameter 2"),
        ],
    )

    try:
        result = executor.execute_action(
            action, {"A": "First Value", "AB": "Second Value"}
        )

        # Check if substitution worked correctly
        assert "First Value and Second Value" == result["stdout"]
    finally:
        temp_dir.cleanup()


def test_parameter_order_dependency():
    """Test if parameter substitution order matters."""

    temp_dir = tempfile.TemporaryDirectory()
    project_root = Path(temp_dir.name)

    executor = CommandExecutor()
    executor.project_root = project_root

    # Test with parameters in different orders
    action = Action(
        name="order_test",
        description="Test parameter order",
        command="echo $PREFIX $PREFIX_SUFFIX",
        parameters=[
            ActionParameter(
                "PREFIX_SUFFIX", ParameterType.INSECURE_STRING, "Full parameter"
            ),
            ActionParameter(
                "PREFIX", ParameterType.INSECURE_STRING, "Prefix parameter"
            ),
        ],
    )

    try:
        result = executor.execute_action(
            action, {"PREFIX": "Hello", "PREFIX_SUFFIX": "Hello World"}
        )

        # Parameter order should be handled correctly
        assert "Hello Hello World" == result["stdout"], (
            f"Expected 'Hello Hello World' in output, got: {result['stdout']}"
        )

    finally:
        temp_dir.cleanup()


def test_special_characters_in_values():
    """Test how special shell characters are handled."""

    temp_dir = tempfile.TemporaryDirectory()
    project_root = Path(temp_dir.name)

    executor = CommandExecutor()
    executor.project_root = project_root

    action = Action(
        name="special_chars_test",
        description="Test special characters",
        command="echo $MESSAGE",
        parameters=[
            ActionParameter(
                "MESSAGE", ParameterType.INSECURE_STRING, "Message with special chars"
            ),
        ],
    )

    test_cases = [
        ("Simple", "Hello World"),
        ("Quotes", 'Hello "quoted" world'),
        ("Single quotes", "Hello 'quoted' world"),
        ("Backticks", "Hello `backticked` world"),
        ("Dollar signs", "Hello $USER world"),
        ("Semicolon", "Hello; echo injected"),
        ("Ampersand", "Hello && echo injected"),
        ("Pipe", "Hello | echo injected"),
    ]

    try:
        for test_name, message in test_cases:
            result = executor.execute_action(action, {"MESSAGE": message})

            assert message == result["stdout"], (
                f"Expected '{message}' in output, got: {result['stdout']} for test {test_name}"
            )

    finally:
        temp_dir.cleanup()


def test_parameter_name_collision_substring():
    """Test what happens when parameter names collide (one is substring of another)."""

    # Create a temporary directory for testing
    temp_dir = tempfile.TemporaryDirectory()
    project_root = Path(temp_dir.name)

    executor = CommandExecutor()
    executor.project_root = project_root

    # Create action with parameters where one name is substring of another
    action = Action(
        name="collision_test",
        description="Test parameter name collision",
        command='echo "$A and $AB"',  # $A is substring of $AB
        parameters=[
            ActionParameter("A", ParameterType.INSECURE_STRING, "Parameter 1"),
            ActionParameter("AB", ParameterType.INSECURE_STRING, "Parameter 2"),
        ],
    )

    try:
        result = executor.execute_action(
            action, {"A": "First Value", "AB": "Second Value"}
        )

        # Check if substitution worked correctly
        # a bad example would be "'First Value' and 'Second Value'" with additional quoting changing the output
        assert "First Value and Second Value" == result["stdout"]
    finally:
        temp_dir.cleanup()
