"""Context size primitives (Phase 6.6).

Only the token estimate lives here so far. Measuring a context and
applying a ContextBudget are later Phase 6.6 steps and must not be added
before them.

The estimate is deliberately model independent and dependency free: a
conservative character based approximation that over-estimates slightly,
so any budget computed from it errs on the safe side. It can be replaced
by a real tokenizer later without changing the schemas or the callers.
"""

import math
import re

_CJK_PATTERN = re.compile(
    "["
    "\u2e80-\u2fff"  # CJK radicals
    "\u3000-\u303f"  # CJK punctuation
    "\u3040-\u30ff"  # kana
    "\u31f0-\u31ff"  # kana extensions
    "\u3400-\u4dbf"  # CJK unified ideographs extension A
    "\u4e00-\u9fff"  # CJK unified ideographs
    "\uf900-\ufaff"  # compatibility ideographs
    "\ufe30-\ufe4f"  # CJK compatibility forms
    "\uff00-\uffef"  # fullwidth forms
    "]"
)

_OTHER_CHARS_PER_TOKEN = 3
_CJK_CHARS_PER_TOKEN = 1


def estimate_tokens(text: str) -> int:
    """Conservative token estimate for mixed Java and Python source text.

    Non CJK characters count three per token, deliberately below the four
    characters per token typical for code, and every CJK character counts
    as one token. The result is therefore a slight over-estimate on
    purpose. Empty text yields 0.
    """
    if not text:
        return 0

    cjk_chars = len(_CJK_PATTERN.findall(text))
    other_chars = len(text) - cjk_chars
    return (
        math.ceil(other_chars / _OTHER_CHARS_PER_TOKEN)
        + cjk_chars * _CJK_CHARS_PER_TOKEN
    )