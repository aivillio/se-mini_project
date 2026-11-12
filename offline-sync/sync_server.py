from flask import Flask, request, jsonify

app = Flask(__name__)

received_records = []


@app.route("/health", methods=["GET"])
def health():
    return jsonify({"status": "UP"}), 200


@app.route("/sync", methods=["POST"])
def sync():
    records = request.get_json()

    if not isinstance(records, list):
        return jsonify({"error": "Expected a list of records"}), 400

    received_records.extend(records)

    return jsonify({
        "message": "Records received successfully",
        "count": len(records)
    }), 200


if __name__ == "__main__":
    app.run(port=5000, debug=False)
    