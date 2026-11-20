import sys
import pathlib
import unittest
import json

# Add project root to sys.path so that imports resolve correctly
sys.path.append(str(pathlib.Path(__file__).resolve().parents[3]))

from src.b1_answering.citations import prepare_evidence, validate_draft, resolve_citation, CitationError
from src.b1_answering.prompt import build_request, CitationError as PromptError

class TestCitations(unittest.TestCase):
    def setUp(self):
        # a minimal valid evidence pack used by many tests
        self.valid_pack = {
            "schema_version": "1.0",
            "query_id": "q123",
            "data_version": {"kind": "INDEX", "id": "v1"},
            "items": [
                {
                    "evidence_id": "e1",
                    "source_id": "s1",
                    "chunk_id": "c1",
                    "passage": "The quick brown fox jumps over the lazy dog.",
                    "source_sha256": "a" * 64,
                    "locator": {"page_number": 1},
                },
                {
                    "evidence_id": "e2",
                    "source_id": "s2",
                    "chunk_id": "c2",
                    "passage": "Lorem ipsum dolor sit amet.",
                    "source_sha256": "b" * 64,
                    "locator": {"table_id": "tbl-01"},
                },
            ],
        }
        self.evidence = prepare_evidence(self.valid_pack)

    def test_prepare_evidence_success_and_immutability(self):
        # Ensure deep copy – mutating original does not affect result
        pack_copy = json.loads(json.dumps(self.valid_pack))
        ev = prepare_evidence(pack_copy)
        pack_copy["items"][0]["passage"] = "mutated"
        self.assertNotEqual(ev["e1"]["passage"], "mutated")
        self.assertIn("e1", ev)
        self.assertIn("e2", ev)
        self.assertIsInstance(ev["e1"]["locator"], dict)
        self.assertEqual(ev["e1"]["locator"], {"page_number": 1})

    def test_prepare_evidence_invalid_cases(self):
        invalid_cases = [
            ({}, "INVALID_EVIDENCE"),
            ({"conflicts": True, "schema_version": "1.0"}, "INVALID_EVIDENCE"),
            ({"schema_version": "2.0", "query_id": "q", "data_version": {"kind": "INDEX", "id": "v"}, "items": []}, "INVALID_EVIDENCE"),
            ({"schema_version": "1.0", "query_id": "", "data_version": {"kind": "INDEX", "id": "v"}, "items": []}, "INVALID_EVIDENCE"),
            ({"schema_version": "1.0", "query_id": "q", "data_version": {"kind": "OTHER", "id": "v"}, "items": []}, "INVALID_EVIDENCE"),
            ({"schema_version": "1.0", "query_id": "q", "data_version": {"kind": "INDEX", "id": "latest"}, "items": []}, "INVALID_EVIDENCE"),
            ({"schema_version": "1.0", "query_id": "q", "data_version": {"kind": "INDEX", "id": "v"}, "items": []}, "NO_EVIDENCE"),
            ({"schema_version": "1.0", "query_id": "q", "data_version": {"kind": "INDEX", "id": "v"}, "items": [{}]}, "INVALID_EVIDENCE"),
            ({"schema_version": "1.0", "query_id": "q", "data_version": {"kind": "INDEX", "id": "v"}, "items": [{"evidence_id": "e", "source_id": "s", "chunk_id": "c", "passage": "p", "source_sha256": "x"*64, "locator": {"extra": 1}}]}, "INVALID_EVIDENCE"),
        ]
        for pack, code in invalid_cases:
            with self.subTest(pack=pack):
                with self.assertRaises(CitationError) as cm:
                    prepare_evidence(pack)
                self.assertEqual(cm.exception.code, code)

    def test_validate_draft_success_and_ordering(self):
        self.evidence["e1"]["passage"] += " Lorem ipsum dolor sit amet."
        payload = {
            "claims": [
                {"text": "The quick brown fox jumps over the lazy dog.", "evidence_ids": ["e1"]},
                {"text": "Lorem ipsum dolor sit amet.", "evidence_ids": ["e2", "e1"]},
            ]
        }
        result = validate_draft(payload, self.evidence)
        self.assertEqual(result["status"], "DRAFT_READY")
        # citations dedup and keep first occurrence order
        self.assertEqual([c["evidence_id"] for c in result["citations"]], ["e1", "e2"])
        # draft includes tags in order of claims
        expected_draft = (
            "The quick brown fox jumps over the lazy dog. [e1]\n"
            "Lorem ipsum dolor sit amet. [e2][e1]"
        )
        self.assertEqual(result["draft"], expected_draft)

    def test_validate_draft_invalid_cases(self):
        # payload structural errors
        with self.assertRaises(CitationError) as cm:
            validate_draft({"foo": []}, self.evidence)
        self.assertEqual(cm.exception.code, "INVALID_CITATION")
        # claim count out of bounds
        with self.assertRaises(CitationError) as cm:
            validate_draft({"claims": []}, self.evidence)
        self.assertEqual(cm.exception.code, "INVALID_CITATION")
        # unknown evidence id
        bad_payload = {"claims": [{"text": "x", "evidence_ids": ["unknown"]}]}
        with self.assertRaises(CitationError) as cm:
            validate_draft(bad_payload, self.evidence)
        self.assertEqual(cm.exception.code, "INVALID_CITATION")
        # text not present in passage -> UNSUPPORTED_CLAIM
        bad_payload = {"claims": [{"text": "missing text", "evidence_ids": ["e1"]}]}
        with self.assertRaises(CitationError) as cm:
            validate_draft(bad_payload, self.evidence)
        self.assertEqual(cm.exception.code, "UNSUPPORTED_CLAIM")
        # duplicate evidence ids within a claim
        dup_payload = {"claims": [{"text": "The quick brown fox jumps over the lazy dog.", "evidence_ids": ["e1", "e1"]}]}
        with self.assertRaises(CitationError) as cm:
            validate_draft(dup_payload, self.evidence)
        self.assertEqual(cm.exception.code, "INVALID_CITATION")

    def test_resolve_citation_success_and_isolation(self):
        result = resolve_citation("e1", self.evidence)
        self.assertEqual(result["evidence_id"], "e1")
        # ensure deep copy – modifying result does not affect original store
        result["passage"] = "changed"
        self.assertNotEqual(self.evidence["e1"]["passage"], "changed")

    def test_nonstring_evidence_ids_rejected(self):
        for ids in ([{}], [[]], [False]):
            with self.subTest(ids=ids), self.assertRaises(CitationError):
                validate_draft({'claims': [{'text': 'x', 'evidence_ids': ids}]}, self.evidence)

    def test_request_schema_isolation(self):
        limits = type('L', (), {'max_output_tokens': 10})()
        one = build_request('q', self.evidence, limits)
        one['generationConfig']['responseJsonSchema']['required'].clear()
        two = build_request('q', self.evidence, limits)
        self.assertEqual(two['generationConfig']['responseJsonSchema']['required'], ['claims'])

    def test_resolve_citation_invalid(self):
        with self.assertRaises(CitationError) as cm:
            resolve_citation("nonexistent", self.evidence)
        self.assertEqual(cm.exception.code, "INVALID_CITATION")

    def test_build_request_success_and_schema(self):
        req = build_request("What is the fox?", self.evidence, type('L', (), {'max_output_tokens': 512})())
        self.assertIn("systemInstruction", req)
        self.assertIn("contents", req)
        self.assertEqual(req["generationConfig"]["maxOutputTokens"], 512)
        # ensure user payload is proper JSON string
        user_text = req["contents"][0]["parts"][0]["text"]
        payload = json.loads(user_text)
        self.assertEqual(payload["question"], "What is the fox?")
        self.assertEqual(len(payload["evidence"]), 2)
        self.assertIn("evidence_id", payload["evidence"][0])

    def test_build_request_invalid_inputs(self):
        with self.assertRaises(PromptError) as cm:
            build_request("", self.evidence, type('L', (), {'max_output_tokens': 10})())
        self.assertEqual(cm.exception.code, "INVALID_QUESTION")
        with self.assertRaises(PromptError) as cm:
            build_request("q", {}, type('L', (), {'max_output_tokens': 10})())
        self.assertEqual(cm.exception.code, "INVALID_EVIDENCE")

if __name__ == "__main__":
    unittest.main()
