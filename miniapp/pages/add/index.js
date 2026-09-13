const api = require('../../services/api');
Page({data: {devices: [], deviceIndex: 0, sizes: ['small', 'medium', 'large'], sizeLabels: ['小盆', '中盆', '大盆'], sizeIndex: 0,
  materials: ['plastic', 'terracotta', 'ceramic'], materialLabels: ['塑料', '陶土', '陶瓷'], materialIndex: 0,
  placements: ['indoor', 'outdoor', 'balcony'], placementLabels: ['室内', '室外', '阳台'], placementIndex: 0,
  name: '', city: '', timezone: 'Asia/Shanghai', drainage: true, error: '', busy: false},
  async onLoad() { try { this.setData({devices: await api.request('/devices')}); } catch (error) { this.setData({error: error.message}); } },
  field(event) { this.setData({[event.currentTarget.dataset.field]: event.detail.value}); },
  picker(event) { this.setData({[event.currentTarget.dataset.field]: Number(event.detail.value)}); },
  drainage(event) { this.setData({drainage: event.detail.value}); },
  async save() {
    if (!this.data.devices.length) { this.setData({error: '尚未绑定设备'}); return; }
    this.setData({busy: true, error: ''});
    try {
      const p = await api.request('/plants', 'POST', {device_id: this.data.devices[this.data.deviceIndex].id,
        name: this.data.name, city: this.data.city, timezone: this.data.timezone,
        placement_type: this.data.placements[this.data.placementIndex], pot_size: this.data.sizes[this.data.sizeIndex],
        pot_material: this.data.materials[this.data.materialIndex], has_drainage: this.data.drainage});
      getApp().globalData.plantId = p.id; wx.redirectTo({url: '/pages/plant/index'});
    } catch (error) { this.setData({error: error.message}); }
    finally { this.setData({busy: false}); }
  }
});
