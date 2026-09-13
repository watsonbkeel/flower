const {chromium, expect} = require('@playwright/test');
const assert = require('node:assert/strict');
const fs = require('node:fs');

(async () => {
  const browser = await chromium.launch({headless: true});
  const report = [];
  try {
    for (const viewport of [{width: 1440, height: 1000}, {width: 390, height: 844}]) {
      const page = await browser.newPage({viewport});
      const errors = [];
      page.on('pageerror', error => errors.push(error.message));
      let expiry = new Date(Date.now() + 3600000).toISOString(), confirmed = false;
      await page.route('**/api/v1/plants/*/status', async route => {
        const response = await route.fetch(), body = await response.json();
        body.care_profile.valid_until = expiry;
        body.care_profile.confirmed = confirmed;
        await route.fulfill({response, json: body});
      });
      await page.goto('http://127.0.0.1:18082/preview/#care');
      const panel = page.locator('#care-validity');
      const button = page.locator('[data-action="confirm-care"]');
      await expect(panel).toContainText('养护卡待确认');
      await expect(button).toBeEnabled();
      confirmed = true;
      await expect(panel).toContainText('养护卡已确认', {timeout: 8000});
      await expect(button).toBeDisabled();
      const input = page.locator('[name="scientific_name"]');
      await input.fill('Manual input remains');
      expiry = new Date(Date.now() - 1000).toISOString();
      await expect(panel).toContainText('养护卡已过期，请重新生成', {timeout: 8000});
      await expect(panel).not.toContainText('养护卡已确认');
      await expect(button).toBeDisabled();
      await expect(page.locator('[data-action="research"]')).toBeEnabled();
      await expect(input).toHaveValue('Manual input remains');
      assert(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth));
      await page.screenshot({path: `../evidence/stage8-care-validity-${viewport.width}.png`, fullPage: true});
      expiry = 'bad';
      await expect(panel).toContainText('养护卡有效期异常，请重新生成', {timeout: 8000});
      await expect(button).toBeDisabled();
      assert.deepEqual(errors, []);
      report.push({viewport, pending: 'PASS', confirmed: 'PASS', expired: 'PASS', invalid: 'PASS',
        form_preserved: 'PASS', overflow: 'PASS', errors});
      await page.close();
    }
    const page = await browser.newPage({viewport: {width: 390, height: 844}});
    await page.goto('http://127.0.0.1:18082/preview/#care');
    await page.locator('[data-action="research"]').click();
    await expect(page.locator('[data-action="confirm-care"]')).toBeEnabled({timeout: 20000});
    await page.locator('[data-action="confirm-care"]').click();
    await expect(page.locator('#care-validity')).toContainText('养护卡已确认');
    await expect(page.locator('[data-action="confirm-care"]')).toBeDisabled();
    await expect(page.locator('#error')).toBeHidden();
    report.push({live_mock_research_and_confirmation: 'PASS'});
    await page.close();
  } finally { await browser.close(); }
  fs.writeFileSync('../evidence/stage8-care-validity-browser.json', JSON.stringify({source_type: 'mock', report}, null, 2));
})().catch(error => { console.error(error); process.exitCode = 1; });
