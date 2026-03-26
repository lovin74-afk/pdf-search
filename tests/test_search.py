from pdf_searcher.search import search_index


def test_search_index_returns_position_metadata() -> None:
    index_data = {
        "documents": [
            {
                "file_name": "sample.pdf",
                "file_path": "sample.pdf",
                "pages": [
                    {
                        "page_number": 1,
                        "page_label": "1페이지",
                        "text": "alpha beta gamma",
                        "fragments": [
                            {
                                "text": "alpha beta gamma",
                                "start_char": 0,
                                "end_char": 16,
                                "line_number": 2,
                                "x": 10.0,
                                "y": 700.0,
                            }
                        ],
                    }
                ],
            }
        ]
    }

    results = search_index(index_data, "beta")

    assert len(results) == 1
    assert results[0]["file_name"] == "sample.pdf"
    assert results[0]["line_number"] == 2
    assert results[0]["start_char"] == 6


def test_search_index_returns_all_results_when_limit_is_none() -> None:
    index_data = {
        "documents": [
            {
                "file_name": "sample.pdf",
                "file_path": "sample.pdf",
                "pages": [
                    {
                        "page_number": 1,
                        "page_label": "1페이지",
                        "text": "beta alpha beta",
                        "fragments": [
                            {
                                "text": "beta alpha beta",
                                "start_char": 0,
                                "end_char": 15,
                                "line_number": 1,
                                "x": 0.0,
                                "y": 0.0,
                            }
                        ],
                    }
                ],
            }
        ]
    }

    results = search_index(index_data, "beta", limit=None)

    assert len(results) == 2


def test_search_index_returns_sentence_excerpt() -> None:
    index_data = {
        "documents": [
            {
                "file_name": "sample.pdf",
                "file_path": "sample.pdf",
                "pages": [
                    {
                        "page_number": 1,
                        "page_label": "1페이지",
                        "text": "첫 문장입니다. 여기서 beta 단어가 포함된 문장이 나옵니다. 마지막 문장입니다.",
                        "fragments": [
                            {
                                "text": "첫 문장입니다. 여기서 beta 단어가 포함된 문장이 나옵니다. 마지막 문장입니다.",
                                "start_char": 0,
                                "end_char": 47,
                                "line_number": 1,
                                "x": 0.0,
                                "y": 0.0,
                            }
                        ],
                    }
                ],
            }
        ]
    }

    results = search_index(index_data, "beta", limit=None)

    assert results[0]["snippet"] == "여기서 beta 단어가 포함된 문장이 나옵니다."


def test_search_index_returns_context_with_two_sentences_before_and_after() -> None:
    index_data = {
        "documents": [
            {
                "file_name": "sample.pdf",
                "file_path": "sample.pdf",
                "pages": [
                    {
                        "page_number": 1,
                        "page_label": "1페이지",
                        "text": (
                            "첫 번째 문장입니다. 두 번째 문장입니다. 세 번째 beta 문장입니다. "
                            "네 번째 문장입니다. 다섯 번째 문장입니다. 여섯 번째 문장입니다."
                        ),
                        "fragments": [
                            {
                                "text": (
                                    "첫 번째 문장입니다. 두 번째 문장입니다. 세 번째 beta 문장입니다. "
                                    "네 번째 문장입니다. 다섯 번째 문장입니다. 여섯 번째 문장입니다."
                                ),
                                "start_char": 0,
                                "end_char": 74,
                                "line_number": 1,
                                "x": 0.0,
                                "y": 0.0,
                            }
                        ],
                    }
                ],
            }
        ]
    }

    results = search_index(index_data, "beta", limit=None)

    assert results[0]["context_snippet"] == (
        "첫 번째 문장입니다. 두 번째 문장입니다. 세 번째 beta 문장입니다. "
        "네 번째 문장입니다. 다섯 번째 문장입니다."
    )
