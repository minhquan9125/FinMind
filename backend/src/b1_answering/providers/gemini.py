import json
import os
from typing import Any, Dict, Optional
import httpx
from ..core.policy import Limits

MAX_RESPONSE_BYTES = 1024 * 1024


class GeminiError(Exception):
    def __init__(self, code: str):
        super().__init__(code)
        self.code = code


class GeminiProvider:
    def __init__(
        self,
        limits: Limits,
        *,
        api_key: Optional[str] = None,
        free_tier_confirmed: bool = False,
        transport: Optional[httpx.AsyncBaseTransport] = None,
    ):
        if not isinstance(limits, Limits):
            raise GeminiError("INVALID_LIMITS")
        self.limits = limits
        key = api_key if api_key is not None else os.environ.get("GEMINI_API_KEY")
        if not isinstance(key, str) or not key.strip() or any(c in key for c in "\r\n"):
            raise GeminiError("MISSING_API_KEY")
        confirmed = (free_tier_confirmed is True) or os.environ.get("B1_GEMINI_FREE_TIER_CONFIRMED") == "1"
        if not confirmed:
            raise GeminiError("FREE_TIER_NOT_CONFIRMED")
        self._api_key = key
        self._transport = transport
        self._base_url = f"https://generativelanguage.googleapis.com/v1beta/models/{limits.model}"

    def __repr__(self) -> str:
        return f"GeminiProvider(model={self.limits.model!r})"

    def _client(self) -> httpx.AsyncClient:
        timeouts = httpx.Timeout(self.limits.read_timeout_seconds, connect=10.0, write=10.0, pool=10.0)
        headers = {"x-goog-api-key": self._api_key, "content-type": "application/json"}
        return httpx.AsyncClient(
            transport=self._transport,
            timeout=timeouts,
            trust_env=False,
            follow_redirects=False,
            headers=headers,
        )

    async def _post(self, path: str, payload: Dict[str, Any]) -> bytes:
        url = f"{self._base_url}:{path}"
        async with self._client() as client:
            try:
                req = client.build_request("POST", url, json=payload)
                resp = await client.send(req, stream=True)
            except httpx.TimeoutException:
                raise GeminiError("GEMINI_TIMEOUT") from None
            except Exception:
                raise GeminiError("GEMINI_UNAVAILABLE") from None

            body = bytearray()
            try:
                async for chunk in resp.aiter_bytes():
                    body.extend(chunk)
                    if len(body) > MAX_RESPONSE_BYTES:
                        await resp.aclose()
                        raise GeminiError("INVALID_GEMINI_RESPONSE") from None
            except httpx.TimeoutException:
                raise GeminiError("GEMINI_TIMEOUT") from None
            except GeminiError:
                raise
            except Exception:
                raise GeminiError("GEMINI_UNAVAILABLE") from None
            finally:
                await resp.aclose()

        if resp.status_code == 429:
            raise GeminiError("RATE_LIMITED")
        if resp.status_code != 200:
            raise GeminiError("GEMINI_UNAVAILABLE") from None
        return bytes(body)

    async def count_tokens(self, request: Dict[str, Any]) -> int:
        body = {"generateContentRequest": {"model": f"models/{self.limits.model}", **request}}
        raw = await self._post("countTokens", body)
        try:
            data = json.loads(raw.decode("utf-8"))
            count = data.get("totalTokens")
            if type(count) is not int or count < 0:
                raise ValueError
            return count
        except Exception:
            raise GeminiError("INVALID_GEMINI_RESPONSE") from None

    async def generate(self, request: Dict[str, Any]) -> Dict[str, Any]:
        raw = await self._post("generateContent", request)

        def _pairs(pairs):
            d = {}
            for k, v in pairs:
                if k in d:
                    raise ValueError
                d[k] = v
            return d

        try:
            data = json.loads(
                raw.decode("utf-8"),
                object_pairs_hook=_pairs,
                parse_constant=lambda x: (_ for _ in ()).throw(ValueError),
            )
        except Exception:
            raise GeminiError("INVALID_GEMINI_RESPONSE") from None

        if not isinstance(data, dict):
            raise GeminiError("INVALID_GEMINI_RESPONSE")

        feedback = data.get("promptFeedback")
        if isinstance(feedback, dict) and feedback.get("blockReason"):
            raise GeminiError("GEMINI_BLOCKED")

        if "candidates" not in data:
            raise GeminiError("INVALID_GEMINI_RESPONSE")
        candidates = data.get("candidates")
        if not isinstance(candidates, list):
            raise GeminiError("INVALID_GEMINI_RESPONSE")
        if len(candidates) == 0:
            raise GeminiError("GEMINI_EMPTY_RESPONSE")
        if len(candidates) != 1:
            raise GeminiError("INVALID_GEMINI_RESPONSE")

        cand = candidates[0]
        if not isinstance(cand, dict):
            raise GeminiError("INVALID_GEMINI_RESPONSE")

        finish = cand.get("finishReason")
        if not isinstance(finish, str):
            raise GeminiError("INVALID_GEMINI_RESPONSE")
        if finish == "MAX_TOKENS":
            raise GeminiError("OUTPUT_LIMIT_EXCEEDED")
        if finish in {"SAFETY", "RECITATION", "BLOCKLIST", "PROHIBITED_CONTENT", "SPII"}:
            raise GeminiError("GEMINI_BLOCKED")
        if finish != "STOP":
            raise GeminiError("INVALID_GEMINI_RESPONSE")

        content = cand.get("content")
        if content is None:
            raise GeminiError("GEMINI_EMPTY_RESPONSE")
        if not isinstance(content, dict):
            raise GeminiError("INVALID_GEMINI_RESPONSE")

        parts = content.get("parts")
        if parts is None or (isinstance(parts, list) and len(parts) == 0):
            raise GeminiError("GEMINI_EMPTY_RESPONSE")
        if not isinstance(parts, list):
            raise GeminiError("INVALID_GEMINI_RESPONSE")

        answer_text_chunks = []
        for part in parts:
            if not isinstance(part, dict):
                raise GeminiError("INVALID_GEMINI_RESPONSE")
            recognized_keys = {"text", "thought", "thoughtSignature"}
            if not set(part.keys()).issubset(recognized_keys):
                raise GeminiError("INVALID_GEMINI_RESPONSE")

            if "thought" in part and not isinstance(part["thought"], bool):
                raise GeminiError("INVALID_GEMINI_RESPONSE")
            if "thoughtSignature" in part and (
                not isinstance(part["thoughtSignature"], str) or not part["thoughtSignature"]
            ):
                raise GeminiError("INVALID_GEMINI_RESPONSE")

            is_thought = part.get("thought") is True
            if "text" in part:
                if not isinstance(part["text"], str):
                    raise GeminiError("INVALID_GEMINI_RESPONSE")
                if not is_thought:
                    answer_text_chunks.append(part["text"])
            elif not is_thought and "thoughtSignature" in part and len(part) == 1:
                pass
            else:
                raise GeminiError("INVALID_GEMINI_RESPONSE")

        nonblank_answer = [chunk for chunk in answer_text_chunks if chunk.strip()]
        if not nonblank_answer:
            raise GeminiError("GEMINI_EMPTY_RESPONSE")

        full_text = "".join(answer_text_chunks)
        try:
            payload = json.loads(
                full_text,
                object_pairs_hook=_pairs,
                parse_constant=lambda x: (_ for _ in ()).throw(ValueError),
            )
        except Exception:
            raise GeminiError("INVALID_GEMINI_JSON") from None

        if not isinstance(payload, dict):
            raise GeminiError("INVALID_GEMINI_JSON")

        usage = None
        meta = data.get("usageMetadata")
        if isinstance(meta, dict):
            prompt = meta.get("promptTokenCount")
            cand_t = meta.get("candidatesTokenCount")
            tot = meta.get("totalTokenCount")
            if (
                type(prompt) is int
                and type(cand_t) is int
                and type(tot) is int
                and prompt >= 0
                and cand_t >= 0
                and tot >= 0
            ):
                usage = {"input_tokens": prompt, "output_tokens": cand_t, "total_tokens": tot}

        ver = data.get("modelVersion")
        model_version = ver.strip() if isinstance(ver, str) and ver.strip() else None
        return {"payload": payload, "usage": usage, "model_version": model_version}
