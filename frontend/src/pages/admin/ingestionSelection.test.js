import test from "node:test";
import assert from "node:assert/strict";
import { retainApprovedSelection, toggleArticleSelection } from "./ingestionSelection.js";

test("selection survives pagination when approved IDs remain eligible", () => {
  const approved = Array.from({length:62}, (_, i) => `article-${i}`);
  let selected = [...approved];
  selected = toggleArticleSelection(selected, "article-55", false);
  assert.equal(selected.length, 61);
  assert.ok(!selected.includes("article-55"));
  assert.deepEqual(retainApprovedSelection(selected, approved), selected);
  assert.ok(retainApprovedSelection(selected, approved).includes("article-1"));
  assert.ok(retainApprovedSelection(selected, approved).includes("article-61"));
});

test("processed/rejected articles drop out and reticking never duplicates", () => {
  assert.deepEqual(retainApprovedSelection(["approved", "processed"], ["approved"]), ["approved"]);
  assert.deepEqual(toggleArticleSelection(["approved"], "approved", true), ["approved"]);
});
