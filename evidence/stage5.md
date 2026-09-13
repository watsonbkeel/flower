# Stage 5 development verification

Source: MOCK/TEST. No WeChat console, native DevTools or physical phone acceptance.

- `PYTHONPATH=backend .venv/bin/python scripts/test_postgres.py .venv/bin/pytest --junitxml=evidence/stage5-postgres.xml`: 128 passed.
- `cd miniapp && npm test`: 6 passed; lifecycle labels, coverage, fault gate, template bindings and job resume/error handling.
- `stage5-photo-red.xml`: missing upload route failed before implementation.
- Browser: `FONTCONFIG_FILE=/root/flower/.runtime/fonts.conf LD_LIBRARY_PATH=/root/flower/.runtime/browser/usr/lib/x86_64-linux-gnu node scripts/verify-preview.js` from miniapp.
- Desktop 1440x1000 and mobile 390x844 screenshots, asset pixels, canvas pixels, six routes and document overflow checked in `stage5-browser.json`.
- Browser dependencies/font packages were extracted under ignored `.runtime`; no host package installation.
- Development preview uses loopback port 18082, private SQLite and actual API/Worker contracts with Mock Pi executor. It is not production.
