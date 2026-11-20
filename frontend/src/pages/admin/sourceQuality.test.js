import test from "node:test";
import assert from "node:assert/strict";
import { qualityLabel, reviewNote, replacementArticleId } from "./sourceQuality.js";
test("quality reason explains attachments/OCR without claiming a false article", () => {
  assert.match(qualityLabel("ATTACHMENT_TEXT_REQUIRED"), /tệp đính kèm/);
  assert.match(qualityLabel("OCR_REQUIRED"), /OCR/);
  assert.equal(reviewNote("source-quality-v1: SHORT_OR_EMPTY_BODY"), "Tự động: Nội dung quá ngắn hoặc chưa lấy được phần chữ");
  assert.equal(reviewNote("Đã xem nguồn."), "Đã xem nguồn.");
});

test("legacy OCR replacement opens its revision and human rejection has no replacement", () => {
  const id = "1708b06a-41db-54ef-ac34-3aa8adb9a42f";
  assert.equal(replacementArticleId({reviews:[{decision:"REJECTED", note:`Đã thay bằng bản trích xuất cần duyệt: ${id}`}]}), id);
  assert.equal(replacementArticleId({reviews:[{decision:"REJECTED",note:"Nội dung không đạt"}]}), null);
});
