# Stage 8 recognition selection verification

Source: Mock recognition and browser route fixtures. No real camera, Provider,
WeChat device or production acceptance was performed.

- Before implementation, `backend/tests/test_recognition_selection.py` failed all
  four confidence/order cases; `stage8-recognition-red.xml` retains the failures.
- Native tests reproduced stale selection after a new low-confidence image and
  manual/candidate submission precedence; see `stage8-recognition-node-red.tap`.
- The API sorts a response copy by confidence and applies the frozen thresholds
  at 0.75, 0.749, 0.45 and 0.449. Stored Provider output is not changed by GET.
- Native selection resets on image change and survives same-image polling.
  Both clients submit the user's last explicit manual edit or candidate choice.
  Low-confidence results display a retake notice.

Validation:

```sh
PYTHONPATH=backend .venv/bin/python scripts/test_postgres.py .venv/bin/pytest --junitxml=evidence/stage8-recognition-postgres.xml
cd miniapp
node --test --test-reporter=tap --test-reporter-destination=../evidence/stage8-recognition-node-green.tap tests/*.test.js
FONTCONFIG_FILE=/root/flower/.runtime/fonts.conf LD_LIBRARY_PATH=/root/flower/.runtime/browser/usr/lib/x86_64-linux-gnu node scripts/verify-recognition.js
```

Results: 194 Python tests passed with one visible upstream Starlette/httpx
deprecation warning; 11 Node tests passed. Playwright passed at 1440x1000 and
390x844, checking submitted payloads, default selection, low-confidence notice,
page errors and horizontal overflow. See `stage8-recognition-browser.json` and
`stage8-recognition-{1440,390}.png`. The mobile screenshot was visually inspected.

The PostgreSQL runner used isolated unpacked PostgreSQL and a private Unix
socket, then stopped and cleaned up the test instance. No host service changed.
