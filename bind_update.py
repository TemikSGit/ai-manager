#!/usr/bin/env python3
import os
import re
import subprocess
import requests
from datetime import datetime

# Получаем переменные окружения
ZONE_FILE = os.getenv("AI_MANAGER_ZONE_FILE", "/etc/bind/db.key-net.ru")
ZONE_NAME = os.getenv("AI_MANAGER_ZONE_NAME", "ai")
DO_API_TOKEN = os.getenv("DO_API_TOKEN")

if not DO_API_TOKEN:
    raise RuntimeError("Переменная окружения DO_API_TOKEN не установлена")

HEADERS = {"Authorization": f"Bearer {DO_API_TOKEN}"}

def get_current_ip():
    resp = requests.get("https://api.digitalocean.com/v2/droplets", headers=HEADERS)
    droplets = resp.json().get("droplets", [])
    for droplet in droplets:
        if droplet.get("name") == "ai-instance":
            return droplet.get("networks", {}).get("v4", [{}])[0].get("ip_address")
    return None

def update_zone_file(ip):
    with open(ZONE_FILE, "r") as f:
        lines = f.readlines()

    new_lines = []
    serial_updated = False
    ip_updated = False

    today = datetime.utcnow().strftime("%Y%m%d")
    serial_pattern = re.compile(r"^\s*(\d{10})\s*;\s*serial")
    ip_pattern = re.compile(rf"^\s*{re.escape(ZONE_NAME)}\s+IN\s+A\s+(\d+\.\d+\.\d+\.\d+)\s*$")

    for line in lines:
        serial_match = serial_pattern.search(line)
        if serial_match:
            old_serial = serial_match.group(1)
            base = today
            count = 0
            if old_serial.startswith(today):
                count = int(old_serial[-2:]) + 1
            new_serial = f"{base}{count:02d}"
            line = re.sub(r"\d{10}", new_serial, line)
            serial_updated = True

        ip_match = ip_pattern.match(line)
        if ip_match:
            old_ip = ip_match.group(1)
            if old_ip != ip:
                line = f"{ZONE_NAME}\tIN\tA\t{ip}\n"
                ip_updated = True

        new_lines.append(line)

    if not ip_updated:
        print("IP не изменился — обновление не требуется.")
        return

    with open(ZONE_FILE, "w") as f:
        f.writelines(new_lines)

    print("Файл зоны обновлён.")
    if serial_updated:
        print("Серийный номер обновлён.")
    subprocess.run(["systemctl", "restart", "bind9"], check=True)
    print("Сервис bind9 перезапущен.")

if __name__ == "__main__":
    ip = get_current_ip()
    if ip:
        update_zone_file(ip)
    else:
        print("Не удалось получить IP дроплета.")

