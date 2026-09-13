const view = require('../utils/viewmodel');
let loginPromise;
function login() {
  if (loginPromise) return loginPromise;
  const app = getApp();
  loginPromise = new Promise((resolve, reject) => {
    function exchange(code) {
      wx.request({url: app.globalData.config.baseUrl + '/api/v1/auth/wechat-login', method: 'POST', data: {code},
        success(response) {
          if (response.statusCode !== 200) { reject(new Error(view.faultLabel(response.data.error && response.data.error.code))); return; }
          app.globalData.token = response.data.access_token; resolve();
        }, fail: reject});
    }
    if (app.globalData.config.mockLogin) exchange(app.globalData.config.mockCode);
    else wx.login({success: result => exchange(result.code), fail: reject});
  }).finally(() => { loginPromise = null; });
  return loginPromise;
}
async function request(path, method = 'GET', data, headers = {}, retry = true) {
  const app = getApp();
  if (!app.globalData.token) await login();
  return new Promise((resolve, reject) => wx.request({url: app.globalData.config.baseUrl + '/api/v1' + path,
    method, data, timeout: 15000, header: {Authorization: 'Bearer ' + app.globalData.token, ...headers},
    async success(response) {
      if (response.statusCode === 401 && retry) {
        app.globalData.token = '';
        try { resolve(await request(path, method, data, headers, false)); } catch (error) { reject(error); }
      } else if (response.statusCode >= 200 && response.statusCode < 300) resolve(response.data);
      else reject(new Error(view.faultLabel(response.data.error && response.data.error.code)));
    }, fail: () => reject(new Error('连接暂不可用'))}));
}
function key() { return Date.now().toString(36) + '-' + Math.random().toString(36).slice(2); }
function photo(imageId) {
  const app = getApp();
  return new Promise((resolve, reject) => wx.downloadFile({url: app.globalData.config.baseUrl + '/api/v1/images/' + imageId,
    header: {Authorization: 'Bearer ' + app.globalData.token},
    success: response => response.statusCode === 200 ? resolve(response.tempFilePath) : reject(new Error('图片不可用')), fail: reject}));
}
async function upload(filePath, plantId) {
  const app = getApp();
  if (!app.globalData.token) await login();
  return new Promise((resolve, reject) => wx.uploadFile({url: app.globalData.config.baseUrl + '/api/v1/images', filePath, name: 'file', formData: {plant_id: plantId}, header: {Authorization: 'Bearer ' + app.globalData.token}, success: response => { try { const result = JSON.parse(response.data); if (response.statusCode !== 201) throw Error(view.faultLabel(result.error && result.error.code)); resolve(result); } catch(error) { reject(error); } }, fail: reject}));
}
module.exports = {request, login, key, photo, upload};
