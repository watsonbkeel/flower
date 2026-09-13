const test = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const vm = require('node:vm');

function fixture() {
  let page, pending;
  const candidate = {common_name: 'Candidate', scientific_name: 'Candidate species', confidence: 0.9};
  const input = {recognition: {image_id: 'image-1', result: {candidates: [candidate]}, default_selection: 0}, calls: []};
  const api = {request: async (path, method, data) => {
    if (method === 'POST') { input.calls.push(data); return {}; }
    if (path.endsWith('/status')) return {plant: {id: 'plant-1'}, care_profile: null, device: {source_type: 'mock'}};
    return input.recognition;
  }};
  vm.runInNewContext(fs.readFileSync('pages/plant/index.js', 'utf8'), {
    require: path => path.includes('viewmodel') ? require('../utils/viewmodel') : api,
    Page: value => { page = value; }, getApp: () => ({globalData: {plantId: 'plant-1'}}),
    wx: {getStorageSync: () => null}
  });
  page.setData = values => Object.assign(page.data, values);
  page.action = fn => { pending = fn(); };
  return {page, input, submitted: () => pending};
}

test('new low-confidence image clears previous candidate selection', async () => {
  const {page, input} = fixture();
  await page.load();
  assert.equal(page.data.selected, 0);
  page.choose({detail: {value: '0'}});
  input.recognition = {image_id: 'image-2', result: {candidates: [{common_name: 'Uncertain', confidence: 0.4}]},
    default_selection: null, retake_recommended: true};
  await page.load();
  assert.equal(page.data.selected, -1);
  assert.equal(page.data.retakeRecommended, true);
});

test('the last explicit manual edit or candidate choice determines submitted species', async () => {
  const {page, input, submitted} = fixture();
  await page.load();
  page.field({currentTarget: {dataset: {field: 'commonName'}}, detail: {value: 'Manual'}});
  page.field({currentTarget: {dataset: {field: 'scientificName'}}, detail: {value: 'Manual species'}});
  assert.equal(page.data.selected, -1);
  await page.load();
  assert.equal(page.data.selected, -1);
  page.choose({detail: {value: '0'}});
  page.confirmSpecies(); await submitted();
  assert.equal(input.calls[0].scientific_name, 'Candidate species');
  assert.equal(input.calls[0].input_method, 'recognition');
  page.field({currentTarget: {dataset: {field: 'scientificName'}}, detail: {value: 'New manual species'}});
  page.confirmSpecies(); await submitted();
  assert.equal(input.calls[1].scientific_name, 'New manual species');
  assert.equal(input.calls[1].input_method, 'manual');
});

test('capture and recognition progress replace old candidates without changing manual input', async () => {
  const {page, input} = fixture();
  await page.load();
  page.field({currentTarget: {dataset: {field: 'scientificName'}}, detail: {value: 'Manual species'}});
  for (const [status, label] of [['capture_pending', '等待拍照'], ['capture_executing', '正在拍照'],
    ['queued', '等待识别'], ['running', '正在识别'], ['failed', '识别失败']]) {
    input.recognition = {status, image_id: 'new-image', result: null};
    await page.load();
    assert.match(page.data.recognitionText, new RegExp(label));
    assert.equal(page.data.selected, -1);
    assert.equal(page.data.candidates.length, 0);
    assert.equal(page.data.scientificName, 'Manual species');
  }
});
