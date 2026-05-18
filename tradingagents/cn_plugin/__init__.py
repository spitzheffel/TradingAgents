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
