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

# Function to scale sensor value to 0-8 range for LED display
def scale_value(value, min_val, max_val):
    # Ensure value is within bounds
    value = max(min_val, min(value, max_val))
    # Scale to 0-8
    scaled = (value - min_val) / (max_val - min_val) * 8
    return int(round(scaled))

# Main loop
while True:
    # Get sensor readings
    temperature = sense.get_temperature()  # in Celsius (0 to 50 typical)
    humidity = sense.get_humidity()        # in % (0 to 100)
    pressure = sense.get_pressure()        # in millibars (950 to 1050 typical)
    accel = sense.get_accelerometer_raw()  # in g (-2 to 2)
    gyro = sense.get_gyroscope_raw()       # in radians/s (-10 to 10)
    mag = sense.get_compass_raw()          # in microteslas (-50 to 50 per axis)

    # Calculate magnetometer magnitude
    mag_magnitude = math.sqrt(mag['x']**2 + mag['y']**2 + mag['z']**2)

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

    # Update LED matrix
    sense.set_pixels(pixels)

    # Small delay to avoid overwhelming the display
    time.sleep(0.5)