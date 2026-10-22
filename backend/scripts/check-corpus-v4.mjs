import { spawn } from 'node:child_process';
import { dirname, resolve } from 'node:path';
import { fileURLToPath } from 'node:url';

const root = resolve(dirname(fileURLToPath(import.meta.url)), '../..');
const python = resolve(root, '.venv', process.platform === 'win32' ? 'Scripts/python.exe' : 'bin/python');
const child = spawn(python, ['backend/scripts/check_corpus_v4.py', ...process.argv.slice(2)], {
  cwd: root, stdio: 'inherit',
});
child.on('error', () => { console.error('Không chạy được Python .venv; hãy cài môi trường theo README.'); process.exitCode = 1; });
child.on('exit', code => { process.exitCode = code ?? 1; });
