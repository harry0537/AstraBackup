import os
import sys

from . import APP_NAME, APP_VERSION
from .ui_wizard import run_cli_wizard


def main():
    # These URLs should point to your GitHub raw manifest and zip archive of scripts
    manifest_url = os.environ.get('ASTRA_MANIFEST_URL', 'https://example.com/manifest.json')
    zip_url = os.environ.get('ASTRA_ZIP_URL', 'https://example.com/repo.zip')

    print(f"{APP_NAME} v{APP_VERSION}")
    # Resolve base dir hint
    if getattr(sys, 'frozen', False):
        # Running from EXE; use the EXE directory for scripts
        base_dir_hint = os.path.abspath(os.path.dirname(sys.executable))
    else:
        base_dir_hint = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))

    try:
        run_cli_wizard(manifest_url, zip_url, base_dir_hint)
    except Exception as e:
        msg = f"Fatal error: {e}"
        print(msg)
        # On Windows EXE, show a message box so double-click users can see the error
        if os.name == 'nt':
            try:
                import ctypes
                ctypes.windll.user32.MessageBoxW(0, msg, APP_NAME, 0x10)
            except Exception:
                pass
        raise


if __name__ == '__main__':
    main()


