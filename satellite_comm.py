import socket
import threading
import time
import struct
from typing import Optional
import random
import requests
import subprocess

# Constants for Space Packet Protocol (simplified CCSDS)
PRIMARY_HEADER_FORMAT = '>HHH'  # Example: 6 bytes primary header
PRIMARY_HEADER_SIZE = 6
MAX_PACKET_SIZE = 1024  # Adjust as needed
RETRY_LIMIT = 5
RETRY_DELAY = 2  # seconds

BLOCKSTREAM_API = "https://api.blockstream.space"
BLOCKSAT_CLI_PATH = "blocksat-cli"  # Ensure blocksat-cli is installed and in PATH

# Example command codes
def get_command_code(command: str) -> int:
    command_map = {
        'reboot': 0x01,
        'steer': 0x02,
        'get_photo': 0x03,
        'get_telemetry': 0x04,
        # Add more as needed
    }
    return command_map.get(command, 0xFF)

class SatelliteComm:
    """
    Handles communication with the satellite using TCP/UDP sockets.
    Implements packet-level retry, error handling, and supports sending/receiving commands and data.
    """
    def __init__(self, host: str, port: int, use_udp: bool = False):
        self.host = host
        self.port = port
        self.use_udp = use_udp
        self.sock: Optional[socket.socket] = None
        self.lock = threading.Lock()
        self.connected = False
        # Packet counters
        self.packets_sent = 0
        self.packets_received = 0

    def connect(self):
        """Establish connection to the satellite."""
        try:
            if self.use_udp:
                self.sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            else:
                self.sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                self.sock.settimeout(10)
                self.sock.connect((self.host, self.port))
            self.connected = True
        except Exception as e:
            print(f"[ERROR] Connection failed: {e}")
            self.connected = False

    def disconnect(self):
        """Close the connection."""
        if self.sock:
            self.sock.close()
        self.connected = False

    def send_packet(self, data: bytes) -> bool:
        """Send a packet with retry logic."""
        for attempt in range(RETRY_LIMIT):
            try:
                with self.lock:
                    if not self.connected:
                        self.connect()
                    if self.use_udp:
                        self.sock.sendto(data, (self.host, self.port))
                    else:
                        self.sock.sendall(data)
                    self.packets_sent += 1
                return True
            except Exception as e:
                print(f"[ERROR] Send failed (attempt {attempt+1}): {e}")
                self.disconnect()
                time.sleep(RETRY_DELAY)
        return False

    def receive_packet(self, expected_size=MAX_PACKET_SIZE) -> Optional[bytes]:
        """Receive a packet with retry logic."""
        for attempt in range(RETRY_LIMIT):
            try:
                with self.lock:
                    if not self.connected:
                        self.connect()
                    if self.use_udp:
                        data, _ = self.sock.recvfrom(expected_size)
                    else:
                        data = self.sock.recv(expected_size)
                if data:
                    self.packets_received += 1
                    return data
            except Exception as e:
                print(f"[ERROR] Receive failed (attempt {attempt+1}): {e}")
                self.disconnect()
                time.sleep(RETRY_DELAY)
        return None

    def build_space_packet(self, apid: int, seq: int, payload: bytes) -> bytes:
        """
        Build a CCSDS-like space packet.
        apid: Application Process ID
        seq: Sequence count
        payload: Data payload
        """
        length = len(payload) + PRIMARY_HEADER_SIZE - 1
        header = struct.pack(PRIMARY_HEADER_FORMAT, apid, seq, length)
        return header + payload

    def parse_space_packet(self, packet: bytes):
        """Parse a CCSDS-like space packet."""
        if len(packet) < PRIMARY_HEADER_SIZE:
            raise ValueError("Packet too short")
        header = packet[:PRIMARY_HEADER_SIZE]
        apid, seq, length = struct.unpack(PRIMARY_HEADER_FORMAT, header)
        payload = packet[PRIMARY_HEADER_SIZE:]
        return apid, seq, payload

    def send_command(self, command: str, params: Optional[bytes] = None) -> bool:
        """
        Send a command to the satellite.
        command: Command string (e.g., 'reboot', 'steer')
        params: Optional parameters as bytes
        """
        code = get_command_code(command)
        payload = struct.pack('>B', code) + (params or b'')
        packet = self.build_space_packet(apid=0x100, seq=int(time.time()) & 0xFFFF, payload=payload)
        return self.send_packet(packet)

    def request_photo(self) -> Optional[bytes]:
        """
        Request a photo from the satellite and receive it as bytes.
        Handles packet reassembly if needed.
        """
        if not self.send_command('get_photo'):
            print("[ERROR] Failed to send photo request command.")
            return None
        photo_data = b''
        while True:
            packet = self.receive_packet()
            if not packet:
                print("[ERROR] Photo packet receive failed.")
                break
            apid, seq, payload = self.parse_space_packet(packet)
            # Example: last packet is marked by a special byte (0xFF)
            if payload.endswith(b'\xFF'):
                photo_data += payload[:-1]
                break
            else:
                photo_data += payload
        return photo_data

    def request_telemetry(self) -> Optional[dict]:
        """
        Request telemetry data from the satellite and parse it into a dictionary.
        """
        if not self.send_command('get_telemetry'):
            print("[ERROR] Failed to send telemetry request command.")
            return None
        packet = self.receive_packet()
        if not packet:
            print("[ERROR] Telemetry packet receive failed.")
            return None
        apid, seq, payload = self.parse_space_packet(packet)
        # Example: parse telemetry (assume simple key-value pairs, comma-separated)
        try:
            telemetry_str = payload.decode(errors='ignore')
            telemetry = dict(item.split('=') for item in telemetry_str.split(',') if '=' in item)
            return telemetry
        except Exception as e:
            print(f"[ERROR] Telemetry parsing failed: {e}")
            return None

    def calculate_steering(self, current_telemetry: dict, target_telemetry: dict) -> bytes:
        """
        Calculate steering command parameters to get back on proper telemetry.
        Returns parameters as bytes to be sent with the 'steer' command.
        """
        # Example: Assume telemetry has 'pos_x', 'pos_y', 'pos_z', 'vel_x', 'vel_y', 'vel_z'
        try:
            delta_x = float(target_telemetry['pos_x']) - float(current_telemetry['pos_x'])
            delta_y = float(target_telemetry['pos_y']) - float(current_telemetry['pos_y'])
            delta_z = float(target_telemetry['pos_z']) - float(current_telemetry['pos_z'])
            # Simple proportional control (for demo)
            steer_x = delta_x * 0.1
            steer_y = delta_y * 0.1
            steer_z = delta_z * 0.1
            # Pack as 3 floats
            return struct.pack('>fff', steer_x, steer_y, steer_z)
        except Exception as e:
            print(f"[ERROR] Steering calculation failed: {e}")
            return b''

    def get_antenna_signal_strength(self) -> float:
        """
        Replace this stub with real hardware integration for signal strength.
        """
        # TODO: Integrate with real antenna hardware API here
        return random.uniform(0.0, 1.0)

    def connect_with_antenna_signal(self, min_signal: float = 0.5, max_attempts: int = 10) -> bool:
        """
        Attempt to connect to the satellite only if antenna signal is above a threshold.
        Retries up to max_attempts times.
        """
        for attempt in range(max_attempts):
            signal = self.get_antenna_signal_strength()
            print(f"[INFO] Antenna signal strength: {signal:.2f}")
            if signal >= min_signal:
                self.connect()
                if self.connected:
                    print("[INFO] Connected to satellite (signal sufficient).")
                    return True
            else:
                print(f"[WARN] Signal too weak (attempt {attempt+1}/{max_attempts}). Retrying...")
                time.sleep(2)
        print("[ERROR] Could not connect: antenna signal too weak.")
        return False

    def get_current_signal_strength(self) -> float:
        """
        Get the current antenna signal strength (for live display).
        """
        return self.get_antenna_signal_strength()

    def get_antenna_diagnostics(self) -> dict:
        """
        Replace this stub with real hardware integration for diagnostics.
        """
        # TODO: Integrate with real antenna hardware API here
        diagnostics = {
            'signal_strength': self.get_antenna_signal_strength(),
            'snr_db': random.uniform(10, 40),
            'ber': random.uniform(1e-7, 1e-4),
            'temperature_c': random.uniform(-20, 60),
            'power_w': random.uniform(5, 50),
            'status': 'OK' if random.random() > 0.1 else 'WARNING'
        }
        return diagnostics

    def get_packet_stats(self) -> dict:
        """
        Return the number of packets sent and received.
        """
        return {
            'packets_sent': self.packets_sent,
            'packets_received': self.packets_received
        }

    # Add more methods as needed for telemetry, redundancy, etc.

class BlockstreamSatelliteIntegration:
    """
    Integration with Blockstream Satellite API and blocksat-cli for real hardware.
    """
    def __init__(self, receiver_type='standalone'):
        self.receiver_type = receiver_type  # 'standalone', 'usb', 'sdr', etc.

    def send_file(self, file_path, bid_msat=10000):
        """
        Send a file via Blockstream Satellite API. Returns order info and Lightning invoice.
        """
        url = f"{BLOCKSTREAM_API}/order"
        files = {
            'bid': (None, str(bid_msat)),
            'file': open(file_path, 'rb')
        }
        response = requests.post(url, files=files)
        if response.status_code == 200:
            data = response.json()
            print("Order placed! Pay this Lightning invoice to broadcast:")
            print(data['lightning_invoice']['payreq'])
            print("Order UUID:", data['uuid'])
            print("Auth token:", data['auth_token'])
            return data
        else:
            print("Error:", response.text)
            return None

    def pay_invoice(self, payreq, lightning_cli_path='lightning-cli'):
        """
        Automate Lightning payment using lightning-cli (must be configured and running).
        """
        try:
            result = subprocess.run([lightning_cli_path, 'pay', payreq], capture_output=True, text=True)
            print(result.stdout)
            return result.returncode == 0
        except Exception as e:
            print(f"[ERROR] Lightning payment failed: {e}")
            return False

    def monitor_signal(self):
        """
        Monitor signal from the specified receiver using blocksat-cli.
        Returns the latest signal strength as a float (0.0-1.0), or None if not found.
        """
        try:
            if self.receiver_type == 'standalone':
                cmd = [BLOCKSAT_CLI_PATH, 'standalone', 'monitor']
            elif self.receiver_type == 'usb':
                cmd = [BLOCKSAT_CLI_PATH, 'usb', 'monitor']
            elif self.receiver_type == 'sdr':
                cmd = [BLOCKSAT_CLI_PATH, 'sdr', 'monitor']
            else:
                raise ValueError('Unknown receiver type')
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=10)
            # Parse signal strength from result.stdout (adjust regex as needed)
            import re
            match = re.search(r'Signal Strength: ([0-9.]+)', result.stdout)
            if match:
                return float(match.group(1))
            else:
                print("[WARN] Could not parse signal strength.")
                return None
        except Exception as e:
            print(f"[ERROR] Signal monitoring failed: {e}")
            return None

    def send_file_and_broadcast(self, file_path, bid_msat=10000, lightning_cli_path='lightning-cli'):
        """
        Full workflow: send file, pay invoice, poll for broadcast status.
        Updates charts and alerts via hooks (to be called in main app logic).
        """
        order = self.send_file(file_path, bid_msat)
        if not order:
            return False
        payreq = order['lightning_invoice']['payreq']
        print("Paying invoice...")
        if not self.pay_invoice(payreq, lightning_cli_path):
            print("[ERROR] Payment failed. Aborting broadcast.")
            return False
        print("Payment sent. Waiting for broadcast...")
        uuid = order['uuid']
        auth_token = order['auth_token']
        # Poll for order status
        for _ in range(30):  # Poll for up to 5 minutes
            status = self.get_order_status(uuid, auth_token)
            print(f"Order status: {status}")
            if status == 'sent':
                print("Broadcast complete!")
                # HOOK: update charts/alerts here
                return True
            time.sleep(10)
        print("[ERROR] Broadcast not completed in time.")
        return False

    def get_order_status(self, uuid, auth_token):
        url = f"{BLOCKSTREAM_API}/order/{uuid}"
        headers = {'X-Auth-Token': auth_token}
        response = requests.get(url, headers=headers)
        if response.status_code == 200:
            data = response.json()
            return data.get('status', 'unknown')
        else:
            print("[ERROR] Could not fetch order status.")
            return 'unknown'

# Example usage (for testing, not for production):
if __name__ == "__main__":
    comm = SatelliteComm('127.0.0.1', 5000)
    comm.connect()
    comm.send_command('reboot')
    photo = comm.request_photo()
    if photo:
        with open('photo.jpg', 'wb') as f:
            f.write(photo)
    comm.disconnect()

# Example usage (to be called from main app logic):
# bsi = BlockstreamSatelliteIntegration(receiver_type='standalone')
# bsi.send_file_and_broadcast('myfile.txt', bid_msat=10000) 