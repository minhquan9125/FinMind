// Simplified version of the original demo's 5-step client-side pipeline.
// Chunking, tokenization, TF-IDF bookkeeping and embedding now all happen
// inside a single backend request (POST /api/documents), so the frontend
// cannot show live per-step progress without adding a streaming/polling API
// that nobody asked for. Instead this shows the 3 phases the browser can
// actually observe: sending the file, the server working, and done.

const STEPS = [
  { key: "uploading", label: "Sending PDF", desc: "upload to backend" },
  { key: "processing", label: "Server processing", desc: "extract, chunk, embed, index" },
  { key: "ready", label: "Ready", desc: "can search now" },
];

export default function PipelineStepper({ status }) {
  const currentIndex = STEPS.findIndex((s) => s.key === status);

  return (
    <div className="flex mt-1">
      {STEPS.map((step, i) => {
        const state = currentIndex < 0 ? "idle" : i < currentIndex ? "done" : i === currentIndex ? "active" : "idle";
        return (
          <div className="flex-1 text-center relative" key={step.key}>
            {i > 0 && (
              <div
                className={`absolute top-3 -left-1/2 w-full h-0.5 z-0 ${
                  state === "done" || state === "active" ? "bg-brand" : "bg-border"
                }`}
              />
            )}
            <div
              className={`w-6 h-6 rounded-full mx-auto mb-1.5 flex items-center justify-center text-[11px] font-bold text-white relative z-10 ${
                state === "active" ? "bg-amber-500 animate-pulse" : state === "done" ? "bg-brand" : "bg-border"
              }`}
            >
              {i + 1}
            </div>
            <div className={`text-[10.5px] leading-tight ${state === "idle" ? "text-muted" : "text-ink"}`}>
              {step.label}
            </div>
            <div className="text-[9.5px] text-muted mt-0.5">{step.desc}</div>
          </div>
        );
      })}
    </div>
  );
}
