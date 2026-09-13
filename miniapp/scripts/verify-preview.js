const {chromium} = require('@playwright/test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
(async () => {
  const browser = await chromium.launch({headless: true});
  const report = [];
  for (const viewport of [{width: 1440, height: 1000}, {width: 390, height: 844}]) {
    const page = await browser.newPage({viewport});
    const errors = [];
    page.on('pageerror', error => errors.push(error.message));
    await page.goto('http://127.0.0.1:18082/preview/');
    await page.locator('.plant-photo').waitFor();
    assert(await page.locator('.plant-photo').evaluate(image => image.complete && image.naturalWidth > 100));
    await page.screenshot({path: `../evidence/stage5-home-${viewport.width}.png`, fullPage: true});
    for (const route of ['care', 'trends', 'records', 'memories', 'alerts']) {
      await page.locator(`nav a[data-tab="${route}"]`).click();
      await page.waitForTimeout(600);
      assert(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth), route + ' overflow');
      assert(await page.locator('#error').isHidden(), route + ' API error');
      if (route === 'trends') {
        assert(await page.locator('canvas').evaluate(c => { const pixels = c.getContext('2d').getImageData(0,0,c.width,c.height).data; return pixels.some((v,i) => i % 4 === 3 && v > 0); }));
        await page.screenshot({path: `../evidence/stage5-trends-${viewport.width}.png`, fullPage: true});
      }
    }
    assert.deepEqual(errors, []);
    report.push({viewport, routes: 6, images: 'PASS', canvas: 'PASS', overflow: 'PASS', errors});
    await page.close();
  }
  await browser.close();
  fs.writeFileSync('../evidence/stage5-browser.json', JSON.stringify({source_type: 'mock', report}, null, 2));
})().catch(error => { console.error(error); process.exit(1); });
