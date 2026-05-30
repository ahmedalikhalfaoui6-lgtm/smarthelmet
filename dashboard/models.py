from django.db import models
from django.utils import timezone

class Rider(models.Model):
    id = models.AutoField(primary_key=True)
    name = models.CharField(max_length=100)
    email = models.EmailField(unique=True)
    bike_id = models.CharField(max_length=50, unique=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.name} ({self.bike_id})"

class Helmet(models.Model):
    helmet_id = models.CharField(max_length=50, primary_key=True)
    rider = models.OneToOneField(Rider, on_delete=models.SET_NULL, null=True, blank=True, related_name='helmet')
    is_connected = models.BooleanField(default=False)
    last_seen = models.DateTimeField(auto_now=True)
    
    # Network metrics
    latency_ms = models.IntegerField(default=0)
    signal_strength = models.IntegerField(default=0) # e.g. -dBm or percentage
    
    # Live Data
    speed = models.FloatField(default=0.0)
    latitude = models.FloatField(default=0.0)
    longitude = models.FloatField(default=0.0)
    alcohol_level = models.FloatField(default=0.0)
    is_worn = models.BooleanField(default=False)
    is_strapped = models.BooleanField(default=False)
    
    # MPU Data
    tilt_angle = models.FloatField(default=0.0)
    
    battery_level = models.IntegerField(default=100)
    state = models.CharField(max_length=20, default='Idle')

    def __str__(self):
        return f"Helmet {self.helmet_id}"

class Route(models.Model):
    rider = models.ForeignKey(Rider, on_delete=models.CASCADE, related_name='routes')
    start_time = models.DateTimeField(default=timezone.now)
    end_time = models.DateTimeField(null=True, blank=True)
    is_active = models.BooleanField(default=True)

    def __str__(self):
        return f"Route for {self.rider.name} at {self.start_time}"

class Incident(models.Model):
    INCIDENT_TYPES = [
        ('CRASH', 'Crash Detected'),
        ('ALC', 'Alcohol Threshold Exceeded'),
        ('DISC', 'Disconnected during ride'),
    ]
    rider = models.ForeignKey(Rider, on_delete=models.CASCADE, related_name='incidents')
    helmet = models.ForeignKey(Helmet, on_delete=models.CASCADE)
    timestamp = models.DateTimeField(auto_now_add=True)
    type = models.CharField(max_length=10, choices=INCIDENT_TYPES)
    latitude = models.FloatField()
    longitude = models.FloatField()
    resolved = models.BooleanField(default=False)

    def __str__(self):
        return f"{self.type} - {self.rider.name} ({self.timestamp.date()})"

class MaintenanceLog(models.Model):
    helmet = models.ForeignKey(Helmet, on_delete=models.CASCADE, related_name='maintenance_logs')
    date = models.DateField(auto_now_add=True)
    description = models.TextField()
    technician = models.CharField(max_length=100)
    battery_replaced = models.BooleanField(default=False)

    def __str__(self):
        return f"Maintenance {self.helmet.helmet_id} - {self.date}"

class GPSPoint(models.Model):
    route = models.ForeignKey(Route, on_delete=models.CASCADE, related_name='points')
    latitude = models.FloatField()
    longitude = models.FloatField()
    timestamp = models.DateTimeField(auto_now_add=True)
    speed = models.FloatField(default=0.0)
    alcohol_level = models.FloatField(default=0.0)
    tilt_angle = models.FloatField(default=0.0)

    class Meta:
        ordering = ['timestamp']

class SystemSettings(models.Model):
    platform_name = models.CharField(max_length=100, default='HeisenHelmet')
    allowed_alcohol_level = models.FloatField(default=0.5)
    speed_limit = models.FloatField(default=60.0)
    map_refresh_rate_seconds = models.PositiveIntegerField(default=5)
    
    # Internal MQTT (Service-to-Broker)
    mqtt_broker_host = models.CharField(max_length=255, default='localhost')
    mqtt_broker_port = models.PositiveIntegerField(default=1883)
    
    # External MQTT (Web/Browser access)
    mqtt_websocket_host = models.CharField(max_length=255, default='', blank=True, help_text="Public address for Web MQTT (e.g. mqtt.yourdomain.com)")
    mqtt_websocket_port = models.PositiveIntegerField(default=443, help_text="Usually 443 for WSS via Cloudflare")
    mqtt_use_ssl = models.BooleanField(default=True)
    
    mqtt_topic_helmet_status = models.CharField(max_length=255, default='helmet/+/status')
    mqtt_topic_helmet_command = models.CharField(max_length=255, default='helmet/+/command')

    def __str__(self):
        return "System Settings"


