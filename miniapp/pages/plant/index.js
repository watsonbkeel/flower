const api = require('../../services/api');
const view = require('../../utils/viewmodel');
Page({data: {plant: {}, profile: null, candidates: [], selected: -1, retakeRecommended: false, commonName: '', scientificName: '', jobText: '', error: '', busy: false},
  onShow() { this.load(); clearInterval(this.timer); this.timer = setInterval(() => this.load(), 2000); },
  onHide() { clearInterval(this.timer); }, onUnload() { clearInterval(this.timer); },
  async load() {
    const pid = getApp().globalData.plantId;
    if (!pid) return;
    try {
      const status = await api.request(`/plants/${pid}/status`);
      const recognition = await api.request(`/plants/${pid}/recognition`);
      this.setData({plant: status.plant, profile: status.care_profile,
        careValidity: view.careProfileView(status.care_profile),
        weather: view.weatherView(status.care_profile && status.care_profile.profile.weather, status.device && status.device.source_type),
        candidates: recognition.result ? recognition.result.candidates : [], retakeRecommended: !!recognition.retake_recommended,
        recognitionText: view.recognitionLabel(recognition.status)});
      if (this.recognitionImageId !== recognition.image_id) {
        this.recognitionImageId = recognition.image_id;
        this.selectionTouched = false;
      }
      if (!this.selectionTouched) this.setData({selected: recognition.default_selection == null ? -1 : recognition.default_selection});
      const jobId = wx.getStorageSync('job:' + pid);
      if (jobId) {
        const job = await api.request(`/jobs/${jobId}`);
        this.setData({jobText: {queued: '等待处理', running: '正在生成养护卡', succeeded: '养护卡已生成', failed: '养护研究失败'}[job.status]});
      }
    } catch (error) { this.setData({error: error.message}); }
  },
  choose(event) { this.selectionTouched = true; this.setData({selected: Number(event.detail.value)}); },
  field(event) { this.selectionTouched = true; this.setData({[event.currentTarget.dataset.field]: event.detail.value, selected: -1}); },
  async action(fn) { this.setData({busy: true, error: ''}); try { await fn(); await this.load(); } catch (error) { this.setData({error: error.message}); } finally { this.setData({busy: false}); } },
  capture() { this.action(async () => { await api.request(`/plants/${this.data.plant.id}/capture`, 'POST', {}, {'Idempotency-Key': api.key()}); }); },
  confirmSpecies() { this.action(async () => {
    const candidate = this.data.candidates[this.data.selected];
    const manual = !candidate;
    if (manual && !this.data.scientificName.trim()) throw new Error('请选择候选或填写植物名称');
    await api.request(`/plants/${this.data.plant.id}/confirm-species`, 'POST', {
      image_id: this.recognitionImageId || null,
      common_name: manual ? this.data.commonName : candidate.common_name,
      scientific_name: manual ? this.data.scientificName : candidate.scientific_name,
      input_method: manual ? 'manual' : 'recognition', confidence: manual ? null : candidate.confidence});
  }); },
  generate() { this.action(async () => { const job = await api.request(`/plants/${this.data.plant.id}/care-profile/generate`, 'POST', {}, {'Idempotency-Key': api.key()}); wx.setStorageSync('job:' + this.data.plant.id, job.job_id); this.setData({jobText: '等待处理'}); }); },
  confirmCare() { this.action(() => api.request(`/plants/${this.data.plant.id}/care-profile/confirm`, 'POST', {profile_id: this.data.profile.id})); },
  copySource(event) { wx.setClipboardData({data: event.currentTarget.dataset.url}); }
});
