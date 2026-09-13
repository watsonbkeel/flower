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
      const candidate = {common_name: 'Mock plant', scientific_name: 'Mock species', confidence: 0.9};
      let value = {image_id: 'old', status: 'succeeded', result: {candidates: [candidate]}, default_selection: 0};
      await page.route('**/api/v1/plants/*/recognition', route => route.fulfill({json: value}));
      await page.route('**/api/v1/plants/*/capture', route => {
        value = {capture_id: 'retake', image_id: null, status: 'capture_pending', result: null};
        return route.fulfill({status: 202, json: {id: 'retake', status: 'pending'}});
      });
      await page.goto('http://127.0.0.1:18082/preview/#care');
      const radio = page.locator('[name="candidate"]');
      await expect(radio).toBeChecked();
      await page.locator('[data-action="capture"]').click();
      const status = page.locator('#recognition-status');
      await expect(status).toHaveText('等待拍照');
      await expect(radio).toHaveCount(0);
      value = {...value, status: 'running', image_id: 'new'};
      await expect(status).toHaveText('正在识别', {timeout: 8000});
      const manual = page.locator('[name="scientific_name"]');
      await manual.fill('Explicit manual choice');
      value = {...value, status: 'succeeded', result: {candidates: [candidate]}, default_selection: 0};
      await expect(status).toHaveText('识别完成，请确认品种', {timeout: 8000});
      await expect(radio).not.toBeChecked();
      await expect(manual).toHaveValue('Explicit manual choice');
      await radio.check();
      await page.waitForTimeout(5500);
      await expect(radio).toBeChecked();
      value = {capture_id: 'next', image_id: null, status: 'capture_failed', result: null};
      await expect(status).toHaveText('拍照失败', {timeout: 8000});
      await expect(radio).toHaveCount(0);
      await expect(status).not.toContainText('补水');
      assert(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth));
      assert.deepEqual(errors, []);
      await page.screenshot({path: `../evidence/stage8-recognition-lifecycle-${viewport.width}.png`, fullPage: true});
      report.push({viewport, old_result_cleared: 'PASS', automatic_result_refresh: 'PASS',
        explicit_choice_preserved: 'PASS', camera_failure: 'PASS', overflow: 'PASS', errors});
      await page.close();
    }
    const page = await browser.newPage({viewport: {width: 390, height: 844}});
    await page.goto('http://127.0.0.1:18082/preview/#care');
    await page.locator('[data-action="capture"]').click();
    await expect(page.locator('#recognition-status')).toHaveText('识别完成，请确认品种', {timeout: 20000});
    await expect(page.locator('[name="candidate"]')).toHaveCount(3);
    await expect(page.locator('#error')).toBeHidden();
    report.push({live_mock_camera_worker_recognition: 'PASS'});
    await page.close();
  } finally { await browser.close(); }
  fs.writeFileSync('../evidence/stage8-recognition-lifecycle-browser.json', JSON.stringify({source_type: 'mock', report}, null, 2));
})().catch(error => { console.error(error); process.exitCode = 1; });
