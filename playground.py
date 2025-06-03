#!/usr/bin/python3
import tkinter as tk
from tkinter import ttk, messagebox
from sense_hat import SenseHat
import threading
import time
import math

# Initialize Sense HAT
sense = SenseHat()
sense.clear()

# Ballistic calculation functions
def atmosphere_correction(bc, temp_c, humidity, pressure=29.92):
    """Adjust ballistic coefficient for environmental conditions."""
    # Standard conditions: 59°F (15°C), 0% humidity, 29.92 inHg
    temp_k = temp_c + 273.15
    std_temp_k = 15 + 273.15
    # Simplified correction factor (approximate)
    temp_factor = std_temp_k / temp_k
    humidity_factor = 1 - (humidity / 100) * 0.02  # Humidity reduces air density slightly
    corrected_bc = bc * temp_factor * humidity_factor
    return corrected_bc

def calculate_trajectory(velocity_fps, bc, bullet_weight_grains, range_yards, zero_range_yards, temp_c, humidity):
    """Calculate bullet drop and velocity at range using point-mass model."""
    # Convert inputs
    velocity = velocity_fps * 0.3048  # Convert fps to m/s
    range_m = range_yards * 0.9144  # Convert yards to meters
    zero_range_m = zero_range_yards * 0.9144  # Convert yards to meters

    # Adjust BC for environment
    corrected_bc = atmosphere_correction(bc, temp_c, humidity)

    # Simplified drag model (G1 approximation)
    drag_coeff = 0.5  # Approximate for G1 drag model
    air_density = 1.225 * (1 - 0.0065 * temp_c / 288.15) ** 4.255  # Approximate air density
    bullet_mass = bullet_weight_grains / 7000 * 0.453592  # Convert grains to kg
    bullet_area = 0.000506707  # Approx. cross-sectional area for .308 bullet (m^2)

    # Time of flight
    time_of_flight = range_m / velocity  # Simplified, ignoring drag slowdown

    # Velocity at range (simplified exponential decay)
    velocity_at_range = velocity * math.exp(-drag_coeff * air_density * bullet_area * range_m / (2 * bullet_mass * corrected_bc))
    velocity_at_range_fps = velocity_at_range / 0.3048  # Convert back to fps

    # Bullet drop (gravity and zero adjustment)
    g = 9.81  # Gravity (m/s^2)
    drop_m = (0.5 * g * time_of_flight ** 2)  # Drop due to gravity
    # Adjust for zero range (simplified, assumes flat-fire approximation)
    zero_angle = math.atan2(drop_m, zero_range_m)
    adjusted_drop_m = drop_m - range_m * math.tan(zero_angle)
    drop_in = adjusted_drop_m * 39.3701  # Convert meters to inches

    return drop_in, velocity_at_range_fps

# GUI Application
class BallisticCalculator(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("Ballistic Calculator")
        self.geometry("800x480")  # Optimized for Raspberry Pi 7" display
        self.attributes("-fullscreen", False)  # Set to True for fullscreen
        self.sense = sense
        self.running = True

        # Variables
        self.velocity_var = tk.StringVar(value="3000")  # Default muzzle velocity (fps)
        self.bc_var = tk.StringVar(value="0.45")  # Default ballistic coefficient (G1)
        self.bullet_weight_var = tk.StringVar(value="150")  # Default bullet weight (grains)
        self.range_var = tk.StringVar(value="100")  # Default range (yards)
        self.zero_range_var = tk.StringVar(value="100")  # Default zero range (yards)
        self.temp_var = tk.StringVar(value="N/A")
        self.humidity_var = tk.StringVar(value="N/A")
        self.drop_var = tk.StringVar(value="0.00")
        self.velocity_at_range_var = tk.StringVar(value="0.00")

        # GUI Layout
        self.create_widgets()

        # Start sensor polling thread
        self.sensor_thread = threading.Thread(target=self.poll_sensors, daemon=True)
        self.sensor_thread.start()

    def create_widgets(self):
        # Main frame
        main_frame = ttk.Frame(self, padding="10")
        main_frame.grid(row=0, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))

        # Input fields
        ttk.Label(main_frame, text="Muzzle Velocity (fps):").grid(row=0, column=0, sticky=tk.W)
        ttk.Entry(main_frame, textvariable=self.velocity_var).grid(row=0, column=1, sticky=(tk.W, tk.E))

        ttk.Label(main_frame, text="Ballistic Coefficient (G1):").grid(row=1, column=0, sticky=tk.W)
        ttk.Entry(main_frame, textvariable=self.bc_var).grid(row=1, column=1, sticky=(tk.W, tk.E))

        ttk.Label(main_frame, text="Bullet Weight (grains):").grid(row=2, column=0, sticky=tk.W)
        ttk.Entry(main_frame, textvariable=self.bullet_weight_var).grid(row=2, column=1, sticky=(tk.W, tk.E))

        ttk.Label(main_frame, text="Range (yards):").grid(row=3, column=0, sticky=tk.W)
        ttk.Entry(main_frame, textvariable=self.range_var).grid(row=3, column=1, sticky=(tk.W, tk.E))

        ttk.Label(main_frame, text="Zero Range (yards):").grid(row=4, column=0, sticky=tk.W)
        ttk.Entry(main_frame, textvariable=self.zero_range_var).grid(row=4, column=1, sticky=(tk.W, tk.E))

        # Sensor fields (read-only)
        ttk.Label(main_frame, text="Temperature (°C):").grid(row=5, column=0, sticky=tk.W)
        ttk.Label(main_frame, textvariable=self.temp_var).grid(row=5, column=1, sticky=tk.W)

        ttk.Label(main_frame, text="Humidity (%):").grid(row=6, column=0, sticky=tk.W)
        ttk.Label(main_frame, textvariable=self.humidity_var).grid(row=6, column=1, sticky=tk.W)

        # Output fields
        ttk.Label(main_frame, text="Bullet Drop (inches):").grid(row=7, column=0, sticky=tk.W)
        ttk.Label(main_frame, textvariable=self.drop_var).grid(row=7, column=1, sticky=tk.W)

        ttk.Label(main_frame, text="Velocity at Range (fps):").grid(row=8, column=0, sticky=tk.W)
        ttk.Label(main_frame, textvariable=self.velocity_at_range_var).grid(row=8, column=1, sticky=tk.W)

        # Calculate button
        ttk.Button(main_frame, text="Calculate", command=self.calculate).grid(row=9, column=0, columnspan=2, pady=10)

        # Configure grid weights
        main_frame.columnconfigure(1, weight=1)
        for i in range(10):
            main_frame.rowconfigure(i, weight=1)

    def poll_sensors(self):
        """Continuously poll Sense HAT sensors and update GUI."""
        while self.running:
            try:
                temp_c = self.sense.get_temperature()
                humidity = self.sense.get_humidity()
                self.temp_var.set(f"{temp_c:.1f}")
                self.humidity_var.set(f"{humidity:.1f}")
            except Exception as e:
                self.temp_var.set("Error")
                self.humidity_var.set("Error")
                print(f"Sensor error: {e}")
            time.sleep(2)  # Poll every 2 seconds

    def calculate(self):
        """Perform ballistic calculation based on inputs."""
        try:
            velocity = float(self.velocity_var.get())
            bc = float(self.bc_var.get())
            bullet_weight = float(self.bullet_weight_var.get())
            range_yards = float(self.range_var.get())
            zero_range_yards = float(self.zero_range_var.get())
            temp_c = float(self.temp_var.get()) if self.temp_var.get() != "Error" else 15.0
            humidity = float(self.humidity_var.get()) if self.humidity_var.get() != "Error" else 0.0

            if velocity <= 0 or bc <= 0 or bullet_weight <= 0 or range_yards < 0 or zero_range_yards <= 0:
                raise ValueError("Inputs must be positive numbers (except range).")

            drop, velocity_at_range = calculate_trajectory(
                velocity, bc, bullet_weight, range_yards, zero_range_yards, temp_c, humidity
            )
            self.drop_var.set(f"{drop:.2f}")
            self.velocity_at_range_var.set(f"{velocity_at_range:.2f}")
        except ValueError as e:
            messagebox.showerror("Input Error", str(e))

    def destroy(self):
        """Clean up on exit."""
        self.running = False
        self.sense.clear()
        super().destroy()

# Run the application
if __name__ == "__main__":
    try:
        app = BallisticCalculator()
        app.mainloop()
    except KeyboardInterrupt:
        app.destroy()