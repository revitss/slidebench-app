import serial
import time
from serial.tools import list_ports
from utils import steps_to_mm

# Global variable holding the current Arduino serial connection
arduino = None


def refresh_ports():
    """
    Scans and returns all available serial (COM) ports on the system.

    Returns
    -------
    list of str
        A list of port names.
    """
    ports = [port.device for port in list_ports.comports()]
    return ports


def connect_arduino(port, baudrate=115200):
    """
    Attempts to establish a serial connection with the Arduino.

    Parameters
    ----------
    port : str
        The COM port name (e.g., "COM3").
    baudrate : int, optional
        Communication speed in bits per second (default: 115200).

    Returns
    -------
    bool
        True if the connection is successfully established, False otherwise.
    """
    global arduino
    try:
        # Open the serial connection
        arduino = serial.Serial(port, baudrate, timeout=1)

        # Wait a short moment for Arduino to reset after opening the port
        time.sleep(2)
        return True

    except serial.SerialException:
        # If connection fails, clear the arduino reference
        arduino = None
        return False


def disconnect_arduino():
    """
    Closes the Arduino serial connection safely if it is currently open.
    """
    global arduino
    if arduino and arduino.is_open:
        arduino.close()
        arduino = None


def send_command(command):
    """
    Sends a text command to the Arduino followed by a newline character.

    Parameters
    ----------
    command : str
        The command string to send (without newline).
    """
    if arduino and arduino.is_open:
        arduino.write((command + '\n').encode())


def read_current_position():
    """
    Reads the current position reported by the Arduino.

    Expected format: "POS:<steps>"

    Converts the received number of motor steps to millimeters using
    the `steps_to_mm()` function from the utils module.

    Returns
    -------
    float or None
        The current position in millimeters, or None if no valid data is received.
    """
    if arduino and arduino.in_waiting:
        line = arduino.readline().decode('utf-8').strip()

        if line.startswith("POS:"):
            try:
                # Extract step count from the message
                steps = abs(int(line.split(":")[1].strip()))

                # Convert steps to millimeters
                return steps_to_mm(steps)

            except Exception as e:
                print(f"Error parsing position data: {e}")

    return None