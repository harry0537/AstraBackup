import os
import subprocess
import sys
from typing import Dict, Optional


class ProcessManager:
    def __init__(self, base_dir: str):
        self.base_dir = base_dir
        self.procs: Dict[str, subprocess.Popen] = {}

    def _spawn(self, name: str, args: list, env: Optional[dict] = None) -> None:
        if name in self.procs and self.procs[name].poll() is None:
            return
        e = os.environ.copy()
        if env:
            e.update(env)
        self.procs[name] = subprocess.Popen(args, cwd=self.base_dir, env=e)

    def start_proximity(self) -> None:
        script = os.path.join(self.base_dir, 'combo_proximity_bridge_v4.py')
        self._spawn('proximity', [sys.executable, script])

    def start_data_relay(self) -> None:
        script = os.path.join(self.base_dir, 'rover_data_relay_v4.py')
        self._spawn('relay', [sys.executable, script])

    def stop_all(self) -> None:
        for p in list(self.procs.values()):
            try:
                if p.poll() is None:
                    p.terminate()
            except Exception:
                pass
        self.procs.clear()


