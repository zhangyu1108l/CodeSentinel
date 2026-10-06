"""Tests for the Phase 6.6.1 token estimator."""

from app.context.context_size_controller import estimate_tokens


class TestEstimateTokensEmpty:
    def test_empty_string(self):
        assert estimate_tokens("") == 0

    def test_none_is_tolerated(self):
        assert estimate_tokens(None) == 0


class TestEstimateTokensAscii:
    def test_single_character(self):
        assert estimate_tokens("a") == 1

    def test_exact_multiple_of_three(self):
        assert estimate_tokens("abc") == 1
        assert estimate_tokens("abcdef") == 2
        assert estimate_tokens("a" * 9) == 3

    def test_ceil_boundary(self):
        assert estimate_tokens("a" * 3) == 1
        assert estimate_tokens("a" * 4) == 2
        assert estimate_tokens("a" * 6) == 2
        assert estimate_tokens("a" * 7) == 3

    def test_whitespace_counts_as_other_characters(self):
        assert estimate_tokens("   ") == 1
        assert estimate_tokens("    ") == 2

    def test_long_ascii_text(self):
        assert estimate_tokens("a" * 30000) == 10000

    def test_code_snippet(self):
        text = "public class Demo {\n    void run() {}\n}\n"
        assert estimate_tokens(text) == (len(text) + 2) // 3


class TestEstimateTokensCjk:
    def test_single_cjk_character(self):
        assert estimate_tokens("中") == 1

    def test_multiple_cjk_characters(self):
        assert estimate_tokens("中文") == 2
        assert estimate_tokens("中文代码") == 4

    def test_cjk_punctuation(self):
        assert estimate_tokens("。") == 1
        assert estimate_tokens("，") == 1

    def test_fullwidth_forms(self):
        assert estimate_tokens("：") == 1
        assert estimate_tokens("（）") == 2

    def test_kana(self):
        assert estimate_tokens("あ") == 1

    def test_cjk_extension_a(self):
        assert estimate_tokens("\u3400") == 1

    def test_cjk_dominates_the_ratio(self):
        assert estimate_tokens("中" * 100) == 100


class TestEstimateTokensMixed:
    def test_ascii_then_cjk(self):
        assert estimate_tokens("abc中") == 2

    def test_cjk_then_ascii(self):
        assert estimate_tokens("中abc") == 2

    def test_interleaved(self):
        assert estimate_tokens("中a文b") == 3

    def test_short_ascii_with_cjk(self):
        assert estimate_tokens("ab中") == 2

    def test_mixed_code_and_comment(self):
        text = "int count = 0; // 计数器"
        cjk = 3
        other = len(text) - cjk
        assert estimate_tokens(text) == (other + 2) // 3 + cjk


class TestEstimateTokensProperties:
    def test_deterministic(self):
        text = "public void run() { /* 运行 */ }"
        assert estimate_tokens(text) == estimate_tokens(text)

    def test_monotonic_for_ascii_prefixes(self):
        base = "a" * 500
        previous = 0
        for length in range(0, len(base) + 1, 17):
            current = estimate_tokens(base[:length])
            assert current >= previous
            previous = current

    def test_monotonic_for_mixed_prefixes(self):
        base = "代码code" * 100
        previous = 0
        for length in range(0, len(base) + 1, 13):
            current = estimate_tokens(base[:length])
            assert current >= previous
            previous = current

    def test_input_is_not_mutated(self):
        text = "demo 演示"
        before = str(text)
        estimate_tokens(text)
        assert text == before

    def test_returns_int(self):
        assert isinstance(estimate_tokens("abc"), int)

    def test_never_negative(self):
        for text in ("", "a", "中", "a中b"):
            assert estimate_tokens(text) >= 0


class TestEstimateTokensNoDependencies:
    def test_module_imports_only_standard_library(self):
        import app.context.context_size_controller as module

        source = module.__dict__
        for forbidden in (
            "httpx",
            "requests",
            "openai",
            "tiktoken",
            "tokenizers",
            "transformers",
            "langchain",
            "langgraph",
        ):
            assert forbidden not in source
            assert not hasattr(module, forbidden)


class TestEstimateTokensContract:
    def test_matches_documented_formula(self):
        for text in (
            "",
            "abc",
            "中文",
            "abc中文",
            "public class A {}",
            "中文注释",
            "混合 mixed 内容",
        ):
            cjk = sum(
                1
                for char in text
                if "\u2e80" <= char <= "\u2fff"
                or "\u3000" <= char <= "\u303f"
                or "\u3040" <= char <= "\u30ff"
                or "\u31f0" <= char <= "\u31ff"
                or "\u3400" <= char <= "\u4dbf"
                or "\u4e00" <= char <= "\u9fff"
                or "\uf900" <= char <= "\ufaff"
                or "\ufe30" <= char <= "\ufe4f"
                or "\uff00" <= char <= "\uffef"
            )
            other = len(text) - cjk
            expected = -(-other // 3) + cjk
            assert estimate_tokens(text) == expected

    def test_ascii_is_never_underestimated_for_code(self):
        text = "public class Demo { private int count = 0; }"
        assert estimate_tokens(text) >= len(text) // 4


class TestEstimateTokensStability:
    def test_repeated_calls_are_stable(self):
        text = "中文" * 50 + "abc" * 50
        assert len({estimate_tokens(text) for _ in range(5)}) == 1