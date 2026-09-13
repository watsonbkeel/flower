# Stage 8 species photo binding

Before the change, species confirmation assigned the newest uploaded image as
the plant's main photo, even if a later upload was unrelated to the displayed
recognition or was a memory photo.

Both clients now submit the recognition image ID. The backend validates its
plant, device and whole/leaf/flower purpose before changing species, and locks
the selected image through the confirmation transaction. It retains that image
indefinitely. Missing image IDs preserve the existing main photo. Invalid image
references reject the whole transaction without changing species or auto mode.

Image cleanup uses `FOR UPDATE SKIP LOCKED` so it cannot select an old expiration,
wait for confirmation and then delete the newly retained image without rechecking.

Evidence:

- `stage8-species-photo-red.xml`: all five API tests failed before implementation.
- `stage8-species-photo-lock-red.xml`: cleanup blocked behind a confirmation lock
  and exceeded the test timeout before the lock-skipping change.
- `stage8-species-photo-postgres.xml`: all 215 Python tests passed with one visible
  upstream Starlette/httpx warning. The six new tests cover explicit retention,
  later uploads, preserving the existing photo, invalid references and cleanup
  contention on actual PostgreSQL row locks.
- `stage8-species-photo-node-red.tap` and `stage8-species-photo-node-green.tap`:
  native request payload assertion failed first, then all 13 Node tests passed.
- `miniapp/scripts/verify-recognition.js`: rerun passed at 1440x1000 and 390x844,
  including new image-ID assertions for candidate and manual submissions. See
  `stage8-recognition-browser.json` and the refreshed recognition screenshots.

```sh
PYTHONPATH=backend .venv/bin/python scripts/test_postgres.py .venv/bin/pytest --junitxml=evidence/stage8-species-photo-postgres.xml
cd miniapp
node --test --test-reporter=tap --test-reporter-destination=../evidence/stage8-species-photo-node-green.tap tests/*.test.js
FONTCONFIG_FILE=/root/flower/.runtime/fonts.conf LD_LIBRARY_PATH=/root/flower/.runtime/browser/usr/lib/x86_64-linux-gnu node scripts/verify-recognition.js
```

Tests use synthetic images and Mock recognition; no real hardware or WeChat
acceptance is claimed. No production directories or host network services changed.
