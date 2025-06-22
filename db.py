import sqlite3
import threading
import json
from datetime import datetime

DB_FILE = 'satellite_data.db'
DB_LOCK = threading.Lock()

# Initialize the database and create tables if they don't exist
def init_db():
    with DB_LOCK, sqlite3.connect(DB_FILE) as conn:
        c = conn.cursor()
        c.execute('''
            CREATE TABLE IF NOT EXISTS telemetry (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp TEXT,
                signal REAL,
                snr REAL,
                ber REAL,
                temperature REAL,
                packets_sent INTEGER,
                packets_received INTEGER
            )
        ''')
        conn.commit()

# Insert a new telemetry/diagnostics record
def insert_record(signal, snr, ber, temperature, packets_sent, packets_received):
    with DB_LOCK, sqlite3.connect(DB_FILE) as conn:
        c = conn.cursor()
        c.execute('''
            INSERT INTO telemetry (timestamp, signal, snr, ber, temperature, packets_sent, packets_received)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        ''', (datetime.utcnow().isoformat(), signal, snr, ber, temperature, packets_sent, packets_received))
        conn.commit()

# Fetch all records as a list of dicts
def fetch_all_records():
    with DB_LOCK, sqlite3.connect(DB_FILE) as conn:
        c = conn.cursor()
        c.execute('SELECT timestamp, signal, snr, ber, temperature, packets_sent, packets_received FROM telemetry ORDER BY id ASC')
        rows = c.fetchall()
        result = []
        for row in rows:
            result.append({
                'timestamp': row[0],
                'signal': row[1],
                'snr': row[2],
                'ber': row[3],
                'temperature': row[4],
                'packets_sent': row[5],
                'packets_received': row[6]
            })
        return result

# Export all records as JSON
def export_all_records_json():
    return json.dumps(fetch_all_records(), indent=2)

# Call this at startup to ensure DB is ready
init_db() 