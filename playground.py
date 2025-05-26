from sense_hat import SenseHat
import time
import math

# Initialize Sense HAT
sense = SenseHat()
sense.clear()

# Define colors for each sensor row
colors = [
    [255, 0, 0],   # Red for temperature
    [0, 255, 0],   # Green for humidity
    [0, 0, 255],   # Blue for pressure
    [255, 255, 0], # Yellow for accel_x
    [255, 0, 255], # Magenta for accel_y
    [0, 255, 255], # Cyan for accel_z
    [255, 128, 0], # Orange for gyro_yaw
    [128, 128, 128] # Gray for mag_magnitude
]

# Color names for console output
color_names = [
    "Red",      # Temperature
    "Green",    # Humidity
    "Blue",     # Pressure
    "Yellow",   # Accel_x
    "Magenta",  # Accel_y
    "Cyan",     # Accel_z
    "Orange",   # Gyro_yaw
    "Gray"      # Mag_magnitude
]

# Function to scale sensor value to 0-8 range for LED display
def scale_value(value, min_val, max_val):
    # Ensure value is within bounds
    value = max(min_val, min(value, max_val))
    # Scale to 0-8
    scaled = (value - min_val) / (max_val - min_val) * 8
    return int(round(scaled))

# Function to apply vertical and horizontal flips to pixel array
def apply_flips(pixels, flip_h, flip_v):
    new_pixels = pixels.copy()
    # Convert 1D array (64 pixels) to 2D 8x8 array
    grid = [new_pixels[i:i+8] for i in range(0, 64, 8)]
    # Apply horizontal flip
    if flip_h:
        grid = [row[::-1] for row in grid]
    # Apply vertical flip
    if flip_v:
        grid = grid[::-1]
    # Flatten back to 1D array
    return [pixel for row in grid for pixel in row]

# Function to format and print sensor data with colors and orientation
def print_sensor_data(temperature, humidity, pressure, accel, gyro_z, mag_magnitude, rotation, flip_h, flip_v):
    orientation = f"Rotation: {rotation}°, Flip H: {'On' if flip_h else 'Off'}, Flip V: {'On' if flip_v else 'Off'}"
    print(f"\rTemp ({color_names[0]}): {temperature:.1f}°C, "
          f"Humidity ({color_names[1]}): {humidity:.1f}%, "
          f"Pressure ({color_names[2]}): {pressure:.1f}mbar, "
          f"Accel X ({color_names[3]}): {accel['x']:.2f}g, "
          f"Accel Y ({color_names[4]}): {accel['y']:.2f}g, "
          f"Accel Z ({color_names[5]}): {accel['z']:.2f}g, "
          f"Gyro Z ({color_names[6]}): {gyro_z:.2f}rad/s, "
          f"Mag ({color_names[7]}): {mag_magnitude:.1f}uT, "
          f"{orientation}", end='')

# Initialize orientation state
rotation = 0  # 0, 90, 180, 270 degrees
flip_h = False  # Horizontal flip
flip_v = False  # Vertical flip

# Main loop
while True:
    # Handle joystick events
    for event in sense.stick.get_events():
        if event.action == "pressed":
            if event.direction == "up":
                flip_v = not flip_v  # Toggle vertical flip
            elif event.direction == "down":
                flip_v = not flip_v  # Toggle vertical flip (same as up for simplicity)
            elif event.direction == "left":
                flip_h = not flip_h  # Toggle horizontal flip
            elif event.direction == "right":
                flip_h = not flip_h  # Toggle horizontal flip (same as left)
            elif event.direction == "middle":
                # Reset orientation
                rotation = 0
                flip_h = False
                flip_v = False

    # Get sensor readings
    temperature = sense.get_temperature()  # in Celsius (0 to 50 typical)
    humidity = sense.get_humidity()        # in % (0 to 100)
    pressure = sense.get_pressure()        # in millibars (950 to 1050 typical)
    accel = sense.get_accelerometer_raw()  # in g (-2 to 2)
    gyro = sense.get_gyroscope_raw()       # in radians/s (-10 to 10)
    mag = sense.get_compass_raw()          # in microteslas (-50 to 50 per axis)

    # Calculate magnetometer magnitude
    mag_magnitude = math.sqrt(mag['x']**2 + mag['y']**2 + mag['z']**2)

    # Print sensor data to console with colors and orientation
    print_sensor_data(temperature, humidity, pressure, accel, gyro['z'], mag_magnitude, rotation, flip_h, flip_v)

    # Scale sensor values to 0-8
    sensor_values = [
        scale_value(temperature, 0, 50),      # Temperature: 0-50°C
        scale_value(humidity, 0, 100),        # Humidity: 0-100%
        scale_value(pressure, 950, 1050),     # Pressure: 950-1050 mbar
        scale_value(accel['x'], -2, 2),       # Accel x: -2 to 2g
        scale_value(accel['y'], -2, 2),       # Accel y: -2 to 2g
        scale_value(accel['z'], -2, 2),       # Accel z: -2 to 2g
        scale_value(gyro['z'], -10, 10),      # Gyro yaw (z-axis): -10 to 10 rad/s
        scale_value(mag_magnitude, 0, 100)    # Mag magnitude: 0-100 uT
    ]

    # Create 8x8 pixel array
    pixels = []
    for row in range(8):
        sensor_val = sensor_values[row]
        color = colors[row]
        # Create row: light up LEDs up to sensor value
        row_pixels = [color if col < sensor_val else [0, 0, 0] for col in range(8)]
        pixels.extend(row_pixels)

    # Apply horizontal and vertical flips
    pixels = apply_flips(pixels, flip_h, flip_v)

    # Set rotation
    sense.set_rotation(rotation)

    # Update LED matrix
    sense.set_pixels(pixels)

    # Small delay to avoid overwhelming the display
    time.sleep(0.5)