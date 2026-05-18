def test_cn_config_merges():
    """Importing cn_plugin should merge config without errors."""
    from tradingagents.dataflows.config import get_config
    import tradingagents.cn_plugin
    config = get_config()
    assert config.get("output_language") == "Chinese"
    assert "china_data_priority" in config
