from sense_hat import SenseHat

class SenseHatIO:
    def __init__(self):
        self.sense = SenseHat()
        self.sense.clear()

    def read_environment(self, use_celsius=True):
        temp_c = self.sense.get_temperature()
        humidity = self.sense.get_humidity()
        pressure_mb = self.sense.get_pressure()
        pressure_inhg = pressure_mb * 0.02953
        temp = temp_c if use_celsius else (temp_c * 9/5 + 32)
        return {
            "temp": temp,
            "humidity": humidity,
            "pressure": pressure_inhg
        }

    def clear(self):
        self.sense.clear()

    def display_grid(self, grid):
        self.sense.set_pixels(grid)
