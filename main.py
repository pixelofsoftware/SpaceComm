from fastapi import FastAPI, UploadFile, File, HTTPException, Depends, Request, Form
from fastapi.responses import FileResponse, JSONResponse, HTMLResponse
from pydantic import BaseModel
import os
from satellite_comm import SatelliteComm, BlockstreamSatelliteIntegration
from fastapi.security import HTTPBasic, HTTPBasicCredentials
import secrets
import json
import db

# Initialize FastAPI app
app = FastAPI(title="Satellite Ground Station Dashboard")

# Global satellite communication instance (for demo, single connection)
comm = SatelliteComm('127.0.0.1', 5000)

bsi = BlockstreamSatelliteIntegration(receiver_type='standalone')  # Change receiver_type as needed

# Models for API
class CommandRequest(BaseModel):
    command: str
    params: str = ''  # Optional, can be used for steer, etc.

security = HTTPBasic()
USERNAME = "admin"
PASSWORD = "space123"

def authenticate(credentials: HTTPBasicCredentials = Depends(security)):
    correct_username = secrets.compare_digest(credentials.username, USERNAME)
    correct_password = secrets.compare_digest(credentials.password, PASSWORD)
    if not (correct_username and correct_password):
        raise HTTPException(status_code=401, detail="Incorrect username or password", headers={"WWW-Authenticate": "Basic"})
    return credentials.username

@app.on_event("startup")
def startup_event():
    """Connect to satellite on startup."""
    comm.connect()

@app.on_event("shutdown")
def shutdown_event():
    """Disconnect from satellite on shutdown."""
    comm.disconnect()

@app.post("/send_command")
def send_command(req: CommandRequest):
    """Send a command to the satellite (e.g., reboot, steer)."""
    params_bytes = req.params.encode() if req.params else None
    success = comm.send_command(req.command, params_bytes)
    if not success:
        raise HTTPException(status_code=500, detail="Failed to send command.")
    return {"status": "Command sent", "command": req.command}

@app.get("/request_photo")
def request_photo():
    """Request a photo from the satellite and return as file download."""
    photo = comm.request_photo()
    if not photo:
        raise HTTPException(status_code=500, detail="Failed to receive photo.")
    photo_path = "received_photo.jpg"
    with open(photo_path, 'wb') as f:
        f.write(photo)
    return FileResponse(photo_path, media_type='image/jpeg', filename='satellite_photo.jpg')

@app.get("/status")
def status():
    """Get connection status."""
    return {"connected": comm.connected}

@app.get("/telemetry", dependencies=[Depends(authenticate)])
def get_telemetry():
    """Get latest telemetry from the satellite."""
    telemetry = comm.request_telemetry()
    if not telemetry:
        raise HTTPException(status_code=500, detail="Failed to receive telemetry.")
    return telemetry

class SteeringRequest(BaseModel):
    target_telemetry: dict

@app.post("/steer", dependencies=[Depends(authenticate)])
def steer(req: SteeringRequest):
    """Calculate and send steering command to get back on proper telemetry."""
    current_telemetry = comm.request_telemetry()
    if not current_telemetry:
        raise HTTPException(status_code=500, detail="Failed to get current telemetry.")
    params = comm.calculate_steering(current_telemetry, req.target_telemetry)
    success = comm.send_command('steer', params)
    if not success:
        raise HTTPException(status_code=500, detail="Failed to send steer command.")
    return {"status": "Steering command sent"}

@app.post("/connect_with_signal", dependencies=[Depends(authenticate)])
def connect_with_signal(min_signal: float = 0.5):
    """Attempt to connect to the satellite based on antenna signal strength."""
    result = comm.connect_with_antenna_signal(min_signal=min_signal)
    signal = comm.get_antenna_signal_strength()
    return {"connected": comm.connected, "signal_strength": signal, "result": result}

@app.get("/signal_strength", dependencies=[Depends(authenticate)])
def signal_strength():
    """Get the current antenna signal strength (live)."""
    return {"signal_strength": comm.get_current_signal_strength()}

@app.get("/antenna_diagnostics", dependencies=[Depends(authenticate)])
def antenna_diagnostics():
    """Get advanced antenna diagnostics."""
    return comm.get_antenna_diagnostics()

@app.get("/packet_stats", dependencies=[Depends(authenticate)])
def packet_stats():
    """Get the number of packets sent and received."""
    return comm.get_packet_stats()

# In-memory storage for historical data and alert thresholds
historical_data = {
    'signal': [],
    'snr': [],
    'ber': [],
    'temperature': [],
    'packets_sent': [],
    'packets_received': [],
    'timestamps': []
}
alert_thresholds = {
    'signal_strength': 0.3,
    'snr_db': 15,
    'ber': 1e-5,
    'temperature_c': 50
}

@app.get("/historical_data", dependencies=[Depends(authenticate)])
def get_historical_data():
    """Export historical data as JSON from persistent storage."""
    return db.fetch_all_records()

@app.post("/set_alert_thresholds", dependencies=[Depends(authenticate)])
def set_alert_thresholds(request: Request):
    """Set user-configurable alert thresholds."""
    data = json.loads(request._body.decode()) if hasattr(request, '_body') else {}
    for key in alert_thresholds:
        if key in data:
            alert_thresholds[key] = float(data[key])
    return {"status": "Thresholds updated", "thresholds": alert_thresholds}

@app.post("/send_satellite_file", dependencies=[Depends(authenticate)])
def send_satellite_file(file_path: str = Form(...), bid_msat: int = Form(10000)):
    """Send a file via Blockstream Satellite, automate payment, and update charts/alerts."""
    result = bsi.send_file_and_broadcast(file_path, bid_msat)
    if result:
        return {"status": "Broadcast complete!"}
    else:
        return {"status": "Broadcast failed or timed out."}

@app.get("/dashboard", response_class=HTMLResponse)
def advanced_dashboard(username: str = Depends(authenticate)):
    html_content = f"""
    <html>
    <head>
        <title>Advanced Satellite Dashboard</title>
        <script src='https://cdn.jsdelivr.net/npm/chart.js'></script>
        <script>
        let signalHistory = [];
        let snrHistory = [];
        let berHistory = [];
        let tempHistory = [];
        let timeHistory = [];
        let sentHistory = [];
        let receivedHistory = [];
        let packetTimeHistory = [];
        let signalChart, packetChart, snrChart, berChart, tempChart;
        let alertThresholds = {signal_strength: {alert_thresholds['signal_strength']}, snr_db: {alert_thresholds['snr_db']}, ber: {alert_thresholds['ber']}, temperature_c: {alert_thresholds['temperature_c']}};
        function updateSignalStrength() {{
            fetch('/signal_strength', {{headers: {{Authorization: 'Basic ' + btoa('admin:space123')}}}})
                .then(response => response.json())
                .then(data => {{
                    document.getElementById('signal_strength').innerText = data.signal_strength.toFixed(2);
                    let now = new Date().toLocaleTimeString();
                    signalHistory.push(data.signal_strength);
                    timeHistory.push(now);
                    if (signalHistory.length > 30) {{ signalHistory.shift(); timeHistory.shift(); }}
                    if (signalChart) {{
                        signalChart.data.labels = timeHistory;
                        signalChart.data.datasets[0].data = signalHistory;
                        signalChart.update();
                    }}
                }});
        }}
        function updateDiagnostics() {{
            fetch('/antenna_diagnostics', {{headers: {{Authorization: 'Basic ' + btoa('admin:space123')}}}})
                .then(response => response.json())
                .then(data => {{
                    document.getElementById('diagnostics').innerText = JSON.stringify(data, null, 2);
                    // Alert if status is WARNING or thresholds exceeded
                    let alertMsg = '';
                    if (data.status && data.status !== 'OK') {{
                        alertMsg = 'ALERT: ' + data.status;
                    }}
                    if (data.signal_strength < alertThresholds.signal_strength) {{
                        alertMsg += ' Signal below threshold!';
                        alert('Signal below threshold!');
                    }}
                    if (data.snr_db < alertThresholds.snr_db) {{
                        alertMsg += ' SNR below threshold!';
                        alert('SNR below threshold!');
                    }}
                    if (data.ber > alertThresholds.ber) {{
                        alertMsg += ' BER above threshold!';
                        alert('BER above threshold!');
                    }}
                    if (data.temperature_c > alertThresholds.temperature_c) {{
                        alertMsg += ' Temperature above threshold!';
                        alert('Temperature above threshold!');
                    }}
                    document.getElementById('alert').innerText = alertMsg;
                    document.getElementById('alert').style.color = alertMsg ? 'red' : '';
                    // Update charts and historical data
                    snrHistory.push(data.snr_db);
                    berHistory.push(data.ber);
                    tempHistory.push(data.temperature_c);
                    if (snrHistory.length > 30) snrHistory.shift();
                    if (berHistory.length > 30) berHistory.shift();
                    if (tempHistory.length > 30) tempHistory.shift();
                    if (snrChart) {{ snrChart.data.labels = timeHistory; snrChart.data.datasets[0].data = snrHistory; snrChart.update(); }}
                    if (berChart) {{ berChart.data.labels = timeHistory; berChart.data.datasets[0].data = berHistory; berChart.update(); }}
                    if (tempChart) {{ tempChart.data.labels = timeHistory; tempChart.data.datasets[0].data = tempHistory; tempChart.update(); }}
                    // Store historical data
                    fetch('/packet_stats', {{headers: {{Authorization: 'Basic ' + btoa('admin:space123')}}}})
                        .then(resp => resp.json())
                        .then(pkt => {{
                            sentHistory.push(pkt.packets_sent);
                            receivedHistory.push(pkt.packets_received);
                            packetTimeHistory.push(new Date().toLocaleTimeString());
                            if (sentHistory.length > 30) {{ sentHistory.shift(); receivedHistory.shift(); packetTimeHistory.shift(); }}
                            // Store in server-side historical_data
                            fetch('/historical_data', {{headers: {{Authorization: 'Basic ' + btoa('admin:space123')}}}})
                                .then(histResp => histResp.json())
                                .then(hist => {{
                                    // Only push if new
                                    if (hist.timestamps.length === 0 || hist.timestamps[hist.timestamps.length-1] !== timeHistory[timeHistory.length-1]) {{
                                        fetch('/historical_data', {{method: 'POST', headers: {{'Content-Type': 'application/json', Authorization: 'Basic ' + btoa('admin:space123')}}, body: JSON.stringify({{
                                            signal: signalHistory,
                                            snr: snrHistory,
                                            ber: berHistory,
                                            temperature: tempHistory,
                                            packets_sent: sentHistory,
                                            packets_received: receivedHistory,
                                            timestamps: timeHistory
                                        }})}});
                                    }}
                                }});
                            // Store in persistent DB
                            db.insert_record(
                                data.signal_strength,
                                data.snr_db,
                                data.ber,
                                data.temperature_c,
                                pkt.packets_sent,
                                pkt.packets_received
                            );
                            // TODO: Add hooks here for advanced analytics (moving averages, trends, etc.)
                            // TODO: Add hooks here for email/SMS notifications if thresholds are exceeded
                        }});
                }});
        }}
        function updatePacketStats() {{
            fetch('/packet_stats', {{headers: {{Authorization: 'Basic ' + btoa('admin:space123')}}}})
                .then(response => response.json())
                .then(data => {{
                    document.getElementById('packets_sent').innerText = data.packets_sent;
                    document.getElementById('packets_received').innerText = data.packets_received;
                    let now = new Date().toLocaleTimeString();
                    sentHistory.push(data.packets_sent);
                    receivedHistory.push(data.packets_received);
                    packetTimeHistory.push(now);
                    if (sentHistory.length > 30) {{ sentHistory.shift(); receivedHistory.shift(); packetTimeHistory.shift(); }}
                    if (packetChart) {{
                        packetChart.data.labels = packetTimeHistory;
                        packetChart.data.datasets[0].data = sentHistory;
                        packetChart.data.datasets[1].data = receivedHistory;
                        packetChart.update();
                    }}
                }});
        }}
        function setupCharts() {{
            const ctx = document.getElementById('signalChart').getContext('2d');
            signalChart = new Chart(ctx, {{
                type: 'line',
                data: {{ labels: timeHistory, datasets: [{{ label: 'Signal Strength', data: signalHistory, borderColor: 'blue', fill: false }}] }},
                options: {{scales: {{y: {{min: 0, max: 1}}}}}}
            }});
            const ctx2 = document.getElementById('packetChart').getContext('2d');
            packetChart = new Chart(ctx2, {{
                type: 'line',
                data: {{ labels: packetTimeHistory, datasets: [
                    {{label: 'Packets Sent', data: sentHistory, borderColor: 'green', fill: false}},
                    {{label: 'Packets Received', data: receivedHistory, borderColor: 'orange', fill: false}}
                ]}},
                options: {{scales: {{y: {{beginAtZero: true}}}}}}
            }});
            const ctx3 = document.getElementById('snrChart').getContext('2d');
            snrChart = new Chart(ctx3, {{
                type: 'line',
                data: {{ labels: timeHistory, datasets: [{{ label: 'SNR (dB)', data: snrHistory, borderColor: 'purple', fill: false }}] }},
                options: {{scales: {{y: {{min: 0, max: 50}}}}}}
            }});
            const ctx4 = document.getElementById('berChart').getContext('2d');
            berChart = new Chart(ctx4, {{
                type: 'line',
                data: {{ labels: timeHistory, datasets: [{{ label: 'BER', data: berHistory, borderColor: 'red', fill: false }}] }},
                options: {{scales: {{y: {{min: 0, max: 0.0001}}}}}}
            }});
            const ctx5 = document.getElementById('tempChart').getContext('2d');
            tempChart = new Chart(ctx5, {{
                type: 'line',
                data: {{ labels: timeHistory, datasets: [{{ label: 'Temperature (C)', data: tempHistory, borderColor: 'brown', fill: false }}] }},
                options: {{scales: {{y: {{min: -30, max: 80}}}}}}
            }});
        }}
        setInterval(updateSignalStrength, 1000);
        setInterval(updateDiagnostics, 5000);
        setInterval(updatePacketStats, 1000);
        window.onload = function() {{
            setupCharts();
            updateSignalStrength();
            updateDiagnostics();
            updatePacketStats();
        }}
        function setThresholds() {{
            let s = parseFloat(document.getElementById('th_signal').value);
            let snr = parseFloat(document.getElementById('th_snr').value);
            let ber = parseFloat(document.getElementById('th_ber').value);
            let t = parseFloat(document.getElementById('th_temp').value);
            alertThresholds.signal_strength = s;
            alertThresholds.snr_db = snr;
            alertThresholds.ber = ber;
            alertThresholds.temperature_c = t;
            fetch('/set_alert_thresholds', {{method: 'POST', headers: {{'Content-Type': 'application/json', Authorization: 'Basic ' + btoa('admin:space123')}}, body: JSON.stringify(alertThresholds)}})
                .then(resp => resp.json())
                .then(data => alert('Thresholds updated!'));
        }}
        function exportHistory() {{
            fetch('/historical_data', {{headers: {{Authorization: 'Basic ' + btoa('admin:space123')}}}})
                .then(resp => resp.json())
                .then(data => {{
                    const blob = new Blob([JSON.stringify(data, null, 2)], {{type: 'application/json'}});
                    const url = URL.createObjectURL(blob);
                    const a = document.createElement('a');
                    a.href = url;
                    a.download = 'historical_data.json';
                    a.click();
                    URL.revokeObjectURL(url);
                }});
        }}
        function sendSatelliteFile() {{
            const filePath = document.getElementById('sat_file_path').value;
            const bidMsat = document.getElementById('sat_bid_msat').value;
            fetch('/send_satellite_file', {{
                method: 'POST',
                headers: {{'Authorization': 'Basic ' + btoa('admin:space123'), 'Content-Type': 'application/x-www-form-urlencoded'}},
                body: `file_path=${{encodeURIComponent(filePath)}}&bid_msat=${{encodeURIComponent(bidMsat)}}`
            }})
            .then(resp => resp.json())
            .then(data => {{
                alert(data.status);
                if (data.status.includes('complete')) {{
                    // Optionally trigger chart/alert update here
                }}
            }});
        }}
        </script>
    </head>
    <body>
        <h1>Satellite Ground Station Dashboard</h1>
        <div id='alert' style='font-weight:bold;'></div>
        <h2>Live Antenna Signal Strength: <span id='signal_strength'>--</span></h2>
        <canvas id='signalChart' width='400' height='100'></canvas>
        <h2>SNR (dB)</h2>
        <canvas id='snrChart' width='400' height='100'></canvas>
        <h2>BER</h2>
        <canvas id='berChart' width='400' height='100'></canvas>
        <h2>Temperature (C)</h2>
        <canvas id='tempChart' width='400' height='100'></canvas>
        <h2>Advanced Antenna Diagnostics:</h2>
        <pre id='diagnostics'>Loading...</pre>
        <h2>Packet Control</h2>
        <div>Packets Sent: <span id='packets_sent'>0</span></div>
        <div>Packets Received: <span id='packets_received'>0</span></div>
        <canvas id='packetChart' width='400' height='100'></canvas>
        <h2>Alert Thresholds</h2>
        <div>
            Signal: <input id='th_signal' type='number' step='0.01' value='{alert_thresholds['signal_strength']}' />
            SNR: <input id='th_snr' type='number' step='0.1' value='{alert_thresholds['snr_db']}' />
            BER: <input id='th_ber' type='number' step='0.00001' value='{alert_thresholds['ber']}' />
            Temp: <input id='th_temp' type='number' step='0.1' value='{alert_thresholds['temperature_c']}' />
            <button onclick='setThresholds()'>Set Thresholds</button>
        </div>
        <button onclick='exportHistory()'>Export Historical Data</button>
        <h2>Connect with Antenna Signal</h2>
        <form action='/connect_with_signal' method='post'>
            <label>Min Signal (0.0-1.0):</label>
            <input name='min_signal' type='number' step='0.01' value='0.5' min='0' max='1' />
            <button type='submit'>Connect</button>
        </form>
        <h2>Send Command</h2>
        <form action='/send_command' method='post'>
            <label>Command:</label>
            <input name='command' type='text' value='reboot' />
            <label>Params:</label>
            <input name='params' type='text' />
            <button type='submit'>Send Command</button>
        </form>
        <h2>Request Photo</h2>
        <form action='/request_photo' method='get'>
            <button type='submit'>Request Photo</button>
        </form>
        <h2>Telemetry</h2>
        <form action='/telemetry' method='get'>
            <button type='submit'>Get Telemetry</button>
        </form>
        <h2>Steering</h2>
        <form action='/steer' method='post'>
            <label>Target pos_x:</label><input name='target_telemetry[pos_x]' type='text' />
            <label>Target pos_y:</label><input name='target_telemetry[pos_y]' type='text' />
            <label>Target pos_z:</label><input name='target_telemetry[pos_z]' type='text' />
            <button type='submit'>Send Steering Command</button>
        </form>
        <h2>Status</h2>
        <form action='/status' method='get'>
            <button type='submit'>Check Status</button>
        </form>
        <h2>Send File via Blockstream Satellite</h2>
        <div>
            File Path: <input id='sat_file_path' type='text' placeholder='e.g. /path/to/file.txt' />
            Bid (msat): <input id='sat_bid_msat' type='number' value='10000' />
            <button onclick='sendSatelliteFile()'>Send & Broadcast</button>
        </div>
    </body>
    </html>
    """
    return HTMLResponse(content=html_content)

# Add more endpoints for telemetry, logs, etc. as needed

# Simple HTML dashboard (for demo)
@app.get("/")
def dashboard():
    html_content = """
    <html>
    <head><title>Satellite Dashboard</title></head>
    <body>
        <h1>Satellite Ground Station Dashboard</h1>
        <form action="/send_command" method="post">
            <label>Command:</label>
            <input name="command" type="text" value="reboot" />
            <label>Params:</label>
            <input name="params" type="text" />
            <button type="submit">Send Command</button>
        </form>
        <form action="/request_photo" method="get">
            <button type="submit">Request Photo</button>
        </form>
        <form action="/status" method="get">
            <button type="submit">Check Status</button>
        </form>
    </body>
    </html>
    """
    return HTMLResponse(content=html_content) 