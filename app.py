# app.py
from flask import Flask, request, jsonify, render_template
from flask_sqlalchemy import SQLAlchemy
import requests, datetime, os
import config

app = Flask(__name__, template_folder="templates", static_folder="static")
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///locations.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
db = SQLAlchemy(app)

class Location(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    device_id = db.Column(db.String(200), index=True)
    lat = db.Column(db.Float)
    lng = db.Column(db.Float)
    accuracy = db.Column(db.Float)
    source = db.Column(db.String(50))  # "browser" or "cell"
    timestamp = db.Column(db.DateTime, default=datetime.datetime.utcnow)

db.create_all()

@app.route("/")
def index():
    return render_template("index.html")

@app.route("/update_location", methods=["POST"])
def update_location():
    data = request.json or {}
    device_id = data.get("device_id") or data.get("deviceId") or "anonymous"
    # If GPS coords provided by browser/client
    if "lat" in data and "lng" in data:
        lat = float(data["lat"])
        lng = float(data["lng"])
        accuracy = float(data.get("accuracy", 0))
        src = "browser"
    # If cell tower info provided, use Google Geolocation
    elif data.get("tower"):
        tower = data["tower"]
        payload = {"cellTowers": [{
            "cellId": tower.get("cid"),
            "locationAreaCode": tower.get("lac"),
            "mobileCountryCode": tower.get("mcc"),
            "mobileNetworkCode": tower.get("mnc"),
            "signalStrength": tower.get("signal", None)
        }]}
        google_url = f"https://www.googleapis.com/geolocation/v1/geolocate?key={config.GOOGLE_API_KEY}"
        resp = requests.post(google_url, json=payload, timeout=10)
        if resp.status_code != 200:
            return jsonify({"status":"error","message":"Geolocation API error","details":resp.text}), 502
        result = resp.json()
        lat = result["location"]["lat"]
        lng = result["location"]["lng"]
        accuracy = result.get("accuracy", None)
        src = "cell"
    else:
        return jsonify({"status":"error","message":"No valid location or tower payload provided"}), 400

    loc = Location(device_id=device_id, lat=lat, lng=lng, accuracy=accuracy, source=src)
    db.session.add(loc)
    db.session.commit()

    return jsonify({"status":"success","device_id":device_id,"lat":lat,"lng":lng,"accuracy":accuracy,"source":src})

@app.route("/get_location/<device_id>", methods=["GET"])
def get_location(device_id):
    loc = Location.query.filter_by(device_id=device_id).order_by(Location.id.desc()).first()
    if not loc:
        return jsonify({"error":"Device not found"}), 404
    return jsonify({
        "device_id": loc.device_id,
        "lat": loc.lat,
        "lng": loc.lng,
        "accuracy": loc.accuracy,
        "source": loc.source,
        "timestamp": loc.timestamp.isoformat()
    })

# optional: endpoint to list all devices (for dashboard)
@app.route("/devices", methods=["GET"])
def devices():
    results = db.session.query(Location.device_id, db.func.max(Location.timestamp)).group_by(Location.device_id).all()
    devices = [row[0] for row in results]
    return jsonify({"devices": devices})

if __name__ == "__main__":
    app.run(debug=True, host="0.0.0.0", port=int(os.environ.get("PORT",5000)))
