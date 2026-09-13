const api = require('../../services/api');
const view = require('../../utils/viewmodel');
Page({data: {range: '7d', source: 'real', label: '数据积累中', error: '', points: [], events: []},
  onShow() { this.load(); },
  async load() {
    const pid = getApp().globalData.plantId;
    if (!pid) return;
    try {
      const series = await api.request(`/plants/${pid}/telemetry/series?range=${this.data.range}&source_type=${this.data.source}`);
      this.setData({label: view.coverageLabel(series), points: series.points, events: series.watering_events, error: ''});
      this.draw(series);
    } catch (error) { this.setData({error: error.message}); }
  },
  range(event) { this.setData({range: event.currentTarget.dataset.value}); this.load(); },
  source(event) { this.setData({source: event.detail.value ? 'mock' : 'real'}); this.load(); },
  draw(series) {
    const query = wx.createSelectorQuery().in(this);
    query.select('#trend').fields({node: true, size: true}).exec(result => {
      if (!result[0] || !result[0].node) return;
      const {node: canvas, width, height} = result[0];
      const dpr = wx.getWindowInfo().pixelRatio;
      canvas.width = width * dpr; canvas.height = height * dpr;
      const ctx = canvas.getContext('2d'); ctx.scale(dpr, dpr); ctx.clearRect(0, 0, width, height);
      const points = series.points;
      if (!points.length) return;
      const start = Date.parse(points[0].occurred_at), end = Date.parse(points[points.length - 1].occurred_at);
      ctx.strokeStyle = '#246b4b'; ctx.lineWidth = 2;
      view.chartSegments(points).forEach(segment => {
        ctx.beginPath(); segment.forEach((p, index) => { const x = 12 + (width - 24) * (Date.parse(p.occurred_at) - start) / Math.max(end - start, 1), y = height - 16 - p.soil_moisture / 100 * (height - 32); if (!index) ctx.moveTo(x, y); else ctx.lineTo(x, y); ctx.fillStyle = '#246b4b'; ctx.fillRect(x - 2, y - 2, 4, 4); }); ctx.stroke();
      });
    });
  }
});
