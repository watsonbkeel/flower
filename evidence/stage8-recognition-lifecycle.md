# Stage 8 recognition lifecycle

The previous recognition GET selected only images with completed results. While a
new upload was queued, running or failed, it silently returned old candidates.
The clients also lacked persistent capture/recognition progress in the care view.

The API now reports the latest capture command status. A successful capture uses
the latest whole/leaf/flower image within the server-recorded start/finish window.
Missing capture timestamps or missing images yield `image_missing`, not historical
candidates. Without capture history, it selects the latest recognition image.
Memory images are excluded. Pending/failed jobs return an empty result and their
actual status. Existing threshold and ranking rules remain unchanged.

Native and browser clients poll recognition progress independently of care jobs.
Browser polling updates the candidate area only when image/candidates change;
same-image manual input and explicit candidate selection survive refreshes.
Capture failures have camera-specific labels.

Before implementation, all 12 new backend cases failed
(`stage8-recognition-lifecycle-red.xml`), as did the new native progress test
(`stage8-recognition-lifecycle-node-red.tap`). After implementation, all 209 Python
and 13 Node tests pass. One existing upstream Starlette/httpx warning remains.

```sh
PYTHONPATH=backend .venv/bin/python scripts/test_postgres.py .venv/bin/pytest --junitxml=evidence/stage8-recognition-lifecycle-postgres.xml
cd miniapp
node --test --test-reporter=tap --test-reporter-destination=../evidence/stage8-recognition-lifecycle-node-green.tap tests/*.test.js
FONTCONFIG_FILE=/root/flower/.runtime/fonts.conf LD_LIBRARY_PATH=/root/flower/.runtime/browser/usr/lib/x86_64-linux-gnu node scripts/verify-recognition-lifecycle.js
FONTCONFIG_FILE=/root/flower/.runtime/fonts.conf LD_LIBRARY_PATH=/root/flower/.runtime/browser/usr/lib/x86_64-linux-gnu node scripts/verify-recognition.js
```

Browser output is `stage8-recognition-lifecycle-browser.json`, with 1440x1000 and
390x844 screenshots. Fixtures exercise removal of old results, automatic results,
manual/candidate preservation, camera failure and overflow. The final browser
case uses the actual development API, command gate, Mock camera upload and Worker.
The earlier selection/low-confidence browser checks were also rerun successfully.

All images and Provider results are Mock; no Pi camera, WeChat platform or physical
acceptance is claimed. The development API/Worker were restarted to load the change.
Production directories, host networking and external aibot services were untouched.
