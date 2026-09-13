# Flower Mini Program

Specification: v2.2.2. Seven native pages use the authenticated Flower API.

Import this directory into WeChat DevTools. Replace the placeholder AppID in
`project.config.json`, configure the HTTPS API domain, and set `config.js`
`mockLogin: false` for real WeChat login. Never place AppSecret in this directory.
Local Mock testing uses the development backend and a loopback/tunneled URL.

`npm ci && npm test` runs view-model and template-handler tests. The `preview`
directory is an additional browser development client; Playwright evidence does
not establish native DevTools or physical WeChat compatibility.

Care jobs and memory jobs resume polling after navigation. Memory photos use
authenticated upload/download routes. Watering accepts mL and displays the
server lifecycle; a pending response never means watering has completed.

Real login, domain validation, subscription consent and native device testing
remain blocked on WeChat console configuration.
