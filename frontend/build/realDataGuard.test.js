import test from "node:test";
import assert from "node:assert/strict";
import { realDataGuard } from "./realDataGuard.js";

test("production guard rejects fixtures in lazy chunks but permits real API modules", () => {
  const plugin = realDataGuard();
  const context = { error: message => { throw new Error(message); } };
  for (const id of ["E:/Finmind/frontend/src/mocks/userMock.js", "E:/Finmind/frontend/src/pages/graph/mock.js", "E:\\Finmind\\frontend\\src\\pages\\dashboard\\pulseMock.js"]) {
    assert.throws(() => plugin.generateBundle.call(context, {}, { lazy: { type: "chunk", modules: { [id]: {} } } }), /Production must use real data/);
  }
  assert.doesNotThrow(() => plugin.generateBundle.call(context, {}, { page: { type: "chunk", modules: { "E:/Finmind/frontend/src/pages/graph/api.js": {} } } }));
});
