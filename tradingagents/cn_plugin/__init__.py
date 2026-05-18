"""CN Plugin — activates China market support on import.

Usage:
    import tradingagents.cn_plugin
"""
from tradingagents.dataflows.config import set_config
from tradingagents.dataflows.interface import VENDOR_LIST, VENDOR_METHODS
from tradingagents.cn_plugin.config import CN_CONFIG
from tradingagents.cn_plugin.routing import patch_routing
from tradingagents.cn_plugin.dataflows.provider import route_china

# 1. Merge CN config
_merged = {k: v for k, v in CN_CONFIG.items() if v}
set_config(_merged)

# 2. Register china vendor
if "china" not in VENDOR_LIST:
    VENDOR_LIST.append("china")

def _make_china_impl(method_name):
    def _impl(*args, **kwargs):
        return route_china(method_name, *args, **kwargs)
    return _impl

for _method_name in list(VENDOR_METHODS.keys()):
    if "china" not in VENDOR_METHODS[_method_name]:
        VENDOR_METHODS[_method_name]["china"] = _make_china_impl(_method_name)

# 3. Patch routing for ticker normalization + china interception
patch_routing()

# 4. Patch get_language_instruction for Chinese enhancement
from tradingagents.cn_plugin.prompts.zh_cn import ZH_INSTRUCTION
import tradingagents.agents.utils.agent_utils as _agent_utils

_original_get_language_instruction = _agent_utils.get_language_instruction

def _zh_language_instruction() -> str:
    from tradingagents.dataflows.config import get_config
    lang = get_config().get("output_language", "English")
    if lang.strip().lower() in ("chinese", "中文"):
        return ZH_INSTRUCTION
    return _original_get_language_instruction()

_agent_utils.get_language_instruction = _zh_language_instruction
