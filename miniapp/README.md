# Flower Mini Program

Specification: v2.2.2. Seven native pages use the authenticated Flower API.

Import this directory into WeChat DevTools. Replace the placeholder AppID in
`project.config.json` and register `https://flower.bkeel.com` as the request,
upload and download domain in the education account console. `config.js`
defaults to that HTTPS URL and real `wx.login`; never place AppSecret in this
directory. Local Mock testing requires a temporary development-only change to
the backend URL and `mockLogin` setting, then restoring the production defaults
before publishing. The server currently has no education AppID/AppSecret, so
phone login and release remain unverified.

`npm ci && npm test` runs view-model and template-handler tests. The `preview`
directory is an additional browser development client; Playwright evidence does
not establish native DevTools or physical WeChat compatibility.

Care jobs and memory jobs resume polling after navigation. Memory photos use
authenticated upload/download routes. Watering accepts mL and displays the
server lifecycle; a pending response never means watering has completed.

Real login, domain validation, subscription consent and native device testing
remain blocked on WeChat console configuration.
