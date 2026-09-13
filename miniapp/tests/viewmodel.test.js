const test = require('node:test');
const assert = require('node:assert/strict');
const view = require('../utils/viewmodel');

test('pending and claimed never mean watering complete', () => {
  for (const status of ['pending', 'claimed', 'executing', 'failed', 'timed_out']) {
    assert.notEqual(view.commandLabel(status), '补水完成');
  }
  assert.equal(view.commandLabel('succeeded'), '补水完成');
});

test('data coverage and demo sources stay visible', () => {
  assert.match(view.coverageLabel({source_type: 'real', coverage_hours: 52}), /52/);
  assert.match(view.coverageLabel({source_type: 'mock', coverage_hours: 168}), /模拟/);
  assert.equal(view.coverageLabel({source_type: 'real', coverage_hours: 0}), '数据积累中');
});

test('uncertain status disables manual watering', () => {
  assert.equal(view.canWater(null), false);
  assert.equal(view.canWater({operating_mode: 'SAFE_HOLD', water_level_ok: true}), false);
  assert.equal(view.canWater({operating_mode: 'FULL', activity: 'IDLE', water_level_ok: true,
    fault_codes: [], soil_moisture: 30, time_trusted: true, calibration_valid: true}), true);
});

test('chart points retain time gaps and sources', () => {
  const values = [{occurred_at: '2026-09-01T00:00:00Z', soil_moisture: 50},
    {occurred_at: '2026-09-03T00:00:00Z', soil_moisture: 20}];
  const segments = view.chartSegments(values);
  assert.equal(segments.length, 2);
});
