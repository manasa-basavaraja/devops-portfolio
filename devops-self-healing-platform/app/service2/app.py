from flask import Flask
import random

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
    return {"status": "ok"}

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000)