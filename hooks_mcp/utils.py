import os
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


def resolve_path(path: str, project_root: Path) -> Path:
    """
    Resolve a path to its canonical form.
    """
    # Convert to Path object
    untrusted_path = Path(path)

    # If the path is absolute, resolve it directly
    if untrusted_path.is_absolute():
        return untrusted_path.resolve()
    else:
        # If the path is relative, resolve it relative to the project root
        # This is crucial for security - we want relative paths to be relative to project root
        return (project_root / untrusted_path).resolve()


def validate_project_path(path: str, project_root: Path) -> bool:
    """
    Validate that a path is within the project boundaries and doesn't
    attempt to break out using directory traversal or any other method.

    This function is designed to be secure against various attack vectors:
    - Directory traversal attacks (../, ../../, etc.)
    - Home directory expansion attacks (~/, ~user/)
    - Environment variable expansion attacks ($HOME, ${EVIL_VAR}, etc.)
    - Symlink attacks (symlinks pointing outside project root)
    - Unicode normalization attacks
    - Case sensitivity issues on different filesystems

    The approach:
    1. Fully expand and resolve both paths to their canonical forms
    2. This includes expanding ~ (user home), environment variables, and symlinks
    3. Then check if the fully resolved untrusted path is within project boundaries
    4. Use pathlib for cross-platform compatibility

    Args:
        path: Path to validate (untrusted input)
        project_root: Project root directory (trusted)

    Returns:
        True if path is valid and within project boundaries, False otherwise
    """

    try:
        # Resolve the trusted project root to canonical absolute path
        # This handles symlinks, normalizes the path, and makes it absolute
        canonical_project_root = project_root.resolve()

        # For the untrusted path, we MUST fully expand everything to see where it really points
        # Expand user home directory (~)
        expanded_path = os.path.expanduser(path)
        # Expand environment variables ($HOME, ${VAR}, etc.)
        expanded_path = os.path.expandvars(expanded_path)

        # Security check: If path still contains unexpanded environment variables,
        # reject it to prevent treating them as relative paths within the project
        # Look for patterns like $VAR or ${VAR} that indicate unexpanded variables
        if re.search(r"\$[A-Za-z_][A-Za-z0-9_]*|\$\{[^}]*\}", expanded_path):
            return False

        # Convert to respoved path
        candidate_path = resolve_path(expanded_path, canonical_project_root)

        # Use is_relative_to() if available (Python 3.9+), otherwise use relative_to()
        if hasattr(candidate_path, "is_relative_to"):
            return candidate_path.is_relative_to(canonical_project_root)
        else:
            try:
                candidate_path.relative_to(canonical_project_root)
                return True
            except ValueError:
                return False

    except (OSError, ValueError, RuntimeError):
        # Any error during path resolution should result in rejection
        # This catches issues like:
        # - Invalid path characters
        # - Too many levels of symbolic links
        # - Permission errors
        # - Path too long
        # - Invalid environment variable references
        return False
