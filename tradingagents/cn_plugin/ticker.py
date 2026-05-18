"""Ticker normalization and China market detection."""
import re

_CHINA_SUFFIXES = {".SH", ".SZ", ".BJ"}

_PREFIX_MAP = {
    "SH": ".SH",
    "SZ": ".SZ",
    "BJ": ".BJ",
}

_CODE_RULES = [
    (re.compile(r"^6\d{5}$"), ".SH"),
    (re.compile(r"^00[0-3]\d{3}$"), ".SZ"),
    (re.compile(r"^30[01]\d{3}$"), ".SZ"),
    (re.compile(r"^688\d{3}$"), ".SH"),
    (re.compile(r"^[48]\d{5}$"), ".BJ"),
]


def normalize_ticker(symbol: str) -> str:
    """Normalize any China ticker input format to CODE.EXCHANGE.

    Supports: 600519, 600519.SH, SH600519, sh600519.
    Non-China tickers are returned unchanged.
    """
    s = symbol.strip()
    upper = s.upper()

    # Already has China suffix
    for suffix in _CHINA_SUFFIXES:
        if upper.endswith(suffix):
            code = upper[: -len(suffix)]
            if code.endswith("."):
                code = code[:-1]
            return f"{code}{suffix}"

    # Has exchange prefix (SH600519, sz000858, BJ830799)
    for prefix, suffix in _PREFIX_MAP.items():
        if upper.startswith(prefix) and upper[len(prefix):].isdigit():
            code = upper[len(prefix):]
            return f"{code}{suffix}"

    # Pure 6-digit number — infer exchange
    if s.isdigit() and len(s) == 6:
        for pattern, suffix in _CODE_RULES:
            if pattern.match(s):
                return f"{s}{suffix}"

    # Not a China ticker — return as-is
    return symbol


def is_china_ticker(symbol: str) -> bool:
    """Check if a normalized ticker belongs to a Chinese exchange."""
    upper = symbol.upper()
    return any(upper.endswith(suffix) for suffix in _CHINA_SUFFIXES)
