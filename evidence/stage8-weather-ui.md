# Stage 8 weather presentation audit

Requirements: v2.2.2 sections 3.4 (source separation), 11.1.B (current weather), 11.4 (explicit demo labels).

The native care page previously rendered missing rainfall as zero, hid a measured temperature of zero, and displayed expired weather as current. The browser also displayed stale forecasts without an expiry label.

- `stage8-weather-ui-red.tap`: 6 passes and 2 expected failures before implementation.
- `stage8-weather-ui-green.tap`: all 8 Node tests pass, including the native page load using the shared weather view model.
- `stage8-weather-browser.json`: desktop 1440x1000 and mobile 390x844 pass for zero readings, expired/missing weather, source labels, retained form input, no horizontal overflow and no page errors.
- `stage8-weather-current-{390,1440}.png` and `stage8-weather-expired-{390,1440}.png`: full-page browser screenshots. Mobile current and desktop expired screenshots were visually inspected; text and layout are legible without overlap.
- Browser weather responses were intercepted as explicit Mock fixtures. No production data or development database contents were changed by this verification.
- The preview updates only the weather section during background polling, preserving manual species input. Native polling uses the same view model.
- `node --check miniapp/preview/app.js` and `git diff --check` passed. Backend/Pi code is unchanged; the preceding full PostgreSQL evidence remains 166 passes.

Reproduce from `miniapp`:

```sh
node --test --test-reporter=tap --test-reporter-destination=../evidence/stage8-weather-ui-green.tap tests/*.test.js
FONTCONFIG_FILE=/root/flower/.runtime/fonts.conf LD_LIBRARY_PATH=/root/flower/.runtime/browser/usr/lib/x86_64-linux-gnu node scripts/verify-weather.js
```

The development stack remains at `http://127.0.0.1:18082/preview/`. Native WeChat DevTools and real phone acceptance remain B09; browser and Node tests do not replace those checks. Production, hardware and Provider blockers are unchanged.
