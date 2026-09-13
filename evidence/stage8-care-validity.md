# Stage 8 care validity presentation

Frozen specification section 12.4 requires an update prompt when knowledge expires.
Native and browser clients now distinguish missing, pending confirmation, confirmed,
expired and malformed-expiry care cards. Expiry takes precedence over historical
confirmation. Only valid, unconfirmed cards enable confirmation.

The shared model test failed before implementation (`stage8-care-validity-red.tap`).
All 12 Node tests now pass (`stage8-care-validity-green.tap`). Full isolated PostgreSQL
regression passes all 197 tests (`stage8-care-validity-postgres.xml`) with the existing
visible upstream Starlette/httpx deprecation warning.

Browser verification command (from `miniapp`):

```sh
FONTCONFIG_FILE=/root/flower/.runtime/fonts.conf LD_LIBRARY_PATH=/root/flower/.runtime/browser/usr/lib/x86_64-linux-gnu node scripts/verify-care-validity.js
```

The script covers 1440x1000 and 390x844, checking time/state transitions, disabled
confirmation, available regeneration, preserved form input, overflow and page
errors. Route fixtures are explicitly Mock. It additionally exercises live Mock
research and care confirmation against the development API and Worker.
See `stage8-care-validity-browser.json` and `stage8-care-validity-{1440,390}.png`.

An extra run of the existing full `verify-workflow.js` stopped at its first watering
request: expected 202, received 409. A direct API check confirmed `MIN_INTERVAL`;
the shared development fixture retained its previous watering at 09:11 UTC.
No safety limits or historical records were changed to force that workflow through.
Its previous pass remains historical evidence, not a successful rerun in this change.
The updated care confirmation assertion is exercised independently by the new live
Mock research/confirmation check.

No production, native WeChat or physical acceptance is claimed.
