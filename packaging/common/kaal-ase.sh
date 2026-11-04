#!/bin/sh
# Run KAAL ASE in the foreground as the current user (use the systemd service for always-on).
cd /opt/kaal-ase && exec /opt/kaal-ase/venv/bin/python -m app.launcher "$@"
