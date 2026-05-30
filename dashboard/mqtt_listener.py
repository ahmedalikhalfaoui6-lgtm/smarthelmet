import json
import logging
import threading
import time

import paho.mqtt.client as mqtt

logger = logging.getLogger(__name__)

_mqtt_started = False
_mqtt_lock = threading.Lock()


# =========================
# MQTT CONNECT
# =========================
def on_connect(client, userdata, flags, rc):
    if rc == 0:
        logger.info('Connected to MQTT Broker!')

        client.subscribe('helmet/+/status')
        client.subscribe('helmet/+/request')

    else:
        logger.error(f'Failed to connect, return code {rc}')


# =========================
# MQTT MESSAGE RECEIVED
# =========================
def on_message(client, userdata, msg):

    try:
        topic = msg.topic
        payload = json.loads(msg.payload.decode())

        print(topic)
        print(payload)

        parts = topic.split('/')

        if len(parts) < 2:
            return

        helmet_id = parts[1]

        if topic.endswith('/status'):
            handle_status_update(helmet_id, payload)

        elif topic.endswith('/request'):
            handle_request(helmet_id, payload)

    except Exception as e:
        logger.error(f'Error processing MQTT message: {e}')


# =========================
# HANDLE STATUS UPDATE
# =========================
def handle_status_update(helmet_id, data):

    from .models import (
        Helmet,
        Route,
        GPSPoint,
        Incident,
        SystemSettings
    )

    # Get/Create helmet
    helmet, created = Helmet.objects.get_or_create(
        helmet_id=helmet_id
    )

    # System config
    config = SystemSettings.objects.first()

    if not config:
        config = SystemSettings.objects.create()

    alcohol_limit = config.allowed_alcohol_level

    # Check active incident
    active_incident = Incident.objects.filter(
        helmet=helmet,
        resolved=False
    ).exists()

    # Update telemetry
    helmet.is_connected = True

    helmet.speed = data.get('speed', helmet.speed)

    helmet.latitude = data.get('lat', helmet.latitude)

    helmet.longitude = data.get('lon', helmet.longitude)

    helmet.alcohol_level = data.get(
        'alc',
        helmet.alcohol_level
    )

    helmet.is_worn = data.get(
        'worn',
        helmet.is_worn
    )

    helmet.battery_level = data.get(
        'bat',
        helmet.battery_level
    )

    helmet.is_strapped = data.get(
        'strapped',
        helmet.is_strapped
    )

    helmet.tilt_angle = data.get(
        'tilt',
        helmet.tilt_angle
    )

    helmet.latency_ms = data.get(
        'latency',
        helmet.latency_ms
    )

    helmet.signal_strength = data.get(
        'rssi',
        helmet.signal_strength
    )

    # =========================
    # STATE LOGIC
    # =========================
    if active_incident:

        helmet.state = 'Accident'

    elif helmet.alcohol_level > alcohol_limit:

        helmet.state = 'Drunk'

    elif helmet.is_connected:

        helmet.state = 'Online'

    else:

        helmet.state = 'Offline'

    # Optional manual override
    if (
        'state' in data
        and not active_incident
        and helmet.state != 'Drunk'
    ):
        helmet.state = data['state']

    helmet.save()

    # =========================
    # CREATE INCIDENT
    # =========================
    if data.get('alc', 0) > alcohol_limit:

        Incident.objects.create(
            rider=helmet.rider,
            helmet=helmet,
            type='ALC',
            latitude=helmet.latitude,
            longitude=helmet.longitude
        )

    # =========================
    # GPS HISTORY
    # =========================
    if helmet.rider:

        route = Route.objects.filter(
            rider=helmet.rider,
            is_active=True
        ).first()

        if not route:

            route = Route.objects.create(
                rider=helmet.rider
            )

        if 'lat' in data and 'lon' in data:

            GPSPoint.objects.create(
                route=route,
                latitude=data['lat'],
                longitude=data['lon'],
                speed=data.get('speed', 0.0),
                alcohol_level=data.get('alc', 0.0),
                tilt_angle=data.get('tilt', 0.0)
            )


# =========================
# HANDLE REQUEST
# =========================
def handle_request(helmet_id, data):

    from .models import SystemSettings

    if data.get('type') == 'get_settings':

        config = SystemSettings.objects.first()

        if not config:
            config = SystemSettings.objects.create()

        response = {
            'allowed_alcohol_level': config.allowed_alcohol_level,
            'speed_limit': config.speed_limit,
            'refresh_rate': config.map_refresh_rate_seconds
        }

        from .mqtt_commands import publish_custom_topic

        publish_custom_topic(
            f'helmet/{helmet_id}/settings',
            response
        )


# =========================
# MQTT LOOP
# =========================
def _mqtt_loop():

    from .models import SystemSettings

    while True:

        try:

            config = SystemSettings.objects.first()

            if not config:
                config = SystemSettings.objects.create()

            host = config.mqtt_broker_host or 'localhost'

            port = config.mqtt_broker_port or 1883

        except Exception as e:

            logger.error(
                f'Database access error in MQTT loop: {e}'
            )

            host = 'localhost'
            port = 1883

        client = mqtt.Client(
            client_id="django-backend-listener",
            clean_session=False
        )

        client.on_connect = on_connect
        client.on_message = on_message

        try:

            logger.info(
                f'Attempting MQTT connection to {host}:{port}'
            )

            client.connect(host, port, 60)

            client.loop_forever()

        except Exception as e:

            logger.error(
                f'MQTT connection error: {e}. Retrying in 5 seconds...'
            )

            time.sleep(5)

# =========================
# START MQTT LISTENER
# =========================
def start_mqtt_listener():

    global _mqtt_started

    with _mqtt_lock:

        if _mqtt_started:
            return

        _mqtt_started = True

    thread = threading.Thread(
        target=_mqtt_loop,
        daemon=True
    )
    thread.start() 

    logger.info('MQTT Listener thread started.')