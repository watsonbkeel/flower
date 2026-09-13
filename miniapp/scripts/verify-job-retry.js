const {chromium, expect} = require('@playwright/test');
const assert = require('node:assert/strict');
const fs = require('node:fs');

(async () => {
  const browser = await chromium.launch({headless: true});
  const keys = [];
  try {
    const page = await browser.newPage({viewport: {width: 390, height: 844}});
    await page.route('**/api/v1/plants/*/care-profile/generate', async route => {
      keys.push(route.request().headers()['idempotency-key']);
      await route.fulfill({status: 202, json: {job_id: `retry-fixture-${keys.length}`}});
    });
    await page.route('**/api/v1/jobs/retry-fixture-*', async route => {
      const failed = route.request().url().endsWith('retry-fixture-1');
      await route.fulfill({json: {status: failed ? 'failed' : 'succeeded'}});
    });
    await page.goto('http://127.0.0.1:18082/preview/#care');
    const button = page.locator('[data-action="research"]');
    await button.click();
    await expect(page.locator('#error')).toContainText('处理失败', {timeout: 8000});
    await expect(button).toBeEnabled();
    await button.click();
    await expect(button).toBeEnabled({timeout: 8000});
    await expect(page.locator('#error')).toBeHidden();
    assert.equal(keys.length, 2);
    assert(keys.every(value => typeof value === 'string' && value.length > 0));
    assert.notEqual(keys[0], keys[1]);
    fs.writeFileSync('../evidence/stage8-job-retry-browser.json', JSON.stringify({
      source_type: 'mock', job_responses: 'intercepted fixtures; no provider calls',
      failed_action_enabled: 'PASS', second_action_succeeded: 'PASS', distinct_request_keys: 'PASS'
    }, null, 2));
  } finally {
    await browser.close();
  }
})().catch(error => { console.error(error); process.exitCode = 1; });
