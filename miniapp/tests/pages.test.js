const test = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const vm = require('node:vm');
test('every native template handler exists', () => {
  for (const name of fs.readdirSync('pages')) {
    let page;
    vm.runInNewContext(fs.readFileSync(`pages/${name}/index.js`, 'utf8'), {
      require: () => ({}), Page: value => { page = value; }
    });
    const template = fs.readFileSync(`pages/${name}/index.wxml`, 'utf8');
    for (const match of template.matchAll(/bind\w+="(\w+)"/g)) assert.equal(typeof page[match[1]], 'function', `${name}: ${match[1]}`);
  }
});
test('memory job errors are handled and polling resumes on show', async () => {
  let page, callback;
  const data = {'memory-job': 'job-1'};
  vm.runInNewContext(fs.readFileSync('pages/memories/index.js', 'utf8'), {
    require: () => ({request: async path => { if (path.startsWith('/jobs/')) throw Error('offline'); return []; }}),
    Page: value => { page = value; }, wx: {getStorageSync: k => data[k]},
    setInterval: fn => { callback = fn; return 1; }, clearInterval: () => {}
  });
  page.setData = values => Object.assign(page.data, values);
  await page.onShow();
  assert.equal(typeof callback, 'function');
  await callback();
  assert.equal(page.data.error, 'offline');
});
