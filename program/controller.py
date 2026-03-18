from communication import send_command
from utils import mm_to_steps
from tkinter import messagebox

# ==========================================================
#  MOTOR CONTROL FUNCTIONS
# ==========================================================
# These functions send movement commands to the Arduino via serial.
# The Arduino interprets each command string and drives the stepper motor.

def move_right(event):
    """
    Sends a command to move the motor continuously to the right.
    Bound to the ButtonPress event of the right arrow button in the GUI.
    The motor keeps moving until stop_motor() is called on ButtonRelease.

    Parameters
    ----------
    event : tkinter.Event
        The button press event passed automatically by Tkinter.
    """
    # 'r' command tells the Arduino to start moving right continuously
    send_command('r')


def move_left(event):
    """
    Sends a command to move the motor continuously to the left.
    Bound to the ButtonPress event of the left arrow button in the GUI.
    The motor keeps moving until stop_motor() is called on ButtonRelease.

    Parameters
    ----------
    event : tkinter.Event
        The button press event passed automatically by Tkinter.
    """
    # 'l' command tells the Arduino to start moving left continuously
    send_command('l')


def stop_motor(event):
    """
    Sends a command to immediately stop the motor.
    Bound to the ButtonRelease event of both arrow buttons in the GUI.
    Called automatically when the user releases the movement button.

    Parameters
    ----------
    event : tkinter.Event
        The button release event passed automatically by Tkinter.
    """
    # 's' command tells the Arduino to stop all motor movement
    send_command('s')


def set_speed(value):
    """
    Sets the motor movement speed by sending a speed command to the Arduino.
    Called every time the speed slider in the GUI is moved.

    Parameters
    ----------
    value : int or str
        Speed value from the slider (1 = slowest, 10 = fastest).
    """
    # 'v' prefix followed by the value sets the speed on the Arduino
    send_command(f'v{value}')


def move_motor(mm, direction):
    """
    Moves the motor a specific distance in millimeters in a given direction.
    Converts the distance from mm to motor steps using mm_to_steps(),
    then sends the move command to the Arduino.

    Parameters
    ----------
    mm : float or str
        The distance to move in millimeters. Can be a string from a GUI entry.
    direction : str
        The direction to move: 'f' for forward or 'b' for backward.
    """
    try:
        # Convert the input to a float and ensure it is positive
        mm_value = abs(float(mm))
        # Convert millimeters to motor steps using the conversion utility
        steps = mm_to_steps(mm_value)
        # Send the move command: 'p' prefix followed by steps and direction
        # e.g. 'p500f' means move 500 steps forward
        send_command(f'p{steps}{direction}')
    except ValueError as e:
        messagebox.showwarning("Error", f"Error: {e}")

def move_to_position(mm):
    """
    Moves the motor to a specific absolute position in millimeters.
    Converts the target position from mm to steps and sends a
    go-to command to the Arduino.

    Parameters
    ----------
    mm : float or str
        The target absolute position in millimeters.
        Can be a string from a GUI entry field.
    """
    try:
        # Convert the input to a float and ensure it is positive
        mm_value = abs(float(mm))
        # Convert the target position from mm to motor steps
        steps = mm_to_steps(mm_value)
        # Send the go-to command: 'g' prefix followed by the step count
        # e.g. 'g1000' means go to position 1000 steps from origin
        send_command(f"g{steps}")
    except ValueError:
        messagebox.showwarning("Error", "Invalid input.")
    except Exception as e:
        messagebox.showwarning("Error", f"Error: {e}")


# ==========================================================
#  FILTER CONTROL
# ==========================================================
# The optical filter wheel is controlled by the Arduino.
# Each filter has an associated GUI highlight color for visual feedback.

# Maps each filter key to its display color in the GUI
colors = {
    "r": "#EA1515",   # Red filter   → red highlight
    "g": "#32CD32",   # Green filter → green highlight
    "b": "#4231DC",   # Blue filter  → blue highlight
    "w": "#BCBCBC"    # White filter → grey highlight
}


def activate_filter(flt):
    """
    Activates a specific optical filter by sending a command to the Arduino.
    The Arduino physically rotates the filter wheel to the selected filter.
    Returns the associated GUI highlight color so the calling code can
    update the button appearance.

    Parameters
    ----------
    flt : str
        The filter to activate. One of: 'r', 'g', 'b', 'w'.

    Returns
    -------
    str
        The hex color code associated with the filter for GUI highlighting.
        Returns 'gray' if an invalid filter key is provided.
    """
    if flt in colors:
        # Send the filter command: 'f:' prefix followed by the filter key
        # e.g. 'f:r' activates the red filter
        send_command(f"f:{flt}")
        # Return the associated color so the GUI can highlight the button
        return colors[flt]
    else:
        # Return gray as a fallback color for invalid filter keys
        return "gray"


# ==========================================================
#  LED CONTROL
# ==========================================================
# The LED light source is controlled by the Arduino.
# It can be turned on/off and its intensity can be adjusted.

def led_on():
    """
    Turns the LED light source on.
    Sends the 'on' command to the Arduino to activate the LED.
    """
    # 'on' command tells the Arduino to turn on the LED
    send_command("on")


def led_off():
    """
    Turns the LED light source off.
    Sends the 'off' command to the Arduino to deactivate the LED.
    """
    # 'off' command tells the Arduino to turn off the LED
    send_command("off")


def led_intensity(value):
    """
    Sets the brightness of the LED light source.
    Sends an intensity command to the Arduino which adjusts
    the LED driver accordingly.

    Parameters
    ----------
    value : int or str
        The intensity level to set (1 = dimmest, 10 = brightest).
    """
    # 'led' prefix followed by the value sets the LED intensity
    # e.g. 'led7' sets the intensity to level 7
    send_command(f"led{value}")