from flask import Flask
import random
from datetime import datetime  # new import

app = Flask(__name__)

@app.route("/")
def home():
    return "Service 1 is running!"

@app.route("/cpu")
def cpu_spike():
    x = [i**2 for i in range(10000000)]
    return "CPU spike triggered!"

@app.route("/health")
def health():
    return {
        "status": "ok",
        "timestamp": datetime.utcnow().isoformat()  # new field
    }

if __name__ == "__main__":
    app.run(host="120.60.0.0", port=3000)