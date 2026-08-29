"""Tests for the post-stream prose artifact normalizer."""

from app.services.chat.prose_normalizer import normalize_prose_artifacts, prose_changed


class TestNormalizeProseArtifacts:
    def test_orphan_colon_line_removed(self):
        text = "Step 1: Simplify\n:\n$2x + 3 = 7$"
        result = normalize_prose_artifacts(text)
        assert ":" not in result.split("\n")
        assert "Step 1: Simplify" in result
        assert "$2x + 3 = 7$" in result

    def test_colon_with_whitespace_removed(self):
        text = "Step 1\n  :  \nFormula here"
        result = normalize_prose_artifacts(text)
        assert result == "Step 1\n\nFormula here"

    def test_inline_colon_preserved(self):
        text = "For x = 3: the result is 6"
        result = normalize_prose_artifacts(text)
        assert result == "For x = 3: the result is 6"

    def test_colon_in_code_fence_preserved(self):
        text = "```python\nx: int = 0\n```"
        result = normalize_prose_artifacts(text)
        # The colon inside the code fence should not be removed because
        # it's not on its own line — it's part of a code line.
        assert "x: int = 0" in result

    def test_lone_colon_line_inside_yaml_fence_preserved(self):
        text = "```yaml\nkey: value\n:\nnested: 1\n```"
        result = normalize_prose_artifacts(text)
        assert ":\n" in result or "\n:" in result
        assert "nested: 1" in result

    def test_blank_lines_inside_python_fence_preserved(self):
        text = "```python\ndef a():\n    return 1\n\n\n\ndef b():\n    return 2\n```"
        result = normalize_prose_artifacts(text)
        assert "def a():" in result
        assert "def b():" in result
        inner = result.split("```python")[1].split("```")[0]
        assert inner.count("\n\n\n") >= 1

    def test_multiple_orphan_colons_removed(self):
        text = "Step 1\n:\nStep 2\n:\nStep 3"
        result = normalize_prose_artifacts(text)
        assert result == "Step 1\n\nStep 2\n\nStep 3"

    def test_excess_blank_lines_collapsed(self):
        text = "Paragraph 1\n\n\n\n\nParagraph 2"
        result = normalize_prose_artifacts(text)
        assert result == "Paragraph 1\n\nParagraph 2"

    def test_double_newline_preserved(self):
        text = "Paragraph 1\n\nParagraph 2"
        result = normalize_prose_artifacts(text)
        assert result == "Paragraph 1\n\nParagraph 2"

    def test_no_change_returns_unchanged(self):
        text = "Hello world\n\nThis is fine."
        result = normalize_prose_artifacts(text)
        assert result == text

    def test_strips_trailing_whitespace(self):
        text = "Hello\n\n\n"
        result = normalize_prose_artifacts(text)
        assert result == "Hello"

    def test_strips_leading_whitespace(self):
        text = "\n\n\nHello"
        result = normalize_prose_artifacts(text)
        assert result == "Hello"

    def test_combined_orphan_colon_and_excess_blanks(self):
        text = "Step 1: Simplify\n:\n\n\n$2x = 4$\n\n\n\nStep 2"
        result = normalize_prose_artifacts(text)
        assert result == "Step 1: Simplify\n\n$2x = 4$\n\nStep 2"


class TestProseChanged:
    def test_changed_when_colon_removed(self):
        original = "Step 1\n:\nFormula"
        normalized = normalize_prose_artifacts(original)
        assert prose_changed(original, normalized) is True

    def test_unchanged_when_no_artifacts(self):
        original = "Hello world\n\nThis is fine."
        normalized = normalize_prose_artifacts(original)
        assert prose_changed(original, normalized) is False

    def test_unchanged_for_empty_string(self):
        original = ""
        normalized = normalize_prose_artifacts(original)
        assert prose_changed(original, normalized) is False
