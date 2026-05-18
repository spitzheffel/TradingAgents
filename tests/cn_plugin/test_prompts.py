import pytest


class TestZhLanguageInstruction:
    def test_returns_chinese_instruction(self):
        import tradingagents.cn_plugin
        from tradingagents.agents.utils.agent_utils import get_language_instruction
        instruction = get_language_instruction()
        assert "简体中文" in instruction
        assert "市盈率" in instruction
        assert "市净率" in instruction

    def test_contains_format_requirements(self):
        import tradingagents.cn_plugin
        from tradingagents.agents.utils.agent_utils import get_language_instruction
        instruction = get_language_instruction()
        assert "人民币" in instruction
        assert "YYYY-MM-DD" in instruction

    def test_english_fallback(self):
        """When language is English, should return original behavior."""
        import tradingagents.cn_plugin
        from tradingagents.dataflows.config import set_config
        from tradingagents.agents.utils.agent_utils import get_language_instruction
        # Temporarily set English
        set_config({"output_language": "English"})
        instruction = get_language_instruction()
        assert "市盈率" not in instruction
        # Restore
        set_config({"output_language": "Chinese"})
