from django.apps import AppConfig
import threading

class DashboardConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'dashboard'

    def ready(self):
        # Start MQTT listener in a separate thread
        from . import mqtt_listener
        thread = threading.Thread(target=mqtt_listener.start_mqtt_listener, daemon=True)
        thread.start()
