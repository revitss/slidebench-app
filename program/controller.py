from communication import send_command
from utils import mm_to_steps

# ==========================================================
#  MOTOR CONTROL FUNCTIONS
# ==========================================================

def move_right(event):
    """Moves the motor continuously to the right."""
    send_command('r')

def move_left(event):
    """Moves the motor continuously to the left."""
    send_command('l')

def stop_motor(event):
    """Stops motor movement immediately."""
    send_command('s')

def set_speed(value):
    """
    Sets the motor speed.

    Parameters
    ----------
    value : int or str
        Speed value to send to the Arduino.
    """
    send_command(f'v{value}')

def move_motor(mm, direction):
    """
    Moves the motor a specific distance (in mm) in the given direction.

    Parameters
    ----------
    mm_entry : tkinter.Entry
        Entry widget containing the distance (in millimeters).
    direction : tkinter.StringVar
        Variable storing the direction command (e.g., 'r' or 'l').
    """
    try:
        # Read and convert millimeters to steps
        mm_value = float(mm)
        mm_value = abs(mm_value)
        steps = mm_to_steps(mm_value)

        # Get direction (left/right) and ensure positive step count
        #direction_val = direction.get()

        # Send the motion command to Arduino
        send_command(f'p{steps}{direction}')

    except ValueError as e:
        print(f"Error: {e}")

def move_to_position(mm):
    """
    Moves the motor to an absolute position (in mm).

    Parameters
    ----------
    entry : tkinter.Entry
        Entry widget containing the target position in millimeters.
    """
    try:
        #mm_value = float(entry.get())
        mm_value = abs(mm)
        steps = mm_to_steps(mm_value)

        # Send the "go to" command (g = go to position)
        command = f"g{steps}"
        send_command(command)

    except ValueError:
        print("Invalid input or value not found in conversion table.")
    except Exception as e:
        print(f"Error: {e}")

# def move_to_position_ventana(steps):
#     """
#     Moves the motor to a specified position in steps.
#     Used by the automatic measurement module.

#     Parameters
#     ----------
#     steps : int
#         Target position in steps.
#     """
#     set_speed(2)
#     send_command(f"g{steps}")

# ==========================================================
#  FILTER CONTROL
# ==========================================================

# Color map for each optical filter (for GUI highlighting)
colores = {
    "r": "#EA1515",   # Red filter
    "g": "#32CD32",   # Green filter
    "b": "#4231DC",   # Blue filter
    "w": "#BCBCBC"    # White filter
}


def activate_filter(filter):
    """
    Activates a specific optical filter by sending a command to Arduino.

    Parameters
    ----------
    filtro : str
        One of: 'r', 'g', 'b', 'w'.

    Returns
    -------
    str
        The associated color code for UI display.
    """
    if filter in colores:
        send_command(f"f:{filter}")
        return colores[filter]
    else:
        print("Invalid filter.")
        return "gray"


# ==========================================================
#  LED CONTROL
# ==========================================================

def led_on():
    """Turns the LED on."""
    send_command("on")


def led_off():
    """Turns the LED off."""
    send_command("off")


def led_intensity(valor):
    """
    Sets the LED intensity.

    Parameters
    ----------
    valor : int or str
        Intensity level (typically 1–10).
    """
    send_command(f"led{valor}")


# def encender_led_maximo():
#     """Turns on the LED at maximum brightness."""
#     encender_led()
#     set_intensidad_led(10)