(function (root) {
  const sourceNames = { real: '真实数据', demo: '演示数据', mock: '模拟数据', imported_test: '受控测试数据' };
  const commands = {pending: '等待领取', claimed: '准备执行', executing: '正在补水',
    succeeded: '补水完成', failed: '补水失败', expired: '领取已过期', timed_out: '执行超时', cancelled: '已取消'};
  const faults = {LOW_WATER: '水箱缺水', SAFE_HOLD: '安全保持', STARTING: '启动自检',
    TIME_UNTRUSTED: '设备时间待同步', SOIL_SENSOR_FAULT: '土壤传感器异常',
    CALIBRATION_MISSING: '尚未完成标定', PROFILE_MISSING: '养护卡待确认', PROFILE_STALE: '养护卡已过期',
    CLOUD_OFFLINE: '设备离线', BLE_STALE: '空气数据暂未更新', CAMERA_UNAVAILABLE: '相机不可用',
    LOCAL_POLICY_EXPIRED: '离线策略已过期', STORAGE_LOW: '存储空间不足', QUOTA_EXCEEDED: '今日额度不足',
    MIN_INTERVAL: '距离上次补水时间过短', ACTIVE_COMMAND: '已有补水指令', PUMP_BUSY: '设备正在工作',
    RATE_LIMITED: '操作频繁，请稍后重试', BELOW_MINIMUM_DOSE: '低于最低可控剂量',
    WECHAT_NOT_CONFIGURED: '微信登录尚未配置', PROVIDER_UNAVAILABLE: '知识服务暂不可用'};
  function commandLabel(status, action) {
    if (action === 'capture') return {pending: '等待拍照', claimed: '准备拍照', executing: '正在拍照', succeeded: '拍照完成'}[status] || commands[status] || '暂无指令';
    return commands[status] || '暂无补水指令';
  }
  function coverageLabel(series) {
    if (!series || !series.coverage_hours) return '数据积累中';
    return `${sourceNames[series.source_type] || '未知来源'} · 已积累 ${Number(series.coverage_hours).toFixed(1).replace('.0', '')} 小时`;
  }
  function canWater(device) {
    return !!(device && device.operating_mode === 'FULL' && device.activity === 'IDLE'
      && device.water_level_ok === true && device.time_trusted === true && device.calibration_valid === true
      && Number.isFinite(device.soil_moisture)
      && !(device.fault_codes || []).some(code => !['BLE_STALE', 'CAMERA_UNAVAILABLE'].includes(code)));
  }
  function faultLabel(code) { return faults[code] || code || '暂无异常'; }
  function careProfileView(profile, now = Date.now()) {
    const expiry = Date.parse(profile && profile.valid_until);
    let statusText = '养护卡待确认';
    if (!profile) statusText = '养护卡尚未生成';
    else if (!Number.isFinite(expiry)) statusText = '养护卡有效期异常，请重新生成';
    else if (expiry <= now) statusText = '养护卡已过期，请重新生成';
    else if (profile.confirmed) statusText = '养护卡已确认';
    return {statusText, canConfirm: statusText === '养护卡待确认',
      validUntilText: Number.isFinite(expiry) ? new Date(expiry).toLocaleString('zh-CN', {hour12: false}) : ''};
  }
  function weatherView(weather, expectedSource, now = Date.now()) {
    const observed = Date.parse(weather && weather.observed_at);
    const expires = Date.parse(weather && weather.valid_until);
    let statusText = '当前天气';
    if (!weather) statusText = '天气暂不可用';
    else if (!sourceNames[weather.source_type] || weather.source_type !== expectedSource) statusText = '天气来源不匹配';
    else if (!Number.isFinite(observed) || !Number.isFinite(expires) || observed > now || expires <= observed) statusText = '天气时间异常';
    else if (expires <= now) statusText = '天气已过期';
    const available = statusText === '当前天气';
    return {available, statusText,
      sourceLabel: sourceNames[weather && weather.source_type] || '暂无来源',
      temperatureText: available && Number.isFinite(weather.temperature_c) ? String(weather.temperature_c) : '--',
      rainText: available && Number.isFinite(weather.rain_next_12h_mm) ? String(weather.rain_next_12h_mm) : '--',
      observedText: Number.isFinite(observed) ? new Date(observed).toLocaleString('zh-CN', {hour12: false}) : ''};
  }
  function chartSegments(points) {
    const sorted = points.slice().sort((a, b) => Date.parse(a.occurred_at) - Date.parse(b.occurred_at));
    const segments = [];
    let previous = null;
    for (const point of sorted) {
      if (!Number.isFinite(point.soil_moisture)) { previous = null; continue; }
      if (!previous || Date.parse(point.occurred_at) - Date.parse(previous.occurred_at) > 2 * 3600000) segments.push([]);
      segments[segments.length - 1].push(point); previous = point;
    }
    return segments;
  }
  function statusView(data) {
    const device = data.device;
    return {...data, canWater: canWater(device), sourceLabel: sourceNames[device && device.source_type] || '数据积累中',
      modeLabel: {FULL: '云端守护', STARTING: '启动自检', LOCAL_CONSERVATIVE: '离线保守守护', SAFE_HOLD: '安全保持'}[device && device.operating_mode] || '等待设备',
      faultText: (device && device.fault_codes || []).map(faultLabel).join(' · '),
      commandText: commandLabel(data.command && data.command.status, data.command && data.command.action),
      soilText: device && Number.isFinite(device.soil_moisture) ? device.soil_moisture.toFixed(0) : '--'};
  }
  const api = {sourceNames, commandLabel, coverageLabel, canWater, faultLabel, careProfileView, weatherView, chartSegments, statusView};
  if (typeof module !== 'undefined') module.exports = api;
  else root.FlowerView = api;
})(typeof globalThis !== 'undefined' ? globalThis : this);
