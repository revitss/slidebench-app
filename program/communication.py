import serial
import time
from serial.tools import list_ports
from utils import steps_to_mm
from tkinter import messagebox

# Global variable holding the active Arduino serial connection.
# It is None when no Arduino is connected, and holds a serial.Serial
# object when a connection has been established.
arduino = None


def refresh_ports():
    """
    Scans the system for all available serial COM ports and returns their names.
    Called when the connection window opens and when the Refresh button is clicked,
    so the user can see all currently connected serial devices.

    Returns
    -------
    list of str
        A list of port name strings e.g. ['COM3', 'COM5'].
        Returns an empty list if no ports are found.
    """
    # list_ports.comports() returns a list of port info objects
    # We extract just the device name (e.g. 'COM3') from each one
    ports = [port.device for port in list_ports.comports()]
    return ports


def connect_arduino(port, baudrate=115200):
    """
    Attempts to establish a serial connection with the Arduino on the given port.
    If successful, stores the connection in the global arduino variable so all
    other functions in this module can use it.

    A 2 second delay is added after opening the port because the Arduino
    resets itself when a serial connection is opened, and needs time to boot
    before it can receive commands.

    Parameters
    ----------
    port : str
        The COM port to connect to e.g. 'COM3'.
    baudrate : int, optional
        The communication speed in bits per second. Must match the baudrate
        set in the Arduino sketch. Default is 115200.

    Returns
    -------
    bool
        True if the connection was established successfully, False otherwise.
    """
    global arduino
    try:
        # Open the serial port with the specified settings
        # timeout=1 means read operations will wait at most 1 second
        arduino = serial.Serial(port, baudrate, timeout=1)
        # Wait for the Arduino to finish resetting after the port is opened
        # Without this delay, the first commands sent may be missed
        time.sleep(2)
        return True
    except serial.SerialException:
        # Connection failed (port busy, wrong port, device not found, etc.)
        # Reset the global to None so other functions know there is no connection
        arduino = None
        return False


def disconnect_arduino():
    """
    Safely closes the Arduino serial connection if it is currently open.
    Resets the global arduino variable to None after closing.
    Should be called when the application closes to release the serial port
    so other programs can use it.
    """
    global arduino
    if arduino and arduino.is_open:
        # Close the serial port to release the hardware resource
        arduino.close()
        # Reset the global so other functions know there is no active connection
        arduino = None


def send_command(command):
    """
    Sends a text command string to the Arduino over the serial connection.
    A newline character is appended to the command because the Arduino sketch
    uses readline() to read incoming commands and expects a newline terminator.

    If the Arduino is not connected, the command is not sent and a message
    is printed to the console for debugging purposes.

    Parameters
    ----------
    command : str
        The command string to send to the Arduino e.g. 'r', 'v5', 'g1000'.
        Do not include the newline — it is added automatically.
    """
    if arduino and arduino.is_open:
        # Encode the command as bytes and send it over the serial port
        # The newline '\n' acts as the command terminator for the Arduino
        arduino.write((command + '\n').encode())
    else:
        # Arduino is not connected — show a debug message so the developer
        # knows the command was not delivered
        messagebox.showwarning("Error", f"Command '{command}' not sent: Arduino not connected.")


def read_current_position():
    """
    Reads the current motor position reported by the Arduino and converts
    it from steps to millimeters.

    The Arduino continuously sends position updates in the format:
        'POS:<steps>'
    For example: 'POS:1250' means the motor is at 1250 steps from origin.

    This function checks if data is available in the serial buffer,
    reads one line, validates the format, extracts the step count,
    and converts it to millimeters using steps_to_mm().

    Called repeatedly every 50ms by the position update loop in the GUI
    to keep the digital position display up to date.

    Returns
    -------
    float or None
        The current motor position in millimeters, or None if no valid
        position data is available in the serial buffer.
    """
    # Only attempt to read if the Arduino is connected and data is waiting
    if arduino and arduino.in_waiting:
        # Read one line from the serial buffer and decode it from bytes to string
        # strip() removes any trailing whitespace or newline characters
        line = arduino.readline().decode('utf-8').strip()

        # Check that the line follows the expected 'POS:<steps>' format
        if line.startswith("POS:"):
            try:
                # Split on ':' and take the second part to get the step count
                # e.g. 'POS:1250' → '1250' → 1250
                steps = abs(int(line.split(":")[1].strip()))
                # Convert the step count to millimeters using the utility function
                return steps_to_mm(steps)
            except Exception as e:
                # If parsing fails (malformed data, unexpected format, etc.)
                # show the error and return None gracefully
                messagebox.showwarning("Error", f"Error parsing position data: {e}")

    # Return None if no data was available or parsing failed
    return None