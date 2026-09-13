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
      let weather = {temperature_c: 0, rain_next_12h_mm: 0, source_type: 'mock',
        observed_at: new Date(Date.now() - 3600000).toISOString(),
        valid_until: new Date(Date.now() + 3600000).toISOString()};
      await page.route('**/api/v1/plants/*/status', async route => {
        const response = await route.fetch();
        const body = await response.json();
        body.care_profile.profile.weather = weather;
        await route.fulfill({response, json: body});
      });
      await page.goto('http://127.0.0.1:18082/preview/#care');
      const panel = page.locator('#local-weather');
      await expect(panel).toContainText('气温：0 °C');
      await expect(panel).toContainText('降雨：0 mm');
      await expect(panel).toContainText('模拟数据');
      assert(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth));
      await page.screenshot({path: `../evidence/stage8-weather-current-${viewport.width}.png`, fullPage: true});
      const input = page.locator('[name="common_name"]');
      await input.fill('待确认的名称');
      weather = {...weather, valid_until: new Date(Date.now() - 1000).toISOString()};
      await expect(panel).toContainText('天气已过期', {timeout: 8000});
      await expect(panel).not.toContainText('降雨：0 mm');
      await expect(input).toHaveValue('待确认的名称');
      await page.screenshot({path: `../evidence/stage8-weather-expired-${viewport.width}.png`, fullPage: true});
      weather = null;
      await expect(panel).toContainText('天气暂不可用', {timeout: 8000});
      await expect(panel).not.toContainText('降雨：');
      await expect(page.locator('#error')).toBeHidden();
      assert(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth));
      assert.deepEqual(errors, []);
      report.push({viewport, zero_readings: 'PASS', expired: 'PASS', missing: 'PASS',
        source_label: 'PASS', form_preserved: 'PASS', overflow: 'PASS', errors});
      await page.close();
    }
  } finally {
    await browser.close();
  }
  fs.writeFileSync('../evidence/stage8-weather-browser.json', JSON.stringify({source_type: 'mock', report}, null, 2));
})().catch(error => { console.error(error); process.exitCode = 1; });
