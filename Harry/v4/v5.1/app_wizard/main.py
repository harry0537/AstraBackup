import os
import sys

from . import APP_NAME, APP_VERSION
from .ui_wizard import run_cli_wizard


def main():
    # These URLs should point to your GitHub raw manifest and zip archive of scripts
    manifest_url = os.environ.get('ASTRA_MANIFEST_URL', 'https://example.com/manifest.json')
    zip_url = os.environ.get('ASTRA_ZIP_URL', 'https://example.com/repo.zip')

    print(f"{APP_NAME} v{APP_VERSION}")
    # Hint base dir as the current repo root containing the v5.1 scripts
    base_dir_hint = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
    run_cli_wizard(manifest_url, zip_url, base_dir_hint)


if __name__ == '__main__':
    main()


