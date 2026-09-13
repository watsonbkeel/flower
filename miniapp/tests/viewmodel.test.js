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

test('weather preserves zero readings and distinguishes absent, stale and mismatched data', () => {
  const now = Date.parse('2026-09-13T08:00:00Z');
  const weather = {temperature_c: 0, rain_next_12h_mm: 0, source_type: 'mock',
    observed_at: '2026-09-13T07:00:00Z', valid_until: '2026-09-13T09:00:00Z'};
  const current = view.weatherView(weather, 'mock', now);
  assert.equal(current.available, true);
  assert.equal(current.temperatureText, '0');
  assert.equal(current.rainText, '0');
  assert.equal(current.sourceLabel, '模拟数据');
  for (const value of [null, {...weather, valid_until: '2026-09-13T08:00:00Z'},
    {...weather, observed_at: '2026-09-13T08:01:00Z'}, {...weather, source_type: 'real'},
    {...weather, valid_until: 'bad'}]) {
    const result = view.weatherView(value, 'mock', now);
    assert.equal(result.available, false);
    assert.equal(result.rainText, '--');
    assert.equal(result.temperatureText, '--');
  }
  assert.equal(view.weatherView({...weather, temperature_c: null}, 'mock', now).temperatureText, '--');
});
