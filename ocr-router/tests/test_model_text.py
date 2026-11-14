import sys
from pathlib import Path

import pytest


sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from model import _validated_text_pages  # noqa: E402
from model import _call_ollama  # noqa: E402


def test_text_only_model_accepts_one_page_without_layout_blocks() -> None:
    result = _validated_text_pages({"pages": [{"file": "p-002.png",
                                              "text": "Tổng tài sản 2,77 triệu tỷ đồng",
                                              "unreadable": []}]}, ["p-002.png"])
    assert result["p-002.png"]["text"] == "Tổng tài sản 2,77 triệu tỷ đồng"
    assert "blocks" not in result["p-002.png"]


def test_text_only_model_rejects_missing_page() -> None:
    with pytest.raises(ValueError, match="đủ trang"):
        _validated_text_pages({"pages": [{"file": "p-002.png", "text": "A"}]},
                              ["p-002.png", "p-003.png"])


def test_ollama_sends_image_and_reads_text(monkeypatch, tmp_path: Path) -> None:
    import json

    image = tmp_path / "p-073.png"
    image.write_bytes(b"image data")
    seen = {}

    class Response:
        def __enter__(self):
            return self

        def __exit__(self, *_):
            return None

        def read(self):
            return json.dumps({"message": {"content": json.dumps({"pages": [
                {"file": "p-073.png", "text": "2,77 triệu tỷ đồng", "unreadable": []}
            ]})}, "prompt_eval_count": 12, "eval_count": 8}).encode()

    def fake_urlopen(request, timeout):
        seen["url"] = request.full_url
        seen["payload"] = json.loads(request.data)
        return Response()

    monkeypatch.setattr("model.urllib.request.urlopen", fake_urlopen)
    page, stats = _call_ollama({"page": 73, "image": image}, "qwen3-vl:4b-instruct",
                               "http://localhost:11434", 90)
    assert seen["url"] == "http://localhost:11434/api/chat"
    assert seen["payload"]["messages"][1]["images"] == ["aW1hZ2UgZGF0YQ=="]
    assert page["text"] == "2,77 triệu tỷ đồng"
    assert stats["input_tokens"] == 12
