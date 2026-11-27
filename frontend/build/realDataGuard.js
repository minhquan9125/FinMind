const forbidden = /\/(?:mocks\/|(?:mock|\w*Mock|mockApi|apiAdapter)\.[cm]?[jt]sx?$)/;

// Inspect emitted chunks, including lazy routes. Test fixtures must never enter
// a production chunk or become a fallback when an API request fails.
export function realDataGuard() {
  return {
    name: "finmind-real-data-only",
    apply: "build",
    generateBundle(_options, bundle) {
      const fixtures = new Set();
      for (const entry of Object.values(bundle)) {
        if (entry.type !== "chunk") continue;
        for (const id of Object.keys(entry.modules)) {
          const normalized = id.replaceAll("\\", "/").split("?")[0];
          if (normalized.includes("/src/") && forbidden.test(normalized)) fixtures.add(normalized);
        }
      }
      if (fixtures.size) this.error(`Production must use real data. Remove fixture imports:\n${[...fixtures].join("\n")}`);
    },
  };
}
