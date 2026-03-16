"""Modal input parsing and _parse_bullets tests."""

from src.controller.modal_templates.feat_modal_input import FeatModalInput
from src.controller.modal_templates.refactor_modal_input import RefactorModalInput
from src.controller.modal_templates.fix_modal_input import FixModalInput
from src.controller.modal_templates.modal_templates import _parse_bullets


class TestFeatModalInput:

    def _make_values(self, **overrides) -> dict:
        defaults = {
            "feature_name": {"input": {"value": "Bookmark"}},
            "background": {"input": {"value": "Users need quick access"}},
            "features": {"input": {"value": "- bookmark items\n- view list"}},
            "constraints": {"input": {"value": "- auth required"}},
            "design_requirements": {"input": {"value": ""}},
        }
        defaults.update(overrides)
        return defaults

    def test_from_view_parsing(self) -> None:
        values = self._make_values()
        result = FeatModalInput.from_view(values)
        assert result.feature_name == "Bookmark"
        assert result.background == "Users need quick access"
        assert "bookmark items" in result.features

    def test_to_prompt_header_format(self) -> None:
        values = self._make_values()
        result = FeatModalInput.from_view(values)
        prompt = result.to_prompt()
        assert prompt.startswith("[feat] Bookmark")

    def test_to_prompt_contains_sections(self) -> None:
        values = self._make_values()
        result = FeatModalInput.from_view(values)
        prompt = result.to_prompt()
        assert "배경:" in prompt
        assert "기능:" in prompt
        assert "제약:" in prompt

    def test_to_prompt_optional_design_requirements_absent(self) -> None:
        values = self._make_values()
        result = FeatModalInput.from_view(values)
        prompt = result.to_prompt()
        assert "설계 요구사항:" not in prompt

    def test_to_prompt_optional_design_requirements_present(self) -> None:
        values = self._make_values(
            design_requirements={"input": {"value": "- REST API /bookmarks"}}
        )
        result = FeatModalInput.from_view(values)
        prompt = result.to_prompt()
        assert "설계 요구사항:" in prompt
        assert "REST API /bookmarks" in prompt

    def test_callback_id(self) -> None:
        assert FeatModalInput.CALLBACK_ID == "feat_submit"


class TestRefactorModalInput:

    def test_header_format(self) -> None:
        values = {
            "target_name": {"input": {"value": "SessionManager"}},
            "background": {"input": {"value": "Too many responsibilities"}},
            "as_is": {"input": {"value": "- direct coupling"}},
            "to_be": {"input": {"value": "- interface injection"}},
            "constraints": {"input": {"value": ""}},
        }
        result = RefactorModalInput.from_view(values)
        prompt = result.to_prompt()
        assert prompt.startswith("[refactor] SessionManager")

    def test_contains_as_is_to_be(self) -> None:
        values = {
            "target_name": {"input": {"value": "SessionManager"}},
            "background": {"input": {"value": "Needs cleanup"}},
            "as_is": {"input": {"value": "coupled"}},
            "to_be": {"input": {"value": "decoupled"}},
            "constraints": {"input": {"value": ""}},
        }
        result = RefactorModalInput.from_view(values)
        prompt = result.to_prompt()
        assert "AS-IS:" in prompt
        assert "TO-BE:" in prompt

    def test_callback_id(self) -> None:
        assert RefactorModalInput.CALLBACK_ID == "refactor_submit"


class TestFixModalInput:

    def test_header_format(self) -> None:
        values = {
            "bug_title": {"input": {"value": "NPE on login"}},
            "symptom": {"input": {"value": "Crash on startup"}},
            "reproduction": {"input": {"value": "- login with empty profile"}},
            "expected": {"input": {"value": "Graceful handling"}},
            "related_areas": {"input": {"value": ""}},
        }
        result = FixModalInput.from_view(values)
        prompt = result.to_prompt()
        assert prompt.startswith("[fix] NPE on login")

    def test_callback_id(self) -> None:
        assert FixModalInput.CALLBACK_ID == "fix_submit"


class TestParseBullets:

    def test_dash_prefix(self) -> None:
        result = _parse_bullets("- item one\n- item two")
        assert result == ["item one", "item two"]

    def test_bullet_prefix(self) -> None:
        result = _parse_bullets("• first\n• second")
        assert result == ["first", "second"]

    def test_empty_lines_ignored(self) -> None:
        result = _parse_bullets("- item\n\n- other")
        assert result == ["item", "other"]

    def test_plain_text(self) -> None:
        result = _parse_bullets("just text\nanother line")
        assert result == ["just text", "another line"]

    def test_empty_string(self) -> None:
        result = _parse_bullets("")
        assert result == []

    def test_whitespace_only_lines(self) -> None:
        result = _parse_bullets("  \n  - hello  \n  ")
        assert result == ["hello"]
