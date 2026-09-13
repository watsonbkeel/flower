const {chromium, expect} = require('@playwright/test');
const assert = require('node:assert/strict');
const fs = require('node:fs');

(async () => {
  const browser = await chromium.launch({headless: true});
  const report = [];
  try {
    for (const viewport of [{width: 1440, height: 1000}, {width: 390, height: 844}]) {
      const page = await browser.newPage({viewport});
      const errors = [], submissions = [];
      page.on('pageerror', error => errors.push(error.message));
      let low = false;
      await page.route('**/api/v1/plants/*/recognition', route => route.fulfill({json: {
        image_id: low ? 'image-2' : 'image-1',
        result: {candidates: [{common_name: 'Mock plant', scientific_name: 'Mock species', confidence: low ? 0.4 : 0.9}]},
        default_selection: low ? null : 0, retake_recommended: low
      }}));
      await page.route('**/api/v1/plants/*/confirm-species', route => {
        submissions.push(route.request().postDataJSON());
        return route.fulfill({json: {}});
      });
      await page.goto('http://127.0.0.1:18082/preview/#care');
      const radio = page.locator('[name="candidate"]');
      const common = page.locator('[name="common_name"]');
      const scientific = page.locator('[name="scientific_name"]');
      const submit = page.getByRole('button', {name: '确认品种', exact: true});
      await expect(radio).toBeChecked();
      await common.fill('Manual plant');
      await scientific.fill('Manual species');
      await expect(radio).not.toBeChecked();
      await submit.click();
      await expect.poll(() => submissions.length).toBe(1);
      assert.equal(submissions[0].input_method, 'manual');
      assert.equal(submissions[0].scientific_name, 'Manual species');
      assert.equal(submissions[0].image_id, 'image-1');
      await expect(radio).toBeChecked();
      await scientific.fill('Another manual species');
      await radio.check();
      await submit.click();
      await expect.poll(() => submissions.length).toBe(2);
      assert.equal(submissions[1].input_method, 'recognition');
      assert.equal(submissions[1].scientific_name, 'Mock species');
      assert.equal(submissions[1].image_id, 'image-1');
      low = true;
      await page.reload();
      await expect(page.locator('#species-form .notice')).toContainText('识别置信度较低');
      await expect(radio).not.toBeChecked();
      assert(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth));
      await page.screenshot({path: `../evidence/stage8-recognition-${viewport.width}.png`, fullPage: true});
      assert.deepEqual(errors, []);
      report.push({viewport, manual_selection: 'PASS', candidate_selection: 'PASS',
        low_confidence: 'PASS', overflow: 'PASS', errors});
      await page.close();
    }
  } finally { await browser.close(); }
  fs.writeFileSync('../evidence/stage8-recognition-browser.json', JSON.stringify({source_type: 'mock', report}, null, 2));
})().catch(error => { console.error(error); process.exitCode = 1; });
