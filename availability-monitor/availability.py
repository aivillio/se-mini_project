from flask import Flask, jsonify
from datetime import datetime

app = Flask(__name__)


@app.route("/health")
def health_check():
    return jsonify({
        "status": "UP",
        "message": "Vehicle Parking System is running",
        "timestamp": datetime.now().isoformat()
    }), 200


if __name__ == "__main__":
    app.run(debug=True)