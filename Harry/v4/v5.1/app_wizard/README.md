# Astra Wizard (v5)

Quick wizard to update scripts from GitHub and run proximity + data relay.

## Run (development)

Windows:
```
python -m app_wizard.main
```

Linux:
```
python3 -m app_wizard.main
```

Set env vars to point to your GitHub sources (optional; local fallback used if unset):
```
ASTRA_MANIFEST_URL=https://.../manifest.json
ASTRA_ZIP_URL=https://.../repo.zip
```

## Build

Windows:
```
app_wizard\build_windows.bat
```

Linux:
```
chmod +x app_wizard/build_linux.sh
app_wizard/build_linux.sh
```

The app currently uses a CLI wizard. A Qt UI can be added next.
