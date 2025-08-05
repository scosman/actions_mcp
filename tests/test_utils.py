from hooks_mcp.utils import process_terminal_output, strip_ansi_codes


class TestStripANSICodes:
    """Test ANSI escape code stripping functionality."""

    def test_strip_basic_ansi_codes(self):
        """Test stripping basic ANSI color codes."""
        # Test basic color codes
        text = "\x1b[31mRed Text\x1b[0m"
        result = strip_ansi_codes(text)
        assert result == "Red Text"

        # Test multiple color codes
        text = "\x1b[32mGreen\x1b[0m and \x1b[34mBlue\x1b[0m"
        result = strip_ansi_codes(text)
        assert result == "Green and Blue"

    def test_strip_formatting_ansi_codes(self):
        """Test stripping ANSI formatting codes."""
        # Test bold
        text = "\x1b[1mBold Text\x1b[0m"
        result = strip_ansi_codes(text)
        assert result == "Bold Text"

        # Test underline
        text = "\x1b[4mUnderlined Text\x1b[0m"
        result = strip_ansi_codes(text)
        assert result == "Underlined Text"

        # Test combination of formatting
        text = "\x1b[1;4;31mBold Underlined Red\x1b[0m"
        result = strip_ansi_codes(text)
        assert result == "Bold Underlined Red"

    def test_strip_cursor_movement_codes(self):
        """Test stripping ANSI cursor movement codes."""
        # Test cursor up
        text = "Line 1\x1b[1AOverwritten"
        result = strip_ansi_codes(text)
        assert result == "Line 1Overwritten"

        # Test cursor down
        text = "Line 1\x1b[1BLine 2"
        result = strip_ansi_codes(text)
        assert result == "Line 1Line 2"

        # Test cursor forward/backward
        text = "Start\x1b[5CJump Forward\x1b[3CJump Back"
        result = strip_ansi_codes(text)
        assert result == "StartJump ForwardJump Back"

    def test_strip_erase_codes(self):
        """Test stripping ANSI erase codes."""
        # Test erase to end of line
        text = "Progress: 50%\x1b[K Complete"
        result = strip_ansi_codes(text)
        assert result == "Progress: 50% Complete"

        # Test erase to beginning of line
        text = "Progress: 50%\x1b[1K Complete"
        result = strip_ansi_codes(text)
        assert result == "Progress: 50% Complete"

        # Test erase entire line
        text = "Progress: 50%\x1b[2K Complete"
        result = strip_ansi_codes(text)
        assert result == "Progress: 50% Complete"

    def test_strip_complex_sequences(self):
        """Test stripping complex ANSI sequences."""
        # Test nested sequences
        text = "\x1b[31mRed \x1b[1mBold Red\x1b[0m \x1b[32mGreen\x1b[0m"
        result = strip_ansi_codes(text)
        assert result == "Red Bold Red Green"

        # Test sequences without reset
        text = "\x1b[31mRed Text"
        result = strip_ansi_codes(text)
        assert result == "Red Text"

    def test_strip_empty_and_no_codes(self):
        """Test stripping with empty text and text without ANSI codes."""
        # Test empty string
        result = strip_ansi_codes("")
        assert result == ""

        # Test text without ANSI codes
        text = "Plain text without any codes"
        result = strip_ansi_codes(text)
        assert result == text

        # Test None handling (though function expects string)
        # This would raise an error, which is expected behavior


class TestProcessTerminalOutput:
    """Test terminal output processing functionality."""

    def test_process_carriage_returns_basic(self):
        """Test basic carriage return processing."""
        # Simple carriage return replacement
        text = "Starting\rComplete"
        result = process_terminal_output(text)
        assert result == "Complete"

        # Multiple carriage returns
        text = "Starting\rProgress\rComplete"
        result = process_terminal_output(text)
        assert result == "Complete"

    def test_process_carriage_returns_with_ansi(self):
        """Test carriage return processing with ANSI codes."""
        # The example from the task
        text = "Starting\n1%\r\033[K\r\033[K25%\r\033[K100%\r\033[KComplete"
        result = process_terminal_output(text)
        assert result == "Starting\nComplete"

        # Carriage returns with color codes
        text = "\x1b[31mRed\r\x1b[32mGreen"
        result = process_terminal_output(text)
        assert result == "Green"

    def test_process_newlines_with_carriage_returns(self):
        """Test processing newlines that contain carriage returns."""
        # Multiple lines with carriage returns
        text = "Line 1\rUpdated Line 1\nLine 2\rUpdated Line 2"
        result = process_terminal_output(text)
        assert result == "Updated Line 1\nUpdated Line 2"

        # Progress indicator example with newlines
        text = "Building...\n1%\r\033[K\r\033[K25%\r\033[K\r\033[K50%\r\033[K\r\033[K100%\r\033[KComplete\nDone"
        result = process_terminal_output(text)
        assert result == "Building...\nComplete\nDone"

    def test_process_multiple_consecutive_carriage_returns(self):
        """Test processing multiple consecutive carriage returns."""
        text = "Start\r\r\rEnd"
        result = process_terminal_output(text)
        assert result == "End"

    def test_process_empty_lines(self):
        """Test processing empty lines and edge cases."""
        # Empty string
        result = process_terminal_output("")
        assert result == ""

        # Only carriage returns
        text = "\r\r\r"
        result = process_terminal_output(text)
        assert result == ""

        # Carriage returns with ANSI clear codes but no content
        text = "\x1b[K\r\x1b[K\r"
        result = process_terminal_output(text)
        assert result == ""

    def test_process_mixed_control_characters(self):
        """Test processing various control characters."""
        # Mix of newlines and carriage returns
        text = "First line\nSecond attempt\rFinal line\n\nNew section\rUpdated"
        result = process_terminal_output(text)
        assert result == "First line\nFinal line\n\nUpdated"

        # Text with both ANSI codes and control characters
        text = "\x1b[31mError:\x1b[0m Starting\n\x1b[33m1%\x1b[0m\r\x1b[K\x1b[33m25%\x1b[0m\r\x1b[K\x1b[32mComplete\x1b[0m"
        result = process_terminal_output(text)
        assert result == "Error: Starting\nComplete"

    def test_process_real_world_examples(self):
        """Test processing real-world terminal output examples."""
        # Simulate a typical progress bar output
        text = "Downloading file...\n[\x1b[32m#\x1b[0m] 10%\r\033[K[\x1b[32m####\x1b[0m] 50%\r\033[K[\x1b[32m########\x1b[0m] 100%\r\033[KDownload complete!\n"
        result = process_terminal_output(text)
        assert result == "Downloading file...\nDownload complete!"

        # Git clone style progress
        text = "Cloning into 'repo'...\nremote: Counting objects: 1%\r\033[Kremote: Counting objects: 50%\r\033[Kremote: Counting objects: 100%\r\033[Kremote: Compressing objects: 1%\r\033[Kremote: Compressing objects: 100%\r\033[K"
        result = process_terminal_output(text)
        assert result == "Cloning into 'repo'..."
