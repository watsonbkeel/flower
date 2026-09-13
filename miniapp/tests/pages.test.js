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

test('native care page exposes weather freshness and source independently of knowledge', async () => {
  let page;
  const weather = {temperature_c: 0, rain_next_12h_mm: 0, source_type: 'mock',
    observed_at: new Date(Date.now() - 60000).toISOString(), valid_until: new Date(Date.now() + 60000).toISOString()};
  const api = {request: async path => path.endsWith('/status') ? {
    plant: {id: 'plant-1'}, device: {source_type: 'mock'},
    care_profile: {profile: {source_type: 'real', weather}}
  } : {result: null}};
  vm.runInNewContext(fs.readFileSync('pages/plant/index.js', 'utf8'), {
    require: path => path.includes('viewmodel') ? require('../utils/viewmodel') : api,
    Page: value => { page = value; }, getApp: () => ({globalData: {plantId: 'plant-1'}}),
    wx: {getStorageSync: () => null}
  });
  page.setData = values => Object.assign(page.data, values);
  await page.load();
  assert.equal(page.data.weather.temperatureText, '0');
  assert.equal(page.data.weather.sourceLabel, '模拟数据');
  weather.valid_until = new Date(Date.now() - 1).toISOString();
  await page.load();
  assert.equal(page.data.weather.available, false);
  assert.equal(page.data.weather.rainText, '--');
});

test('new care and memory actions use distinct request keys', async () => {
  for (const name of ['plant', 'memories']) {
    let page, sequence = 0;
    const calls = [];
    const api = {key: () => `request-${++sequence}`, request: async (...args) => {
      calls.push(args); return {job_id: 'job-1'};
    }};
    vm.runInNewContext(fs.readFileSync(`pages/${name}/index.js`, 'utf8'), {
      require: () => api, Page: value => { page = value; }, wx: {setStorageSync: () => {}}
    });
    page.setData = values => Object.assign(page.data, values);
    page.action = fn => fn();
    page.resumeJob = () => {};
    page.data.plant = {id: 'plant-1'};
    for (let i = 0; i < 2; i++) {
      if (name === 'plant') page.generate();
      else await page.structure({currentTarget: {dataset: {id: 'memory-1'}}});
    }
    assert.equal(calls[0][3]['Idempotency-Key'], 'request-1');
    assert.equal(calls[1][3]['Idempotency-Key'], 'request-2');
  }
});
