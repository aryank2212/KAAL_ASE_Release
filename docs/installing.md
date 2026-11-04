# Installing KAAL ASE 2.2

All three installers set up the same thing: the API plus the web console, SQLite storage, no Docker needed.
The console is at `http://127.0.0.1:8140/ui/`. On first start a random API key is generated and saved with
owner-only permissions; the console asks for it once.

| Platform | File | Install |
|---|---|---|
| Debian / Ubuntu | `kaal-ase_<ver>_all.deb` | `sudo apt install ./kaal-ase_<ver>_all.deb` |
| Arch / Manjaro | `kaal-ase-<ver>-1-any.pkg.tar.zst` | `sudo pacman -U kaal-ase-<ver>-1-any.pkg.tar.zst` |
| Windows 10/11 (x64) | `KAAL-ASE-<ver>-setup.exe` | Run it. No admin rights needed (per-user install). |

Linux packages create a Python environment at install time (internet needed once, about 760 MB on disk because of
OpenCV, GDAL and Maigret) and install a systemd service `kaal-ase`:

    sudo systemctl enable --now kaal-ase
    sudo cat /var/lib/kaal-ase/api_key        # paste into the console
    sudoedit /etc/kaal-ase/kaal-ase.env       # port, model host, API keys for optional sources

Windows: the installer adds a Start Menu shortcut that starts KAAL ASE and opens the console already signed in
(the key is passed in the URL fragment, which never reaches the server, and is removed from the address bar
immediately; it only protects a service bound to this PC). The executable is not code-signed, so SmartScreen will
show a warning the first time: choose "More info", then "Run anyway", and compare the file with `SHA256SUMS.txt`.
Data lives in `%APPDATA%\KAAL-ASE`.

## Optional tools

Holehe, GHunt and the face models are installed separately (they have their own licences and GHunt needs your own
Google login):

    sudo -u kaal-ase /opt/kaal-ase/install-optional-tools.sh      # Linux
    .\install-optional-tools.ps1                                  # Windows (needs Python on PATH)

ExifTool: the `.deb` and Arch packages depend on the distribution's ExifTool; the Windows installer bundles the
official build only if its published SHA-256 verified during the build, otherwise it falls back to ExifRead.

## Docker Compose (V1 style stack)

`docker compose up` still works and uses `requirements.txt` with PostgreSQL; the installers above use
`requirements-core.txt` with SQLite.
