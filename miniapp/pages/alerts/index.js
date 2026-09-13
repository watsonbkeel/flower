const api = require('../../services/api');
Page({data: {items: [], error: ''},
  async onShow() { try { this.setData({items: await api.request('/alerts'), error: ''}); } catch (error) { this.setData({error: error.message}); } },
  async read(event) { try { await api.request(`/alerts/${event.currentTarget.dataset.id}/read`, 'PUT'); await this.onShow(); } catch (error) { this.setData({error: error.message}); } }
});
