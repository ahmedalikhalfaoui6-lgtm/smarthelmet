from django.contrib import admin
from .models import Rider, Helmet, Route, GPSPoint, SystemSettings

@admin.register(Rider)
class RiderAdmin(admin.ModelAdmin):
    list_display = ('id', 'name', 'email', 'bike_id', 'created_at')
    search_fields = ('name', 'email', 'bike_id')

@admin.register(Helmet)
class HelmetAdmin(admin.ModelAdmin):
    list_display = ('helmet_id', 'rider', 'is_connected', 'speed', 'alcohol_level', 'is_worn', 'battery_level', 'last_seen')
    list_filter = ('is_connected', 'is_worn', 'state')
    search_fields = ('helmet_id', 'rider__name', 'rider__bike_id')

@admin.register(Route)
class RouteAdmin(admin.ModelAdmin):
    list_display = ('id', 'rider', 'start_time', 'end_time', 'is_active')
    list_filter = ('is_active', 'start_time')
    search_fields = ('rider__name',)

@admin.register(GPSPoint)
class GPSPointAdmin(admin.ModelAdmin):
    list_display = ('id', 'route', 'latitude', 'longitude', 'speed', 'timestamp')
    list_filter = ('timestamp',)

@admin.register(SystemSettings)
class SystemSettingsAdmin(admin.ModelAdmin):
    list_display = ('allowed_alcohol_level', 'map_refresh_rate_seconds', 'mqtt_broker_host', 'mqtt_broker_port')
    
