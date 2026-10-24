from akashic.anchor import find_quote, normalise, unsupported_numbers

RAW = (
    "Intro text.\n\nWe find that hybrid retrieval (BM25 + dense) improves recall@10 "
    "from 61.2% to 74.0% on the “in-domain” split, while extrac-\ntion latency stays flat."
)


def test_exact_quote_found_with_offset():
    q = "hybrid retrieval (BM25 + dense) improves recall@10"
    off = find_quote(q, RAW)
    assert off is not None and RAW[off:off + 6] == "hybrid"


def test_smart_quotes_case_and_whitespace_are_normalised():
    assert find_quote('ON THE "in-domain"   split, while', RAW) is not None


def test_line_break_hyphenation_is_joined():
    assert find_quote("while extraction latency stays flat", RAW) is not None


def test_paraphrase_is_not_an_anchor():
    assert find_quote("hybrid search raises recall substantially", RAW) is None


def test_short_quotes_are_refused():
    assert find_quote("We find", RAW) is None


def test_ligatures_fold():
    assert normalise("eﬃcient") == "efficient"


def test_numbers_must_appear_in_quotes():
    quote = "improves recall@10 from 61.2% to 74.0% on the"
    assert unsupported_numbers("Recall rises from 61.2% to 74%", [quote]) == set()
    assert unsupported_numbers("Recall rises from 61.2% to 80%", [quote]) == {"80%"}
    assert unsupported_numbers("1,000 documents", ["a corpus of 1000 documents"]) == set()
