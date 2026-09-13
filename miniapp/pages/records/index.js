const api = require('../../services/api');
const view = require('../../utils/viewmodel');
Page({data: {items: [], error: ''},
  async onShow() {
    const pid = getApp().globalData.plantId;
    if (!pid) return;
    try { this.setData({items: (await api.request(`/plants/${pid}/events`)).map(item => ({...item, label: view.sourceNames[item.source_type], time: item.occurred_at.replace('T', ' ').slice(0, 19)})), error: ''}); }
    catch (error) { this.setData({error: error.message}); }
  }
});
