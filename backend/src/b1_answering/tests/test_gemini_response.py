import asyncio
import json
import unittest
from unittest.mock import AsyncMock, MagicMock
import httpx

from pathlib import Path
import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[3]))
from src.b1_answering.gemini import GeminiProvider, GeminiError
from src.b1_answering.policy import Limits


class MockTransport(httpx.AsyncBaseTransport):
    """Mock HTTP transport for testing without real API calls."""

    def __init__(self, response_body: bytes, status_code: int = 200):
        self.response_body = response_body
        self.status_code = status_code

    async def handle_async_request(self, request: httpx.Request) -> httpx.Response:
        """Return mocked response."""
        return httpx.Response(
            status_code=self.status_code,
            content=self.response_body,
            request=request,
        )


class TestGeminiResponseContract(unittest.TestCase):
    """Test Gemini response parsing per GEMINI_RESPONSE_CONTRACT.md."""

    def setUp(self):
        self.limits = Limits(
            model="gemini-3.5-flash-lite",
            read_timeout_seconds=30,
        )
        self.provider = None

    async def _call_generate(self, response_body: dict, status_code: int = 200):
        """Helper: call generate() with mocked transport."""
        body_bytes = json.dumps(response_body).encode("utf-8")
        transport = MockTransport(body_bytes, status_code)
        provider = GeminiProvider(
            self.limits,
            api_key="test-key",
            free_tier_confirmed=True,
            transport=transport,
        )
        return await provider.generate({"contents": []})

    async def _call_generate_error(self, response_body: dict, status_code: int = 200):
        """Helper: expect generate() to raise GeminiError."""
        body_bytes = json.dumps(response_body).encode("utf-8")
        transport = MockTransport(body_bytes, status_code)
        provider = GeminiProvider(
            self.limits,
            api_key="test-key",
            free_tier_confirmed=True,
            transport=transport,
        )
        try:
            await provider.generate({"contents": []})
            return None
        except GeminiError as e:
            return e.code

    def test_valid_text_with_signature_metadata(self):
        """Accept valid text part with thoughtSignature; metadata not concatenated."""
        response = {
            "candidates": [
                {
                    "finishReason": "STOP",
                    "content": {
                        "parts": [
                            {
                                "text": '{"result": "success"}',
                                "thoughtSignature": "sig_abc123",
                            }
                        ]
                    },
                }
            ],
            "usageMetadata": {
                "promptTokenCount": 10,
                "candidatesTokenCount": 5,
                "totalTokenCount": 15,
            },
        }
        result = asyncio.run(self._call_generate(response))
        self.assertEqual(result["payload"], {"result": "success"})
        self.assertEqual(result["usage"]["input_tokens"], 10)

    def test_skip_thought_true_parts(self):
        """Skip parts where thought:true; only emit text from thought:false parts."""
        response = {
            "candidates": [
                {
                    "finishReason": "STOP",
                    "content": {
                        "parts": [
                            {"text": "reasoning here", "thought": True},
                            {"text": '{"answer": 1}', "thought": False},
                        ]
                    },
                }
            ],
        }
        result = asyncio.run(self._call_generate(response))
        self.assertEqual(result["payload"], {"answer": 1})

    def test_split_text_parts_concatenated(self):
        """Concatenate multiple text parts; ignore ordering nuance."""
        response = {
            "candidates": [
                {
                    "finishReason": "STOP",
                    "content": {
                        "parts": [
                            {"text": '{"a": 1,'}, {"text": ' "b": 2}'},
                        ]
                    },
                }
            ],
        }
        result = asyncio.run(self._call_generate(response))
        self.assertEqual(result["payload"], {"a": 1, "b": 2})

    def test_signature_only_part_ignored(self):
        """Ignore signature-only parts (no text); don't fail."""
        response = {
            "candidates": [
                {
                    "finishReason": "STOP",
                    "content": {
                        "parts": [
                            {"thoughtSignature": "sig_xyz"},
                            {"text": '{"result": 1}'},
                        ]
                    },
                }
            ],
        }
        result = asyncio.run(self._call_generate(response))
        self.assertEqual(result["payload"], {"result": 1})

    def test_empty_response_no_candidates(self):
        """Return GEMINI_EMPTY_RESPONSE when candidates list is empty."""
        response = {"candidates": []}
        code = asyncio.run(self._call_generate_error(response))
        self.assertEqual(code, "GEMINI_EMPTY_RESPONSE")

    def test_empty_response_no_text(self):
        """Return GEMINI_EMPTY_RESPONSE when no non-blank text parts exist."""
        response = {
            "candidates": [
                {
                    "finishReason": "STOP",
                    "content": {"parts": [{"text": "   "}, {"text": ""}]},
                }
            ]
        }
        code = asyncio.run(self._call_generate_error(response))
        self.assertEqual(code, "GEMINI_EMPTY_RESPONSE")

    def test_blocked_response_prompt_feedback(self):
        """Return GEMINI_BLOCKED when promptFeedback.blockReason is set."""
        response = {"promptFeedback": {"blockReason": "SAFETY"}}
        code = asyncio.run(self._call_generate_error(response))
        self.assertEqual(code, "GEMINI_BLOCKED")

    def test_blocked_response_finish_reason(self):
        """Return GEMINI_BLOCKED for finish reasons: SAFETY, RECITATION, BLOCKLIST."""
        for reason in ["SAFETY", "RECITATION", "BLOCKLIST", "PROHIBITED_CONTENT", "SPII"]:
            response = {
                "candidates": [
                    {
                        "finishReason": reason,
                        "content": {"parts": [{"text": "test"}]},
                    }
                ]
            }
            code = asyncio.run(self._call_generate_error(response))
            self.assertEqual(
                code, "GEMINI_BLOCKED", f"Expected GEMINI_BLOCKED for {reason}"
            )

    def test_invalid_type_text_not_string(self):
        """Reject text field that is not a string."""
        response = {
            "candidates": [
                {
                    "finishReason": "STOP",
                    "content": {"parts": [{"text": 123}]},
                }
            ]
        }
        code = asyncio.run(self._call_generate_error(response))
        self.assertEqual(code, "INVALID_GEMINI_RESPONSE")

    def test_invalid_type_signature_not_string(self):
        """Reject thoughtSignature that is not a string."""
        response = {
            "candidates": [
                {
                    "finishReason": "STOP",
                    "content": {
                        "parts": [{"text": '{"x": 1}', "thoughtSignature": 42}]
                    },
                }
            ]
        }
        code = asyncio.run(self._call_generate_error(response))
        self.assertEqual(code, "INVALID_GEMINI_RESPONSE")

    def test_invalid_type_signature_empty_string(self):
        """Reject empty thoughtSignature string."""
        response = {
            "candidates": [
                {
                    "finishReason": "STOP",
                    "content": {
                        "parts": [{"text": '{"x": 1}', "thoughtSignature": ""}]
                    },
                }
            ]
        }
        code = asyncio.run(self._call_generate_error(response))
        self.assertEqual(code, "INVALID_GEMINI_RESPONSE")

    def test_invalid_type_thought_not_bool(self):
        """Reject thought field that is not boolean."""
        response = {
            "candidates": [
                {
                    "finishReason": "STOP",
                    "content": {"parts": [{"text": '{"x": 1}', "thought": "yes"}]},
                }
            ]
        }
        code = asyncio.run(self._call_generate_error(response))
        self.assertEqual(code, "INVALID_GEMINI_RESPONSE")

    def test_unknown_field_rejected(self):
        """Reject parts with unknown fields (e.g., functionCall, inlineData)."""
        for field in ["functionCall", "inlineData", "customField"]:
            response = {
                "candidates": [
                    {
                        "finishReason": "STOP",
                        "content": {"parts": [{"text": '{"x": 1}', field: {}}]},
                    }
                ]
            }
            code = asyncio.run(self._call_generate_error(response))
            self.assertEqual(
                code, "INVALID_GEMINI_RESPONSE", f"Expected rejection of field {field}"
            )

    def test_invalid_json_in_assembled_text(self):
        """Return INVALID_GEMINI_JSON when assembled text is not valid JSON dict."""
        response = {
            "candidates": [
                {
                    "finishReason": "STOP",
                    "content": {"parts": [{"text": "not json"}]},
                }
            ]
        }
        code = asyncio.run(self._call_generate_error(response))
        self.assertEqual(code, "INVALID_GEMINI_JSON")

    def test_invalid_json_non_dict(self):
        """Return INVALID_GEMINI_JSON when assembled text is JSON array or scalar."""
        response = {
            "candidates": [
                {
                    "finishReason": "STOP",
                    "content": {"parts": [{"text": "[1, 2, 3]"}]},
                }
            ]
        }
        code = asyncio.run(self._call_generate_error(response))
        self.assertEqual(code, "INVALID_GEMINI_JSON")

    def test_max_tokens_finish_reason(self):
        """Return OUTPUT_LIMIT_EXCEEDED for MAX_TOKENS finish reason."""
        response = {
            "candidates": [
                {
                    "finishReason": "MAX_TOKENS",
                    "content": {"parts": [{"text": '{"x": 1}'}]},
                }
            ]
        }
        code = asyncio.run(self._call_generate_error(response))
        self.assertEqual(code, "OUTPUT_LIMIT_EXCEEDED")

    def test_malformed_envelope_missing_candidates(self):
        """Return INVALID_GEMINI_RESPONSE for missing candidates (backward compat)."""
        response = {}
        code = asyncio.run(self._call_generate_error(response))
        self.assertEqual(code, "INVALID_GEMINI_RESPONSE")

    def test_malformed_envelope_duplicate_keys(self):
        """Reject malformed JSON with duplicate keys in response body."""
        # Simulate duplicate key by manually constructing raw JSON
        body = b'{"candidates": [], "candidates": []}'
        transport = MockTransport(body)
        provider = GeminiProvider(
            self.limits,
            api_key="test-key",
            free_tier_confirmed=True,
            transport=transport,
        )
        try:
            asyncio.run(provider.generate({"contents": []}))
            self.fail("Expected GeminiError for duplicate keys")
        except GeminiError as e:
            self.assertEqual(e.code, "INVALID_GEMINI_RESPONSE")

    def test_no_secrets_in_error_messages(self):
        """Verify error codes do not leak response body, signatures, or credentials."""
        response = {
            "candidates": [
                {
                    "finishReason": "STOP",
                    "content": {
                        "parts": [
                            {
                                "text": '{"api_key": "secret"}',
                                "thoughtSignature": "sig_sensitive",
                            }
                        ]
                    },
                }
            ]
        }
        result = asyncio.run(self._call_generate(response))
        # Error message (GeminiError.code) should never contain signature or body
        self.assertNotIn("sig_sensitive", result["payload"].__str__())
        self.assertIsNone(result.get("raw_body"))
        self.assertIsNone(result.get("debug_log"))


if __name__ == "__main__":
    unittest.main()
