# Production Run Guide

This guide explains how to deploy the Gemini OCR pipeline as a robust systemd service on an Ubuntu server, handle logging with rotation, and generate performance reports.

## 1. Service Deployment (Systemd)

We use `systemd` to manage the OCR process, ensuring it restarts on failure and respects environment configurations.

### Installation

1.  **Copy Service Files & Wrapper:**
    ```bash
    # Service definition
    sudo cp ops/systemd/gemini-ocr.service /etc/systemd/system/

    # Environment configuration
    sudo cp ops/systemd/gemini-ocr.env /etc/default/gemini-ocr

    # Wrapper script (builds CLI args from env)
    sudo cp ops/systemd/gemini-ocr-run.sh /usr/local/bin/
    sudo chmod +x /usr/local/bin/gemini-ocr-run.sh
    ```

2.  **Configure Service User & Paths:**
    Edit `/etc/systemd/system/gemini-ocr.service` to match your user and installation path:
    ```ini
    [Service]
    User=tomaasz
    Group=tomaasz
    WorkingDirectory=/home/tomaasz/projects/ocr-gemini
    ```
    *Note: Failing to set the correct user will result in permission errors accessing files.*

3.  **Configure Environment:**
    Edit `/etc/default/gemini-ocr`.

    **Example Configuration:**
    ```bash
    # Paths (Quotes are handled automatically by the wrapper, but creating variables safely is recommended)
    OCR_ROOT="/home/tomaasz/mnt/nas_genealogy/Sources/Nurskie dokumenty/"
    OCR_OUT_ROOT="/home/tomaasz/ocr_out"

    # OCR Settings
    OCR_PROMPT_ID="agad_generic"
    OCR_PROFILE_DIR="/home/tomaasz/.pw_gemini_profile"

    # Runtime Control
    OCR_LIMIT=1000        # Files per restart (avoids memory leaks)
    OCR_RECURSIVE=1       # Scan subdirectories (0/1)
    OCR_HEADED=0          # Run browser in headless mode (0/1)
    OCR_IMPORT_ONLY=false # Set to true to just scan files
    ```
    *Note: The wrapper correctly handles spaces in `OCR_ROOT`.*

4.  **Enable & Start:**
    ```bash
    sudo systemctl daemon-reload
    sudo systemctl enable gemini-ocr
    sudo systemctl start gemini-ocr
    ```

5.  **Status Check:**
    ```bash
    sudo systemctl status gemini-ocr
    journalctl -u gemini-ocr -f
    ```

### Diagnostic Mode
To verify arguments without running the OCR, you can use the wrapper's debug mode:
```bash
# Verify how arguments are parsed (prints command and exits)
sudo -u tomaasz bash -c 'set -a; source /etc/default/gemini-ocr; set +a; PRINT_ARGS=1 /usr/local/bin/gemini-ocr-run.sh'
```

---

## 2. Logging & Rotation

Standard output is captured by `journald`.

### Logrotate Configuration
If you configure file logging (see `ops/logrotate`), ensure the log directory exists and is writable by the service user.

---

## 3. Metrics & Reporting

Use the helper script to view performance:
```bash
journalctl -u gemini-ocr --since "1 hour ago" | python3 scripts/metrics_summary.py
```

---

## 4. Troubleshooting

### Duplicated flags or missing `--prompt-id`
If you see logs like `--out-root ... --out-root ...` or missing arguments:
1.  **Check the wrapper version:** Ensure `/usr/local/bin/gemini-ocr-run.sh` is up to date with `ops/systemd/gemini-ocr-run.sh`. Old versions might loop or miss new variables.
2.  **Verify Environment:** Run the **Diagnostic Mode** command (above). It shows exactly what arguments are passed to Python.
3.  **Check Variable Names:** Ensure you use `OCR_PROMPT_ID` (not `PROMPT_ID`) and `OCR_OUT_ROOT` in `/etc/default/gemini-ocr`.

### Service fails to start
*   **Permissions:** Check if `User` in `gemini-ocr.service` has access to `OCR_PROFILE_DIR` and `OCR_ROOT`.
*   **Paths:** Ensure `WorkingDirectory` points to the valid repo root containing `gemini_ocr.py`.
