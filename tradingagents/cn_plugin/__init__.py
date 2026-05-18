"""CN Plugin — activates China market support on import.

Usage:
    import tradingagents.cn_plugin
"""
from tradingagents.dataflows.config import set_config
from tradingagents.cn_plugin.config import CN_CONFIG

# Merge CN config (does not overwrite user-set values)
_merged = {k: v for k, v in CN_CONFIG.items() if v}
set_config(_merged)
