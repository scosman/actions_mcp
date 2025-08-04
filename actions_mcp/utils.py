import re
from pathlib import Path


def strip_ansi_codes(text: str) -> str:
    """
    Strip ANSI escape codes from text to produce clean plaintext output.

    Args:
        text: Text that may contain ANSI escape codes

    Returns:
        Text with ANSI escape codes removed
    """
    # Regular expression to match ANSI escape codes
    ansi_escape = re.compile(r"\x1B(?:[@-Z\\-_]|\[[0-?]*[ -/]*[@-~])")
    return ansi_escape.sub("", text)


def process_terminal_output(text: str) -> str:
    """
    Process terminal output to simulate what would actually be visible after
    control characters like carriage returns are handled.

    Args:
        text: Raw terminal output

    Returns:
        Processed text that represents the final visible state
    """
    # Strip ANSI codes first
    clean_text = strip_ansi_codes(text)

    # Handle carriage returns - they overwrite the current line
    lines = clean_text.split("\n")
    processed_lines = []

    for line in lines:
        # Split by carriage return and keep only the last part (final state)
        parts = line.split("\r")
        if parts:
            # The last part is what would be visible after all carriage returns
            processed_lines.append(parts[-1])
        else:
            processed_lines.append("")

    return "\n".join(processed_lines).strip()


def validate_project_path(path: str, project_root: Path) -> bool:
    """
    Validate that a path is within the project boundaries and doesn't
    attempt to break out using directory traversal.

    Args:
        path: Path to validate
        project_root: Project root directory

    Returns:
        True if path is valid, False otherwise
    """
    # Resolve the project root to an absolute path
    project_root = project_root.resolve()

    # Create a Path object for the given path
    # We don't resolve it yet as that might normalize it in ways we don't want
    path_obj = Path(path)

    # Check if path starts with dangerous patterns
    if path.startswith("~") or path.startswith("$HOME"):
        return False

    # Check if path contains parent directory references
    if ".." in path:
        return False

    # Resolve the full path relative to project root
    full_path = (project_root / path_obj).resolve()

    # Check if the resolved path is within the project root
    try:
        full_path.relative_to(project_root)
        return True
    except ValueError:
        # Path is not within project root
        return False
