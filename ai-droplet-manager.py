import os
import logging
import requests
from flask import Flask, render_template_string, redirect, jsonify

logging.basicConfig(
    filename="/var/log/ai-manager.log",
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s"
)

DIGITALOCEAN_TOKEN = os.getenv("DO_API_TOKEN")
if not DIGITALOCEAN_TOKEN:
    raise RuntimeError("DO_API_TOKEN environment variable is not set")

HEADERS = {"Authorization": f"Bearer {DIGITALOCEAN_TOKEN}" }
DROPLET_NAME = "ai-instance"
SNAPSHOT_ID = "192399134"
REGION = "tor1"
SIZE = "gpu-6000adax1-48gb"
SSH_KEY_IDS = [48954231]

app = Flask(__name__, static_url_path="/ai/static")
app.config["APPLICATION_ROOT"] = "/ai"

def get_droplet():
    try:
        response = requests.get("https://api.digitalocean.com/v2/droplets", headers=HEADERS)
        droplets = response.json().get("droplets", [])
        for droplet in droplets:
            if droplet["name"] == DROPLET_NAME:
                return droplet
    except Exception as e:
        logging.error(f"Ошибка при проверке дроплета: {e}")
    return None

def create_droplet():
    if get_droplet():
        logging.info("Дроплет уже запущен, повторный запуск не требуется.")
        return True
    logging.info("Запрос на создание дроплета: имя={DROPLET_NAME}, регион={REGION}, размер={SIZE}, снапшот={SNAPSHOT_ID}")
    data = {
        "name": DROPLET_NAME,
        "region": REGION,
        "size": SIZE,
        "image": SNAPSHOT_ID,
        "ssh_keys": SSH_KEY_IDS,
        "backups": False,
        "ipv6": False,
        "monitoring": True,
        "tags": ["gpu"],
    }
    try:
        r = requests.post("https://api.digitalocean.com/v2/droplets", json=data, headers=HEADERS)
        logging.info("Ответ от API при создании: %s - %s", r.status_code, r.text)
        return r.status_code == 202
    except Exception as e:
        logging.error(f"Ошибка при создании дроплета: {e}")
        return False

def destroy_droplet(droplet_id):
    logging.info("Запрос на удаление дроплета ID={droplet_id}")
    try:
        r = requests.delete(f"https://api.digitalocean.com/v2/droplets/{droplet_id}", headers=HEADERS)
        logging.info("Ответ от API при удалении: %s", r.status_code)
        return r.status_code == 204
    except Exception as e:
        logging.error(f"Ошибка при удалении дроплета: {e}")
        return False

@app.route("/ai/")
def index():
    droplet = get_droplet()
    status = droplet["status"] if droplet else "off"
    return render_template_string("""<html>
<head>
    <title>GPU Droplet Manager</title>
    <script src="https://code.jquery.com/jquery-3.6.0.min.js"></script>
    <style>
        body { font-family: sans-serif; text-align: center; padding: 30px; }
        h2 { font-size: 24px; margin-bottom: 20px; }
        button { padding: 12px 24px; font-size: 16px; margin: 10px; cursor: pointer; }
        #status { font-weight: bold; }
        .link-row { margin-top: 20px; }
    </style>
    <script>
        function updateStatus() {
            $.get("/ai/status", function(data) {
                let color = (data.status === "off") ? "red" : "green";
                $("#status").text(data.status).css("color", color);
                if (data.status === "off") {
                    $("#start-form").show();
                    $("#stop-form").hide();
                    $("#links").hide();
                } else {
                    $("#start-form").hide();
                    $("#stop-form").show();
                    $("#links").show();
                }
            });
        }
        $(document).ready(function() {
            updateStatus();
            setInterval(updateStatus, 5000);
        });
    </script>
</head>
<body>
    <h2>🧠 GPU Droplet Status: <span id="status">...</span></h2>
    <div id="start-form" style="display:none;">
        <form action="/ai/start" method="post">
            <button type="submit">🚀 Запустить</button>
        </form>
    </div>
    <div id="stop-form" style="display:none;">
        <form action="/ai/stop" method="post">
            <button type="submit">⛔ Остановить</button>
        </form>
    </div>
    <div id="links" class="link-row" style="display:none;">
        <a href="http://ai.key-net.ru/framepack" target="_blank" rel="noopener noreferrer">🧠 FramePack</a> |
        <a href="http://ai.key-net.ru/gpu" target="_blank" rel="noopener noreferrer">📊 Утилизация GPU</a>
    </div>
</body>
</html>
""", status=status)

@app.route("/ai/status")
def status():
    droplet = get_droplet()
    return jsonify({"status": droplet["status"] if droplet else "off"})

@app.route("/ai/start", methods=["POST"])
def start():
    create_droplet()
    return redirect("/ai/")

@app.route("/ai/stop", methods=["POST"])
def stop():
    droplet = get_droplet()
    if droplet:
        destroy_droplet(droplet["id"])
    return redirect("/ai/")

if __name__ == "__main__":
    import logging
    log = logging.getLogger('werkzeug')
    log.setLevel(logging.ERROR)
    app.run(host="0.0.0.0", port=7860)
