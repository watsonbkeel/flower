const api = require('../../services/api');
const view = require('../../utils/viewmodel');
Page({
  data: {loading: true, plant: null, device: null, error: '', amount: 10, busy: false, photo: '', commandText: ''},
  onShow() { this.load(); clearInterval(this.timer); this.timer = setInterval(() => this.load(), 5000); },
  onHide() { clearInterval(this.timer); },
  onUnload() { clearInterval(this.timer); },
  async load() {
    try {
      const plants = await api.request('/plants');
      if (!plants.length) { this.setData({loading: false, plant: null}); return; }
      const app = getApp();
      const plant = plants.find(p => p.id === app.globalData.plantId) || plants[0];
      app.globalData.plantId = plant.id;
      const status = await api.request(`/plants/${plant.id}/status`);
      this.setData({...view.statusView(status), loading: false, error: ''});
      if (status.photo_id && this.photoId !== status.photo_id) {
        this.photoId = status.photo_id;
        this.setData({photo: await api.photo(status.photo_id)});
      }
    } catch (error) { this.setData({loading: false, error: error.message}); }
  },
  changeAmount(event) { this.setData({amount: Number(event.detail.value)}); },
  async water() {
    if (!this.data.canWater || this.data.busy) return;
    const amount = this.data.amount;
    wx.showModal({title: '确认补水', content: `基于标定的估算量 ${amount} mL`, success: async result => {
      if (!result.confirm) return;
      this.setData({busy: true, error: ''});
      try {
        const command = await api.request(`/plants/${this.data.plant.id}/water`, 'POST',
          {quantity: amount, unit: 'ml'}, {'Idempotency-Key': api.key()});
        this.setData({command, commandText: view.commandLabel(command.status)});
      } catch (error) { this.setData({error: error.message}); }
      finally { this.setData({busy: false}); }
    }});
  },
  async toggleAuto(event) {
    try {
      await api.request(`/plants/${this.data.plant.id}/auto-mode`, 'PUT', {enabled: event.detail.value});
      await this.load();
    } catch (error) { this.setData({error: error.message, 'plant.auto_mode': this.data.plant.auto_mode}); }
  },
  add() { wx.navigateTo({url: '/pages/add/index'}); },
  care() { wx.navigateTo({url: '/pages/plant/index'}); },
  trends() { wx.navigateTo({url: '/pages/trends/index'}); }
});
