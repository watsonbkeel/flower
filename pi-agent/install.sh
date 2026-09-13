#!/usr/bin/env bash
set -euo pipefail
[[ "$(uname -m)" == "aarch64" ]] || { echo '仅允许在已接线验收的64位树莓派运行'; exit 1; }
[[ "${1:-}" == "--physical-window" ]] || { echo '断开12V泵电源，在物理安装窗口使用 --physical-window'; exit 1; }
[[ $EUID == 0 ]] || { echo '需要root安装独立Flower服务'; exit 1; }
cd -- "$(dirname -- "$0")"
[[ "$PWD" == /opt/smart-guardian ]] || { echo '先准备独立 /opt/smart-guardian release'; exit 1; }
apt-get install -y python3-venv python3-dev i2c-tools bluez libgpiod2
raspi-config nonint do_i2c 0
id flower-pi >/dev/null 2>&1 || useradd --system --home /var/lib/smart-guardian flower-pi
usermod -a -G gpio,i2c,video,bluetooth flower-pi
install -d -o flower-pi -g flower-pi -m 700 /var/lib/smart-guardian
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt
chmod +x emergency_pump_off.sh diagnose.sh calibrate.sh ble_probe.sh
[[ -f /etc/flower-pi.env ]] || { echo '缺少独立 /etc/flower-pi.env；服务未安装启动'; exit 1; }
install -m 644 smart-guardian.service /etc/systemd/system/smart-guardian.service
systemctl daemon-reload
systemctl enable --now smart-guardian.service
./diagnose.sh
