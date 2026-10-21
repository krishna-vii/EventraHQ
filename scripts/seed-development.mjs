import { spawn } from 'node:child_process';
import { existsSync } from 'node:fs';
import { resolve } from 'node:path';
const root = resolve(import.meta.dirname, '..');
if (existsSync(resolve(root, '.env'))) process.loadEnvFile(resolve(root, '.env'));
const python = process.env.EVENTRA_PYTHON || resolve(root, 'services/api/.venv', process.platform === 'win32' ? 'Scripts/python.exe' : 'bin/python');
const child = spawn(python, [resolve(root, 'scripts/seed_development.py'), ...process.argv.slice(2)], {
  cwd: root, stdio: 'inherit', windowsHide: true,
});
child.on('error', () => { console.error('Install the API virtual environment before running the development seed.'); process.exitCode = 1; });
child.on('exit', code => { process.exitCode = code ?? 1; });
