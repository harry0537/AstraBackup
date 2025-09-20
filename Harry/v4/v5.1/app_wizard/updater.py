import hashlib
import json
import os
import shutil
import tempfile
import zipfile
from typing import Dict, List

import requests


def sha256(path: str) -> str:
    h = hashlib.sha256()
    with open(path, 'rb') as f:
        for chunk in iter(lambda: f.read(1 << 20), b''):
            h.update(chunk)
    return h.hexdigest()


def install_root() -> str:
    root = os.path.expanduser("~/.astra")
    os.makedirs(root, exist_ok=True)
    return root


def load_manifest(manifest_url: str) -> Dict:
    r = requests.get(manifest_url, timeout=10)
    r.raise_for_status()
    return r.json()


def update_from_github(manifest_url: str, zip_url: str) -> str:
    manifest = load_manifest(manifest_url)
    version = manifest.get("version", "dev")
    root = install_root()
    target_dir = os.path.join(root, version)
    if os.path.exists(target_dir):
        return target_dir

    with tempfile.TemporaryDirectory() as td:
        zpath = os.path.join(td, 'repo.zip')
        with requests.get(zip_url, stream=True, timeout=30) as r:
            r.raise_for_status()
            with open(zpath, 'wb') as f:
                for chunk in r.iter_content(1 << 20):
                    f.write(chunk)

        with zipfile.ZipFile(zpath) as zf:
            zf.extractall(td)

        # Find extracted root
        roots: List[str] = [os.path.join(td, d) for d in os.listdir(td) if os.path.isdir(os.path.join(td, d))]
        src_root = roots[0] if roots else td

        os.makedirs(target_dir, exist_ok=True)
        for art in manifest.get('artifacts', []):
            src = os.path.join(src_root, art['path'])
            dst = os.path.join(target_dir, os.path.basename(art['path']))
            os.makedirs(os.path.dirname(dst), exist_ok=True)
            shutil.copy2(src, dst)
            if 'sha256' in art:
                assert sha256(dst) == art['sha256']

    # Atomically point current -> version
    current = os.path.join(root, 'current')
    tmp = current + '.tmp'
    try:
        if os.path.islink(tmp) or os.path.exists(tmp):
            os.unlink(tmp)
        os.symlink(target_dir, tmp)
        os.replace(tmp, current)
    except Exception:
        # On Windows, symlink may fail; write a marker file instead
        with open(current, 'w') as f:
            f.write(target_dir)

    return target_dir


