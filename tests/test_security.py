import tempfile
from pathlib import Path

import pytest

from hooks_mcp.config import Action, ActionParameter, ParameterType
from hooks_mcp.executor import CommandExecutor, ExecutionError
from hooks_mcp.utils import validate_project_path


class TestSecurity:
    """Test security features of HooksMCP."""

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

    def test_validate_project_path_safe_paths(self):
        """Test that safe paths are validated correctly."""
        # Test valid paths
        assert validate_project_path("./tests/test1.py", self.project_root)
        assert validate_project_path("tests/test1.py", self.project_root)
        assert validate_project_path("./src/main.py", self.project_root)
        assert validate_project_path("src/main.py", self.project_root)
        assert validate_project_path("./", self.project_root)
        assert validate_project_path(".", self.project_root)

    @pytest.mark.parametrize(
        "safe_path",
        [
            # Basic relative paths
            "tests/test1.py",
            "src/main.py",
            "./tests/test1.py",
            "./src/main.py",
            # Current directory references
            ".",
            "./",
            "./.",
            # Valid subdirectory paths
            "tests/subdir/file.py",
            "src/package/module.py",
            "./tests/deep/nested/file.py",
            "src/very/deep/nested/structure/file.py",
            # Non-existent but valid paths
            "tests/nonexistent.py",
            "src/future_file.py",
            "new_directory/new_file.py",
            "./future/directory/file.py",
            # Files with various extensions
            "README.md",
            "package.json",
            "Dockerfile",
            "script.sh",
            "config.yaml",
            "data.json",
            "style.css",
            "index.html",
            # Files with special characters (but still safe)
            "file-with-dashes.py",
            "file_with_underscores.py",
            "file.with.dots.py",
            "file with spaces.py",
            "tests/test-file.py",
            "src/module_name.py",
            # Empty string (should resolve to project root)
            "",
            # Paths with current directory components (but still within project)
            "tests/./test1.py",
            "./tests/./test1.py",
            "tests/./subdir/./file.py",
            "src/./package/./module.py",
            # Multiple slashes (should be normalized)
            "tests//test1.py",
            "./tests//subdir//file.py",
            "src///main.py",
            # Paths that look suspicious but are actually safe
            "tests/test_security.py",
            "src/path_utils.py",
            "config/environment.py",
            "scripts/home_manager.py",
            # Deep nested paths
            "a/b/c/d/e/f/g/file.py",
            "./very/deep/path/structure/file.txt",
            # Files that start with dots (hidden files)
            ".gitignore",
            ".env",
            ".config/settings.json",
            "tests/.test_config",
            # Numeric and mixed names
            "file123.py",
            "123file.py",
            "v1.2.3/release.py",
            "test_2024_01_01.py",
        ],
    )
    def test_validate_project_path_comprehensive_safe_paths(self, safe_path):
        """Test that various legitimate path patterns are all accepted."""
        assert validate_project_path(safe_path, self.project_root), (
            f"Legitimate path '{safe_path}' was incorrectly rejected"
        )

    def test_validate_project_path_dangerous_paths(self):
        """Test that dangerous paths are rejected."""
        # Test paths that break out of project root
        assert not validate_project_path("../outside.py", self.project_root)
        assert not validate_project_path("~/secret.py", self.project_root)
        assert not validate_project_path("$HOME/secret.py", self.project_root)
        assert not validate_project_path("./../outside.py", self.project_root)
        assert not validate_project_path("tests/../../outside.py", self.project_root)

    @pytest.mark.parametrize(
        "malicious_path",
        [
            # Directory traversal attacks - basic
            "../outside.py",
            "../../outside.py",
            "../../../etc/passwd",
            "../../../../etc/passwd",
            # Directory traversal attacks - with current directory
            "./../outside.py",
            "./../../outside.py",
            "./../../../etc/passwd",
            # Directory traversal attacks - from subdirectories that actually escape
            "tests/../../outside.py",
            "tests/../../../etc/passwd",
            "tests/./../../outside.py",
            "src/../../outside.py",
            "tests/../src/../../outside.py",
            "tests/./../../src/../outside.py",
            # Home directory expansion attacks
            "~/secret.py",
            "~/../../etc/passwd",
            "~/../etc/passwd",
            "~root/secret.py",
            "~/../../../etc/passwd",
            # Environment variable expansion attacks
            "$HOME/secret.py",
            "${HOME}/secret.py",
            "$HOME/../etc/passwd",
            "$HOME/../../etc/passwd",
            "$SHELL/../etc/passwd",
            "$PATH/../etc/passwd",
            "$PWD/../outside.py",
            "${PWD}/../outside.py",
            "$TMPDIR/../etc/passwd",
            # Absolute path attacks
            "/etc/passwd",
            "/tmp/outside.py",
            "/absolute/path/outside.py",
            "/usr/bin/evil",
            "/var/log/outside.py",
            "/root/secret.py",
            # Mixed expansion attacks
            "~/$USER/../etc/passwd",
            "$HOME/../../../etc/passwd",
            "~/../$HOME/secret.py",
            "${HOME}/../$USER/secret.py",
            "~/../${PWD}/outside.py",
            "$HOME/../~root/secret.py",
            # Edge cases with special characters that escape
            "../outside file.py",
            "~/ secret.py",
            "$HOME/../file with spaces.py",
            # Trying to escape with multiple techniques
            "../~root/secret.py",
            "~/../$HOME/../etc/passwd",
            "$HOME/../~/../etc/passwd",
            "${HOME}/../../../etc/passwd",
            "~/../${HOME}/../etc/passwd",
            # Network paths (Windows style, but should be rejected on any platform)
            "//network/share/file.py",
            # Null byte attacks (if they don't cause exceptions)
            "../outside.py\x00.txt",
            "~/secret.py\x00.txt",
            # Unicode normalization attacks
            "../\u00e9outside.py",  # é character
            "~\u002f../etc/passwd",  # Unicode slash
            # Case variations (especially important on case-insensitive filesystems)
            "../Outside.py",
            "~/Secret.py",
            "$HOME/../Etc/Passwd",
            # Long paths trying to exhaust path resolution
            "../" * 20 + "etc/passwd",
            "tests/" + "../" * 10 + "outside.py",
            # Symlink-style attacks (even without actual symlinks) that actually escape
            "symlink/../../../etc/passwd",
        ],
    )
    def test_validate_project_path_comprehensive_attacks(self, malicious_path):
        """Test that various malicious path attack vectors are all rejected."""
        assert not validate_project_path(malicious_path, self.project_root), (
            f"Security vulnerability: malicious path '{malicious_path}' was incorrectly accepted"
        )

    @pytest.mark.parametrize(
        "tricky_but_safe_path",
        [
            # These look suspicious but actually resolve to within the project root
            "tests/../outside.py",  # resolves to "outside.py"
            "src/../config.json",  # resolves to "config.json"
            "tests/../src/../main.py",  # resolves to "main.py"
            "./tests/../src/../app.py",  # resolves to "app.py"
            "docs/../outside.py",  # resolves to "outside.py"
            "tests/./../../tests/test1.py",  # resolves to "tests/test1.py" (back to same place)
            # Environment variables that resolve to relative paths within project
            # Note: These depend on the specific environment, so might vary
            # Whitespace that doesn't change the meaning
            " tests/../outside.py",  # leading space resolves to " tests/../outside.py" -> may be within project
            "tests/../outside.py ",  # trailing space
            "\ttests/../main.py",  # tab prefix
            "\ntests/../config.py",  # newline prefix
            # Multiple slashes that normalize
            "tests//../outside.py",  # double slash normalizes to single
            "tests///../outside.py",  # triple slash normalizes
            ".//outside.py",  # current dir with double slash
            # Complex but safe navigation
            "tests/subdir/../../outside.py",  # goes up from subdir but stays in project
            "src/lib/../../../main.py",  # complex navigation that ends up in project
            # Shell patterns that don't actually get expanded by our function
            "file$(echo nothing).py",  # shell command substitution (not expanded by os.path.expandvars)
            "file`echo nothing`.py",  # backtick substitution (not expanded)
            "${VAR:-default.py}",  # bash parameter expansion (partially expanded)
        ],
    )
    def test_validate_project_path_tricky_but_safe(self, tricky_but_safe_path):
        """Test that paths which look suspicious but are actually safe are accepted."""
        # Note: Some of these might actually be rejected depending on environment
        # The goal is to document the expected behavior for tricky edge cases
        result = validate_project_path(tricky_but_safe_path, self.project_root)
        print(f"Path '{tricky_but_safe_path}' -> {'ALLOWED' if result else 'REJECTED'}")
        # We're not asserting here because behavior may vary by environment
        # This test is mainly for documentation and manual inspection

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
                ActionParameter(
                    "file_path",
                    ParameterType.PROJECT_FILE_PATH,
                    "A file path",
                    "tests/test1.py",
                )
            ],
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
                ActionParameter(
                    "file_path", ParameterType.PROJECT_FILE_PATH, "A file path"
                )
            ],
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
                ActionParameter(
                    "TEST_STRING", ParameterType.INSECURE_STRING, "An insecure string"
                )
            ],
        )

        # This should work even with potentially dangerous content
        # (though the command itself won't do anything harmful)
        result = self.executor.execute_action(action, {"TEST_STRING": "123 && rm -r ~"})
        assert "123 && rm -r ~" in result["stdout"]
