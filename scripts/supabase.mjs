import { spawn } from 'node:child_process';
import { existsSync } from 'node:fs';
import { resolve } from 'node:path';

const root = resolve(import.meta.dirname, '..');
if (existsSync(resolve(root, '.env'))) process.loadEnvFile(resolve(root, '.env'));
const python = process.env.EVENTRA_PYTHON || resolve(root, 'services/api/.venv', process.platform === 'win32' ? 'Scripts/python.exe' : 'bin/python');
if (!existsSync(python)) {
  console.error('Install the API virtual environment first; see docs/SUPABASE_SETUP.md.');
  process.exit(1);
}
const child = spawn(python, [resolve(root, 'scripts/supabase_setup.py'), ...process.argv.slice(2)], {
  cwd: root, stdio: 'inherit', windowsHide: true, env: process.env,
});
child.on('error', () => { console.error('Unable to start the setup helper.'); process.exitCode = 1; });
child.on('exit', code => { process.exitCode = code ?? 1; });
