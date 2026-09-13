# Stage 1 Safety Core / v2.2.2

Source: MOCK / TEST. Physical tests: NOT_RUN.

Command: `.venv/bin/pytest --junitxml=evidence/stage1-green.xml`
Result: 67 passed (12 foundation + 55 Pi tests).

Red runs: stage1-red.xml, stage1-adapters-red.xml.

Coverage includes all sources in STARTING/SAFE_HOLD, uncertain sensor/time/calibration
rejection, independent timer shutdown, injected errors during pumping, session deadline
during waits, 60-second claim TTL separation, reservation before output HIGH, concurrent
reservations, 20 restart quota retention, unknown timestamp recovery, conservative cloud
quota merge, policy timezone/hash/version/expiry, P451 debounce and soil median filtering.

One initial debounce test supplied contradictory observations at the same instant; the
test now respects the required 200ms interval and full ten-second stable recovery.

Hardware adapters are lazy-loaded and not exercised against real GPIO, I2C, BLE or USB.
Encrypted stock Xiaomi packets report BINDKEY_REQUIRED/UNSUPPORTED_MODEL; SHT30 is the
supported fallback. No claim of encrypted-device compatibility is made.

The AST boundary test permits output HIGH only from the Flower executor. It does not
constitute an OS sandbox against a privileged process; physical deployment must give
Flower exclusive GPIO ownership and verify the actual service permissions.

Real calibration pumping remains blocked by B08. Calibration import validates measured
values but never pumps. Runtime, installation and diagnostics are integrated with Stage 2.
