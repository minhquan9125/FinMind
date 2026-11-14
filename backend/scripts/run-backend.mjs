import { existsSync } from "node:fs";
import { spawn } from "node:child_process";
import { dirname, resolve } from "node:path";
import { fileURLToPath } from "node:url";

const backend = resolve(dirname(fileURLToPath(import.meta.url)), "..");
const root = resolve(backend, "..");
const python = resolve(root, ".venv", process.platform === "win32" ? "Scripts/python.exe" : "bin/python");

if (!existsSync(python)) {
  console.error("Chưa có .venv. Tại gốc FinMind, chạy: python -m venv .venv");
  console.error("Sau đó dùng Python trong .venv để cài: -m pip install -r backend/requirements.txt");
  process.exit(1);
}

const child = spawn(python, [
  "-B", "-m", "uvicorn", "src.main:app",
  "--host", "127.0.0.1", "--port", "8000", "--workers", "1",
  ...process.argv.slice(2),
], { cwd: backend, stdio: "inherit" });

// Forward termination and let uvicorn close its DB pool and collector.
for (const signal of ["SIGINT", "SIGTERM"]) {
  process.on(signal, () => { if (!child.killed) child.kill(signal); });
}
child.on("error", (error) => {
  console.error(`Không khởi động được backend: ${error.message}`);
  process.exitCode = 1;
});
child.on("exit", (code, signal) => { process.exitCode = code ?? (signal ? 1 : 0); });
