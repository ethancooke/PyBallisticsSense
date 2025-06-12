import tkinter as tk
from tkinter import ttk, messagebox
import threading
import time
import json
from ballistics import convert_temperature, convert_distance, calculate_trajectory
from sensehat_io import SenseHatIO

class BallisticCalculator(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("Ballistic Calculator")
        self.geometry("800x480")
        self.attributes("-fullscreen", False)
        self.sensehat = SenseHatIO()
        self.running = True

        with open("defaults.json", "r") as f:
            defaults = json.load(f)

        self._init_vars(defaults)
        self.create_widgets()
        self.sensor_thread = threading.Thread(target=self.poll_sensors, daemon=True)
        self.sensor_thread.start()

    def _init_vars(self, defaults):
        self.vars = {}
        var_map = {
            'rifle': ["scope_height", "zero_range", "barrel_twist"],
            'bullet': ["velocity", "bc", "weight", "drag_model"],
            'environment_user': ["range", "target_size", "target_angle", "wind_speed", "wind_direction", "altitude"],
            'environment_sensor': ["temp", "humidity", "pressure"],
            'output': ["drop", "velocity_at_range", "energy", "moa", "mrad", "lateral_drift", "lateral_moa", "lateral_mrad"],
            'units': ["temp_unit", "dist_unit"]
        }
        for section, keys in var_map.items():
            for key in keys:
                value = str(defaults[section][key]) if section in defaults and key in defaults[section] else ""
                self.vars[key] = tk.StringVar(value=value)
        # Rifle
        self.rifle_scope_height = self.vars["scope_height"]
        self.rifle_zero_range = self.vars["zero_range"]
        self.rifle_barrel_twist = self.vars["barrel_twist"]
        # Bullet
        self.bullet_velocity = self.vars["velocity"]
        self.bullet_bc = self.vars["bc"]
        self.bullet_weight = self.vars["weight"]
        self.bullet_drag_model = self.vars["drag_model"]
        # Environment (User Input)
        self.env_range = self.vars["range"]
        self.env_target_size = self.vars["target_size"]
        self.env_target_angle = self.vars["target_angle"]
        self.env_wind_speed = self.vars["wind_speed"]
        self.env_wind_direction = self.vars["wind_direction"]
        self.env_altitude = self.vars["altitude"]
        # Environment (Sensors)
        self.env_temp = self.vars["temp"]
        self.env_humidity = self.vars["humidity"]
        self.env_pressure = self.vars["pressure"]
        # Output/Results
        self.result_drop = self.vars["drop"]
        self.result_velocity_at_range = self.vars["velocity_at_range"]
        self.result_energy = self.vars["energy"]
        self.result_moa = self.vars["moa"]
        self.result_mrad = self.vars["mrad"]
        self.result_lateral_drift = self.vars["lateral_drift"]
        self.result_lateral_moa = self.vars["lateral_moa"]
        self.result_lateral_mrad = self.vars["lateral_mrad"]
        # Units
        self.unit_temp = self.vars["temp_unit"]
        self.unit_dist = self.vars["dist_unit"]

    def create_widgets(self):
        # ...existing code for widget creation, using the new variable names...
        pass

    def update_units(self):
        use_celsius = self.unit_temp.get() == "°C"
        use_meters = self.unit_dist.get() == "Meters"
        try:
            if self.env_temp.get() != "N/A" and self.env_temp.get() != "Error":
                temp = float(self.env_temp.get())
                self.env_temp.set(f"{convert_temperature(temp, use_celsius):.1f}")
            for var in [self.env_range, self.rifle_zero_range]:
                if var.get() and var.get() != "Error":
                    value = float(var.get())
                    new_value = convert_distance(value, use_meters)
                    var.set(f"{new_value:.2f}")
            for var in [self.rifle_scope_height, self.env_target_size, self.result_drop, self.result_lateral_drift]:
                if var.get() and var.get() != "Error" and var.get() != "0.00":
                    value = float(var.get())
                    new_value = convert_distance(value, use_meters, is_height=True)
                    var.set(f"{new_value:.2f}")
        except ValueError:
            pass

    def poll_sensors(self):
        while self.running:
            try:
                use_celsius = self.unit_temp.get() == "°C"
                env = self.sensehat.read_environment(use_celsius)
                self.env_temp.set(f"{env['temp']:.1f}")
                self.env_humidity.set(f"{env['humidity']:.1f}")
                self.env_pressure.set(f"{env['pressure']:.2f}")
            except Exception as e:
                self.env_temp.set("Error")
                self.env_humidity.set("Error")
                self.env_pressure.set("Error")
                print(f"Sensor error: {e}")
            time.sleep(2)

    def calculate(self):
        try:
            with open("defaults.json", "r") as f:
                defaults = json.load(f)
            zero_env = defaults.get("zero_environment", None)
            velocity = float(self.bullet_velocity.get())
            bc = float(self.bullet_bc.get())
            bullet_weight = float(self.bullet_weight.get())
            range_ = float(self.env_range.get())
            zero_range = float(self.rifle_zero_range.get())
            scope_height = float(self.rifle_scope_height.get())
            wind_speed = float(self.env_wind_speed.get())
            wind_direction = float(self.env_wind_direction.get())
            barrel_twist = float(self.rifle_barrel_twist.get())
            target_size = float(self.env_target_size.get())
            target_angle = float(self.env_target_angle.get())
            altitude = float(self.env_altitude.get())
            temp = float(self.env_temp.get()) if self.env_temp.get() != "Error" else (15.0 if self.unit_temp.get() == "°C" else 59.0)
            humidity = float(self.env_humidity.get()) if self.env_humidity.get() != "Error" else 0.0
            pressure_inhg = float(self.env_pressure.get()) if self.env_pressure.get() != "Error" else 29.92
            drag_model = self.bullet_drag_model.get()
            use_celsius = self.unit_temp.get() == "°C"
            use_meters = self.unit_dist.get() == "Meters"
            if any(x <= 0 for x in [velocity, bc, bullet_weight, zero_range, scope_height, barrel_twist, target_size]):
                raise ValueError("Inputs must be positive (except range, angles, wind, altitude).")
            if not 0 <= wind_direction <= 360:
                raise ValueError("Wind direction must be between 0 and 360 degrees.")
            if not 0.05 <= bc <= 1.0:
                raise ValueError("Ballistic coefficient must be between 0.05 and 1.0.")
            if range_ < 0:
                raise ValueError("Range must be non-negative.")
            if abs(target_angle) > 90:
                raise ValueError("Target angle must be between -90 and 90 degrees.")
            drop, velocity_at_range, energy, moa, mrad, lateral_drift, lateral_moa, lateral_mrad = calculate_trajectory(
                velocity, bc, bullet_weight, range_, zero_range, scope_height, temp, humidity, pressure_inhg, altitude, target_angle, drag_model, wind_speed, wind_direction, barrel_twist, use_meters, use_celsius, zero_env
            )
            self.result_drop.set(f"{drop:.2f}")
            self.result_velocity_at_range.set(f"{velocity_at_range:.2f}")
            self.result_energy.set(f"{energy:.2f}")
            self.result_moa.set(f"{moa:.2f}")
            self.result_mrad.set(f"{mrad:.2f}")
            self.result_lateral_drift.set(f"{lateral_drift:.2f}")
            self.result_lateral_moa.set(f"{lateral_moa:.2f}")
            self.result_lateral_mrad.set(f"{lateral_mrad:.2f}")
        except ValueError as e:
            messagebox.showerror("Input Error", str(e))
            self.sensehat.clear()

    def destroy(self):
        self.running = False
        self.sensehat.clear()
        super().destroy()

if __name__ == "__main__":
    try:
        app = BallisticCalculator()
        app.mainloop()
    except KeyboardInterrupt:
        app.destroy()
