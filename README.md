# SpaceComm: Satellite Ground Station & Dashboard

## Overview

SpaceComm is a Python-based ground station and web dashboard for satellite communication, telemetry, and control. It supports:
- Real-time satellite communication (TCP/UDP/serial)
- Command and telemetry interface
- Photo and data reception
- Live dashboard with charts, analytics, and alerts
- Persistent historical data storage (SQLite)
- Integration with Blockstream Satellite API for global data broadcast
- Automated Lightning payment for satellite transmission
- Email/SMS alert hooks (extensible)

---

## Features

- **Satellite Communication**: Connect, send commands (reboot, steer, etc.), receive telemetry and photos.
- **Live Dashboard**: FastAPI-based web UI with real-time charts for signal, SNR, BER, temperature, and packet stats.
- **Alerts & Notifications**: User-configurable thresholds, browser/email/SMS alerts (hooks provided).
- **Persistent Analytics**: All data stored in SQLite, exportable as JSON.
- **Blockstream Satellite API Integration**: Send files/messages globally, automate Lightning payment, monitor broadcast status.
- **Hardware Integration**: Monitor real antenna signal using `blocksat-cli`.

---

## Requirements

- Python 3.8+
- pip packages: `fastapi`, `uvicorn`, `websockets`, `python-multipart`, `requests`, `pydantic`, `sqlite3`
- [blocksat-cli](https://blockstream.github.io/satellite/doc/quick-reference.html) (for hardware/signal monitoring)
- [lightning-cli](https://github.com/ElementsProject/lightning) (for automated Lightning payments)
- (Optional) Email/SMS libraries: `smtplib`, `twilio`

---

## Installation

1. **Clone the repository**
   ```bash
   git clone <your-repo-url>
   cd SpaceComm
   ```

2. **Install Python dependencies**
   ```bash
   pip install fastapi uvicorn websockets python-multipart requests pydantic
   ```

3. **Install blocksat-cli**
   ```bash
   pip install blocksat-cli
   # Or follow Blockstream's official guide for your OS
   ```

4. **Install and configure lightning-cli**
   - Follow [Core Lightning setup](https://github.com/ElementsProject/lightning) and ensure `lightning-cli` is in your PATH and running.

---

## Running the Application

1. **Start the FastAPI server**
   ```bash
   uvicorn main:app --reload
   ```

2. **Access the dashboard**
   - Open [http://127.0.0.1:8000/dashboard](http://127.0.0.1:8000/dashboard)
   - Default credentials: `admin` / `space123`

3. **API documentation**
   - Swagger UI: [http://127.0.0.1:8000/docs](http://127.0.0.1:8000/docs)

---

## Dashboard Usage

- **Live Charts**: Signal, SNR, BER, temperature, and packet stats update in real time.
- **Alerts**: Set thresholds for each parameter. Alerts are shown in the dashboard and can be extended to email/SMS.
- **Send Commands**: Use the dashboard to send commands (reboot, steer, etc.) to the satellite.
- **Request Photo**: Request and download photos from the satellite.
- **Telemetry**: View latest telemetry data.
- **Steering**: Input target telemetry to auto-calculate and send steering commands.
- **Packet Control**: Monitor packets sent/received.
- **Export Data**: Download all historical data as JSON.
- **Blockstream Satellite File Broadcast**: Enter a file path and bid, click "Send & Broadcast" to transmit via Blockstream Satellite (automated Lightning payment required).

---

## Blockstream Satellite API Integration

- **Send a File**: Enter the file path and bid (msat) in the dashboard, click "Send & Broadcast".
- **Automated Payment**: The system uses `lightning-cli` to pay the invoice automatically.
- **Broadcast Status**: The dashboard will alert you when the broadcast is complete.
- **Signal Monitoring**: Uses `blocksat-cli` to monitor real antenna signal (standalone, USB, or SDR receivers supported).

---

## Advanced Analytics

- Moving averages, min/max, and trends are computed and displayed for all key parameters.
- All analytics are based on persistent data stored in SQLite.

---

## Alerts & Notifications

- Set thresholds for signal, SNR, BER, and temperature in the dashboard.
- Alerts are shown in the UI and can be extended to email/SMS by adding your SMTP/Twilio credentials in the code.

---

## Customization & Extensibility

- **Hardware Integration**: Edit `satellite_comm.py` to use your specific receiver/API.
- **Notification Channels**: Add your email/SMS logic in the provided hooks.
- **Analytics**: Extend analytics in `db.py` and display in the dashboard.
- **Authentication**: Change credentials in `main.py` as needed.

---

## Troubleshooting

- Ensure `blocksat-cli` and `lightning-cli` are installed and in your PATH.
- The backend must have access to any file you wish to send via satellite.
- For Lightning payments, your node must be funded and running.
- Check logs for error messages if broadcasts or payments fail.

---

## References
- [Blockstream Satellite API Docs](https://blockstream.com/satellite-api-documentation/)
- [blocksat-cli Quick Reference](https://blockstream.github.io/satellite/doc/quick-reference.html)
- [Core Lightning](https://github.com/ElementsProject/lightning)

---

## License

MIT License. See LICENSE file for details. 