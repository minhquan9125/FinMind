import test from "node:test";
import assert from "node:assert/strict";
import { readNewsGraphPackage, newsGraphError } from "./newsGraphImport.js";

function batch() { return { items: [{ candidate: { candidate_id: "one", relation_type: "COOPERATES_WITH",
  subject: { canonical_name: "A" }, object: { canonical_name: "B" },
  evidence: [{ quote: "A hợp tác với B", chunk_id: "chunk", locator: {} }] }, evaluation: { status: "APPROVED" } }] }; }

test("file approval labels cannot become a saved server decision", () => {
  const value = readNewsGraphPackage(JSON.stringify(batch()));
  assert.equal(value.items[0].evaluation, undefined);
  assert.equal(value.items[0].candidate.candidate_id, "one");
});
test("persistence failures are not mislabeled as missing source evidence", () => {
  assert.match(newsGraphError(409, { code: "QUARANTINE_HISTORY_MISSING" }), /luồng lưu duyệt/);
  assert.match(newsGraphError(409, { code: "NEWS_REVIEW_NOT_READY" }), /kiểm tra lại chưa đạt/);
  assert.match(newsGraphError(503, { code: "NEWS_WRITER_NOT_CONFIGURED" }), /cấu hình ghi/);
  assert.match(newsGraphError(500, {}), /Dịch vụ/);
  assert.doesNotMatch(newsGraphError(409, "private-secret"), /private-secret/);
});
test("invalid file shapes fail before rendering evidence", () => {
  for (const text of ["not json", "null", "{}", '{"items":[]}']) assert.throws(() => readNewsGraphPackage(text));
  for (const change of [b => b.items[0].candidate.evidence.push(null),
    b => b.items[0].candidate.subject = {}, b => b.items.push(b.items[0]),
    b => b.items[0].candidate.attributes = { cooperation_scope: {} },
    b => b.items[0].candidate.temporal = { as_of: 2026 }]) {
    const value = batch(); change(value);
    assert.throws(() => readNewsGraphPackage(JSON.stringify(value)));
  }
});
