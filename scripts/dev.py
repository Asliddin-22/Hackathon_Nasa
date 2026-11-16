#!/usr/bin/env python3
"""Start both local services and stop their process groups together."""
import os
from pathlib import Path
import signal
import subprocess
import sys
import time

ROOT = Path(__file__).resolve().parents[1]
PYTHON = ROOT / '.venv' / 'bin' / 'python'

def main():
    if not PYTHON.exists() or not (ROOT / 'frontend' / 'node_modules').exists():
        sys.exit('Install dependencies first; see README.md.')
    env_args = ['--env-file', str(ROOT / '.env')] if (ROOT / '.env').exists() else []
    commands = [([str(PYTHON), '-m', 'uvicorn', 'backend.app.main:app', '--reload', '--reload-dir', str(ROOT / 'backend'), '--reload-dir', str(ROOT / 'simulator'), '--host', '127.0.0.1', '--port', '8000', *env_args], ROOT),
                (['npm', 'run', 'dev', '--', '--port', '5173', '--strictPort'], ROOT / 'frontend')]
    processes=[]
    def shutdown(*_):
        raise KeyboardInterrupt()
    signal.signal(signal.SIGTERM, shutdown)
    try:
        for command, cwd in commands:
            processes.append(subprocess.Popen(command, cwd=cwd, start_new_session=True))
        print('\nGravityGuard dashboard: http://127.0.0.1:5173\nAPI documentation: http://127.0.0.1:8000/docs\n', flush=True)
        while all(p.poll() is None for p in processes):
            time.sleep(.3)
    except KeyboardInterrupt:
        pass
    finally:
        for p in processes:
            if p.poll() is None:
                os.killpg(p.pid, signal.SIGTERM)
        for p in processes:
            try:
                p.wait(timeout=5)
            except subprocess.TimeoutExpired:
                os.killpg(p.pid, signal.SIGKILL)
        return max([p.returncode or 0 for p in processes] + [0])

if __name__ == '__main__':
    sys.exit(main())
