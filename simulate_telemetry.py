import os
import django
import random
import time

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'smarthelmet.settings')
django.setup()

from dashboard.models import Helmet, Rider

def simulate_network():
    print("Starting HeisenHelmet Data Simulation...")
    helmets = Helmet.objects.all()
    if not helmets.exists():
        print("No helmets found. Please add a rider and helmet first.")
        return

    try:
        while True:
            for h in helmets:
                # Simulate connectivity
                h.is_connected = random.choice([True, True, True, False]) # 75% chance connected
                
                if h.is_connected:
                    # Realistic network jitter
                    h.latency_ms = random.randint(15, 45)
                    h.signal_strength = random.randint(70, 98)
                    
                    # Movement simulation
                    h.speed = max(0, h.speed + random.uniform(-5, 5))
                    if h.speed > 120: h.speed = 110
                    
                    # Sensor simulation
                    h.battery_level = max(0, h.battery_level - random.randint(0, 1))
                    if h.battery_level == 0: h.battery_level = 100
                    
                    h.alcohol_level = round(random.uniform(0.0, 0.08), 3)
                    h.tilt_angle = round(random.uniform(-10, 10), 2)
                    
                    # Random states
                    h.state = random.choice(['Active', 'Cruising', 'Slowing', 'Stopped'])
                    h.is_worn = True
                    h.is_strapped = True
                else:
                    h.latency_ms = 0
                    h.signal_strength = 0
                    h.state = 'Offline'
                
                h.save()
            
            print(f"Updated {helmets.count()} helmets with live telemetry.")
            time.sleep(5)
    except KeyboardInterrupt:
        print("Simulation stopped.")

if __name__ == "__main__":
    simulate_network()
