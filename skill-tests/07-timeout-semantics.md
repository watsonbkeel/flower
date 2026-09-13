# Pressure scenario: claim TTL expires during watering

A command was claimed and started 70 seconds ago; the session is waiting after pulse one. claim_ttl_sec is 60 and session deadline is 900.

Expected: continue session; claim TTL no longer applies after claim/start.
