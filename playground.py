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
def atmosphere_correction(bc, temp_c, humidity, pressure_inhg, altitude_ft):
    """Adjust ballistic coefficient for environmental conditions."""
    temp_k = temp_c + 273.15
    std_temp_k = 15 + 273.15
    if pressure_inhg == 29.92 and altitude_ft != 0:
        pressure_inhg = 29.92 * math.exp(-altitude_ft / 30000)
    pressure_pa = pressure_inhg * 3386.39
    air_density = (pressure_pa / (287.05 * temp_k)) * (1 - 0.0065 * temp_c / 288.15) ** 4.255
    std_air_density = (101325 / (287.05 * std_temp_k)) * (1 - 0.0065 * 15 / 288.15) ** 4.255
    density_factor = std_air_density / air_density
    humidity_factor = 1 - (humidity / 100) * 0.02
    corrected_bc = bc * density_factor * humidity_factor
    return corrected_bc, pressure_inhg

def calculate_spin_drift(bullet_weight_grains, barrel_twist_in, range_yards, velocity_fps):
    """Calculate spin drift."""
    bullet_mass_kg = bullet_weight_grains / 7000 * 0.453592
    range_m = range_yards * 0.9144
    velocity_ms = velocity_fps * 0.3048
    twist_rate = 1 / barrel_twist_in
    spin_velocity = velocity_ms * twist_rate * 0.0254
    drift_m = 1.25 * (bullet_mass_kg / 0.01) * (range_m / 1000) ** 2 / (velocity_ms / 300) * (twist_rate / 0.1)
    return drift_m * 39.3701

def calculate_wind_drift(wind_speed_mph, wind_direction_deg, time_of_flight, range_yards):
    """Calculate lateral drift due to wind."""
    wind_speed_ms = wind_speed_mph * 0.44704
    crosswind = wind_speed_ms * math.sin(math.radians(wind_direction_deg))
    drift_m = crosswind * time_of_flight
    drift_in = drift_m * 39.3701
    moa = (drift_in / (range_yards / 100)) / 1.047
    mrad = (drift_in / (range_yards / 100)) / 3.6
    return drift_in, moa, mrad

def calculate_trajectory(velocity_fps, bc, bullet_weight_grains, range_yards, zero_range_yards, scope_height_in, temp_c, humidity, pressure_inhg, altitude_ft, target_angle_deg, drag_model, wind_speed_mph, wind_direction_deg, barrel_twist_in):
    """Calculate bullet drop, velocity, energy, and scope adjustments."""
    velocity = velocity_fps * 0.3048
    range_m = range_yards * 0.9144
    zero_range_m = zero_range_yards * 0.9144
    scope_height_m = scope_height_in * 0.0254
    bullet_mass = bullet_weight_grains / 7000 * 0.453592
    bullet_area = 0.000506707  # Approx. for .308 bullet
    target_angle_rad = math.radians(target_angle_deg)

    corrected_bc, adjusted_pressure = atmosphere_correction(bc, temp_c, humidity, pressure_inhg, altitude_ft)
    drag_coeff = 0.5 if drag_model == "G1" else 0.25
    air_density = (adjusted_pressure * 3386.39) / (287.05 * (temp_c + 273.15))

    time_of_flight = range_m / velocity
    velocity_at_range = velocity * math.exp(-drag_coeff * air_density * bullet_area * range_m / (2 * bullet_mass * corrected_bc))
    time_of_flight = range_m / ((velocity + velocity_at_range) / 2)

    velocity_at_range_fps = velocity_at_range / 0.3048
    energy_joules = 0.5 * bullet_mass * velocity_at_range ** 2
    energy_ftlbs = energy_joules / 1.35582

    g = 9.81
    drop_m = (0.5 * g * time_of_flight ** 2) * math.cos(target_angle_rad)
    zero_angle = math.atan2(drop_m + scope_height_m, zero_range_m)
    adjusted_drop_m = drop_m - range_m * math.tan(zero_angle) + scope_height_m
    drop_in = adjusted_drop_m * 39.3701

    moa_adjustment = (drop_in / (range_yards / 100)) / 1.047
    mrad_adjustment = (drop_in / (range_yards / 100)) / 3.6

    wind_drift_in, wind_moa, wind_mrad = calculate_wind_drift(wind_speed_mph, wind_direction_deg, time_of_flight, range_yards)
    spin_drift_in = calculate_spin_drift(bullet_weight_grains, barrel_twist_in, range_yards, velocity_fps)
    total_lateral_drift_in = wind_drift_in + spin_drift_in
    total_lateral_moa = (total_lateral_drift_in / (range_yards / 100)) / 1.047
    total_lateral_mrad = (total_lateral_drift_in / (range_yards / 100)) / 3.6

    return drop_in, velocity_at_range_fps, energy_ftlbs, moa_adjustment, mrad_adjustment, total_lateral_drift_in, total_lateral_moa, total_lateral_mrad

# GUI Application
class BallisticCalculator(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("Ballistic Calculator")
        self.geometry("800x480")
        self.attributes("-fullscreen", False)
        self.sense = sense
        self.running = True

        # Variables
        self.velocity_var = tk.StringVar(value="3000")
        self.bc_var = tk.StringVar(value="0.225")
        self.bullet_weight_var = tk.StringVar(value="150")
        self.range_var = tk.StringVar(value="100")
        self.zero_range_var = tk.StringVar(value="100")
        self.scope_height_var = tk.StringVar(value="1.5")
        self.wind_speed_var = tk.StringVar(value="10")
        self.wind_direction_var = tk.StringVar(value="90")
        self.barrel_twist_var = tk.StringVar(value="10")
        self.target_size_var = tk.StringVar(value="10")
        self.target_angle_var = tk.StringVar(value="0")
        self.altitude_var = tk.StringVar(value="0")
        self.temp_var = tk.StringVar(value="N/A")
        self.humidity_var = tk.StringVar(value="N/A")
        self.pressure_var = tk.StringVar(value="N/A")
        self.drop_var = tk.StringVar(value="0.00")
        self.velocity_at_range_var = tk.StringVar(value="0.00")
        self.energy_var = tk.StringVar(value="0.00")
        self.moa_var = tk.StringVar(value="0.00")
        self.mrad_var = tk.StringVar(value="0.00")
        self.lateral_drift_var = tk.StringVar(value="0.00")
        self.lateral_moa_var = tk.StringVar(value="0.00")
        self.lateral_mrad_var = tk.StringVar(value="0.00")
        self.drag_model_var = tk.StringVar(value="G7")

        # GUI Layout
        self.create_widgets()

        # Start sensor polling thread
        self.sensor_thread = threading.Thread(target=self.poll_sensors, daemon=True)
        self.sensor_thread.start()

    def create_widgets(self):
        # Main container
        main_container = ttk.Frame(self, padding="10")
        main_container.grid(row=0, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))
        self.columnconfigure(0, weight=1)
        self.rowconfigure(0, weight=1)

        # Quadrants
        rifle_frame = ttk.LabelFrame(main_container, text="Rifle Details", padding="5")
        rifle_frame.grid(row=0, column=0, sticky=(tk.W, tk.E, tk.N, tk.S), padx=5, pady=5)

        bullet_frame = ttk.LabelFrame(main_container, text="Bullet Details", padding="5")
        bullet_frame.grid(row=0, column=1, sticky=(tk.W, tk.E, tk.N, tk.S), padx=5, pady=5)

        env_frame = ttk.LabelFrame(main_container, text="Environment Details", padding="5")
        env_frame.grid(row=1, column=0, sticky=(tk.W, tk.E, tk.N, tk.S), padx=5, pady=5)

        result_frame = ttk.LabelFrame(main_container, text="Resulting Calculations", padding="5")
        result_frame.grid(row=1, column=1, sticky=(tk.W, tk.E, tk.N, tk.S), padx=5, pady=5)

        # Configure grid weights
        main_container.columnconfigure(0, weight=1)
        main_container.columnconfigure(1, weight=1)
        main_container.rowconfigure(0, weight=1)
        main_container.rowconfigure(1, weight=1)

        # Rifle Details (Top Left)
        ttk.Label(rifle_frame, text="Scope Height (in):").grid(row=0, column=0, sticky=tk.W)
        ttk.Entry(rifle_frame, textvariable=self.scope_height_var).grid(row=0, column=1, sticky=(tk.W, tk.E))

        ttk.Label(rifle_frame, text="Zero Range (yd):").grid(row=1, column=0, sticky=tk.W)
        ttk.Entry(rifle_frame, textvariable=self.zero_range_var).grid(row=1, column=1, sticky=(tk.W, tk.E))

        ttk.Label(rifle_frame, text="Barrel Twist (in/turn):").grid(row=2, column=0, sticky=tk.W)
        ttk.Entry(rifle_frame, textvariable=self.barrel_twist_var).grid(row=2, column=1, sticky=(tk.W, tk.E))

        rifle_frame.columnconfigure(1, weight=1)

        # Bullet Details (Top Right)
        ttk.Label(bullet_frame, text="Muzzle Velocity (fps):").grid(row=0, column=0, sticky=tk.W)
        ttk.Entry(bullet_frame, textvariable=self.velocity_var).grid(row=0, column=1, sticky=(tk.W, tk.E))

        ttk.Label(bullet_frame, text="Ballistic Coefficient:").grid(row=1, column=0, sticky=tk.W)
        ttk.Entry(bullet_frame, textvariable=self.bc_var).grid(row=1, column=1, sticky=(tk.W, tk.E))

        ttk.Label(bullet_frame, text="Bullet Weight (gr):").grid(row=2, column=0, sticky=tk.W)
        ttk.Entry(bullet_frame, textvariable=self.bullet_weight_var).grid(row=2, column=1, sticky=(tk.W, tk.E))

        ttk.Label(bullet_frame, text="Drag Model:").grid(row=3, column=0, sticky=tk.W)
        ttk.Radiobutton(bullet_frame, text="G1", variable=self.drag_model_var, value="G1").grid(row=3, column=1, sticky=tk.W)
        ttk.Radiobutton(bullet_frame, text="G7", variable=self.drag_model_var, value="G7").grid(row=3, column=1, sticky=tk.E)

        bullet_frame.columnconfigure(1, weight=1)

        # Environment Details (Bottom Left)
        ttk.Label(env_frame, text="Range (yd):").grid(row=0, column=0, sticky=tk.W)
        ttk.Entry(env_frame, textvariable=self.range_var).grid(row=0, column=1, sticky=(tk.W, tk.E))

        ttk.Label(env_frame, text="Target Size (in):").grid(row=1, column=0, sticky=tk.W)
        ttk.Entry(env_frame, textvariable=self.target_size_var).grid(row=1, column=1, sticky=(tk.W, tk.E))

        ttk.Label(env_frame, text="Target Angle (deg):").grid(row=2, column=0, sticky=tk.W)
        ttk.Entry(env_frame, textvariable=self.target_angle_var).grid(row=2, column=1, sticky=(tk.W, tk.E))

        ttk.Label(env_frame, text="Wind Speed (mph):").grid(row=3, column=0, sticky=tk.W)
        ttk.Entry(env_frame, textvariable=self.wind_speed_var).grid(row=3, column=1, sticky=(tk.W, tk.E))

        ttk.Label(env_frame, text="Wind Direction (deg):").grid(row=4, column=0, sticky=tk.W)
        ttk.Entry(env_frame, textvariable=self.wind_direction_var).grid(row=4, column=1, sticky=(tk.W, tk.E))

        ttk.Label(env_frame, text="Altitude (ft):").grid(row=5, column=0, sticky=tk.W)
        ttk.Entry(env_frame, textvariable=self.altitude_var).grid(row=5, column=1, sticky=(tk.W, tk.E))

        ttk.Label(env_frame, text="Temperature (°C):").grid(row=6, column=0, sticky=tk.W)
        ttk.Label(env_frame, textvariable=self.temp_var).grid(row=6, column=1, sticky=tk.W)

        ttk.Label(env_frame, text="Humidity (%):").grid(row=7, column=0, sticky=tk.W)
        ttk.Label(env_frame, textvariable=self.humidity_var).grid(row=7, column=1, sticky=tk.W)

        ttk.Label(env_frame, text="Pressure (inHg):").grid(row=8, column=0, sticky=tk.W)
        ttk.Label(env_frame, textvariable=self.pressure_var).grid(row=8, column=1, sticky=tk.W)

        env_frame.columnconfigure(1, weight=1)

        # Resulting Calculations (Bottom Right)
        ttk.Label(result_frame, text="Bullet Drop (in):").grid(row=0, column=0, sticky=tk.W)
        ttk.Label(result_frame, textvariable=self.drop_var).grid(row=0, column=1, sticky=tk.W)

        ttk.Label(result_frame, text="Velocity at Range (fps):").grid(row=1, column=0, sticky=tk.W)
        ttk.Label(result_frame, textvariable=self.velocity_at_range_var).grid(row=1, column=1, sticky=tk.W)

        ttk.Label(result_frame, text="Energy at Range (ft-lbs):").grid(row=2, column=0, sticky=tk.W)
        ttk.Label(result_frame, textvariable=self.energy_var).grid(row=2, column=1, sticky=tk.W)

        ttk.Label(result_frame, text="Elevation Adjustment (MOA):").grid(row=3, column=0, sticky=tk.W)
        ttk.Label(result_frame, textvariable=self.moa_var).grid(row=3, column=1, sticky=tk.W)

        ttk.Label(result_frame, text="Elevation Adjustment (MRAD):").grid(row=4, column=0, sticky=tk.W)
        ttk.Label(result_frame, textvariable=self.mrad_var).grid(row=4, column=1, sticky=tk.W)

        ttk.Label(result_frame, text="Lateral Drift (in):").grid(row=5, column=0, sticky=tk.W)
        ttk.Label(result_frame, textvariable=self.lateral_drift_var).grid(row=5, column=1, sticky=tk.W)

        ttk.Label(result_frame, text="Windage Adjustment (MOA):").grid(row=6, column=0, sticky=tk.W)
        ttk.Label(result_frame, textvariable=self.lateral_moa_var).grid(row=6, column=1, sticky=tk.W)

        ttk.Label(result_frame, text="Windage Adjustment (MRAD):").grid(row=7, column=0, sticky=tk.W)
        ttk.Label(result_frame, textvariable=self.lateral_mrad_var).grid(row=7, column=1, sticky=tk.W)

        result_frame.columnconfigure(1, weight=1)

        # Calculate button
        ttk.Button(main_container, text="Calculate", command=self.calculate).grid(row=2, column=0, columnspan=2, pady=10)

    def poll_sense_grid(self, drop_in, lateral_drift_in):
        """Update Sense HAT 8x8 grid to show bullet impact point."""
        self.sense.clear()
        # Scale 8x8 grid to 16x16 inches (2 in per pixel)
        scale = 2.0
        x = int(lateral_drift_in / scale) + 4  # Center at x=4
        y = int(-drop_in / scale) + 4  # Center at y=4, negative drop (down)
        if 0 <= x < 8 and 0 <= y < 8:
            self.sense.set_pixel(x, y, 255, 0, 0)  # Red pixel for impact
        else:
            # Flash red if impact is off target
            for _ in range(2):
                self.sense.clear(255, 0, 0)
                time.sleep(0.5)
                self.sense.clear()
                time.sleep(0.5)

    def poll_sensors(self):
        """Continuously poll Sense HAT sensors and update GUI."""
        while self.running:
            try:
                temp_c = self.sense.get_temperature()
                humidity = self.sense.get_humidity()
                pressure_mb = self.sense.get_pressure()
                pressure_inhg = pressure_mb * 0.02953
                self.temp_var.set(f"{temp_c:.1f}")
                self.humidity_var.set(f"{humidity:.1f}")
                self.pressure_var.set(f"{pressure_inhg:.2f}")
            except Exception as e:
                self.temp_var.set("Error")
                self.humidity_var.set("Error")
                self.pressure_var.set("Error")
                print(f"Sensor error: {e}")
            time.sleep(2)

    def calculate(self):
        """Perform ballistic calculation based on inputs."""
        try:
            velocity = float(self.velocity_var.get())
            bc = float(self.bc_var.get())
            bullet_weight = float(self.bullet_weight_var.get())
            range_yards = float(self.range_var.get())
            zero_range_yards = float(self.zero_range_var.get())
            scope_height = float(self.scope_height_var.get())
            wind_speed = float(self.wind_speed_var.get())
            wind_direction = float(self.wind_direction_var.get())
            barrel_twist = float(self.barrel_twist_var.get())
            target_size = float(self.target_size_var.get())
            target_angle = float(self.target_angle_var.get())
            altitude = float(self.altitude_var.get())
            temp_c = float(self.temp_var.get()) if self.temp_var.get() != "Error" else 15.0
            humidity = float(self.humidity_var.get()) if self.humidity_var.get() != "Error" else 0.0
            pressure_inhg = float(self.pressure_var.get()) if self.pressure_var.get() != "Error" else 29.92
            drag_model = self.drag_model_var.get()

            # Input validation
            if any(x <= 0 for x in [velocity, bc, bullet_weight, zero_range_yards, scope_height, barrel_twist, target_size]):
                raise ValueError("Inputs must be positive (except range, angles, wind, altitude).")
            if not 0 <= wind_direction <= 360:
                raise ValueError("Wind direction must be between 0 and 360 degrees.")
            if not 0.05 <= bc <= 1.0:
                raise ValueError("Ballistic coefficient must be between 0.05 and 1.0.")
            if range_yards < 0:
                raise ValueError("Range must be non-negative.")
            if abs(target_angle) > 90:
                raise ValueError("Target angle must be between -90 and 90 degrees.")

            drop, velocity_at_range, energy, moa, mrad, lateral_drift, lateral_moa, lateral_mrad = calculate_trajectory(
                velocity, bc, bullet_weight, range_yards, zero_range_yards, scope_height, temp_c, humidity, pressure_inhg, altitude, target_angle, drag_model, wind_speed, wind_direction, barrel_twist
            )
            self.drop_var.set(f"{drop:.2f}")
            self.velocity_at_range_var.set(f"{velocity_at_range:.2f}")
            self.energy_var.set(f"{energy:.2f}")
            self.moa_var.set(f"{moa:.2f}")
            self.mrad_var.set(f"{mrad:.2f}")
            self.lateral_drift_var.set(f"{lateral_drift:.2f}")
            self.lateral_moa_var.set(f"{lateral_moa:.2f}")
            self.lateral_mrad_var.set(f"{lateral_mrad:.2f}")

            # Update Sense HAT grid
            self.poll_sense_grid(drop, lateral_drift)

            # Validate target size
            if abs(drop) > target_size:
                messagebox.showwarning("Target Warning", f"Bullet drop ({abs(drop):.2f} in) exceeds target size ({target_size:.2f} in).")
            if abs(lateral_drift) > target_size:
                messagebox.showwarning("Target Warning", f"Lateral drift ({abs(lateral_drift):.2f} in) exceeds target size ({target_size:.2f} in).")
        except ValueError as e:
            messagebox.showerror("Input Error", str(e))
            self.sense.clear()

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