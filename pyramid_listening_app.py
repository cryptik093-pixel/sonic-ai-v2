"""
Standalone Pyramid listening app.

Ambient audio plus simple environmental sensor values are translated into a
phrase and melody recipe shaped around King's Chamber-inspired acoustics.
"""

from __future__ import annotations

from flask import Flask, jsonify, render_template, request

from pyramid_resonance import PyramidResonanceEngine


app = Flask(__name__)
app.config["JSON_SORT_KEYS"] = False

engine = PyramidResonanceEngine()


@app.route("/")
def index():
    return render_template("pyramid.html")


@app.route("/api/pyramid/status", methods=["GET"])
def pyramid_status():
    return jsonify(engine.status()), 200


@app.route("/api/pyramid/start", methods=["POST"])
def pyramid_start():
    try:
        return jsonify(engine.start()), 200
    except RuntimeError as exc:
        return jsonify({"error": str(exc), "status": engine.status()}), 500


@app.route("/api/pyramid/stop", methods=["POST"])
def pyramid_stop():
    return jsonify(engine.stop()), 200


@app.route("/api/pyramid/capture", methods=["POST"])
def pyramid_capture():
    data = request.get_json(silent=True) or {}
    sensors = data.get("sensors") or {}

    try:
        capture = engine.capture_resonance(sensors=sensors)
        return jsonify(capture), 200
    except RuntimeError as exc:
        return jsonify({"error": str(exc), "status": engine.status()}), 400


@app.route("/health", methods=["GET"])
def health():
    status = engine.status()
    return jsonify({"status": "healthy", "listening": status["running"]}), 200


if __name__ == "__main__":
    print(
        """
Pyramid Listening App
Listening UI: http://localhost:5050
Health:       http://localhost:5050/health
"""
    )
    app.run(debug=True, host="0.0.0.0", port=5050)
