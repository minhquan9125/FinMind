from src.chunking import Page, build_chunks


def test_short_page_becomes_single_chunk():
    pages = [Page(page=1, text=" ".join(f"w{i}" for i in range(50)))]
    chunks = build_chunks(pages, chunk_words=130, chunk_stride=100)
    assert len(chunks) == 1
    assert chunks[0].page == 1


def test_long_page_is_split_with_overlap():
    words = [f"w{i}" for i in range(300)]
    pages = [Page(page=1, text=" ".join(words))]
    chunks = build_chunks(pages, chunk_words=130, chunk_stride=100)

    # windows start at 0, 100, 200 -> 3 chunks for 300 words
    assert len(chunks) == 3
    first_words = chunks[0].text.split(" ")
    second_words = chunks[1].text.split(" ")
    assert len(first_words) == 130
    # 30-word overlap: last 30 words of chunk 1 == first 30 words of chunk 2
    assert first_words[100:] == second_words[:30]


def test_empty_page_text_is_skipped():
    pages = [Page(page=1, text=""), Page(page=2, text="hello world")]
    chunks = build_chunks(pages, chunk_words=130, chunk_stride=100)
    assert len(chunks) == 1
    assert chunks[0].page == 2


def test_short_tail_window_is_dropped():
    # 235 words -> windows at start=0 (130 words) and start=100 (135 words,
    # since 235-100=135 >= 25) -> both kept, no 3rd window since
    # 100+130=230 < 235 but next start=200 would give a 35-word tail.
    words = [f"w{i}" for i in range(235)]
    pages = [Page(page=1, text=" ".join(words))]
    chunks = build_chunks(pages, chunk_words=130, chunk_stride=100)
    assert len(chunks) == 3
    assert len(chunks[-1].text.split(" ")) == 35
