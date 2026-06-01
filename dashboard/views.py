from datetime import datetime, time, timedelta

from django.shortcuts import render, redirect
from django.conf import settings
from django.http import JsonResponse
from .models import Rider, Helmet, Route, GPSPoint, SystemSettings, Incident, MaintenanceLog
import json
from django.db.models import Q
from django.contrib.auth.decorators import login_required
from django.utils import timezone

def get_dashboard_safety_summary():
    total_helmets = Helmet.objects.count()
    settings = SystemSettings.objects.first()
    alcohol_limit = settings.allowed_alcohol_level if settings else 0.5
    connected_qs = Helmet.objects.filter(is_connected=True)
    connected_helmets = connected_qs.count()
    disconnected_helmets = max(total_helmets - connected_helmets, 0)

    ride_ready_qs = connected_qs.filter(
        is_worn=True,
        is_strapped=True,
        alcohol_level__lt=alcohol_limit
    )
    ride_ready_helmets = ride_ready_qs.count()
    helmet_worn_count = connected_qs.filter(is_worn=True).count()
    strap_secured_count = connected_qs.filter(is_strapped=True).count()
    alcohol_safe_count = connected_qs.filter(alcohol_level__lt=alcohol_limit).count()

    strap_open_count = connected_qs.filter(is_strapped=False).count()
    alcohol_high_count = connected_qs.filter(alcohol_level__gte=alcohol_limit).count()
    helmet_missing_count = connected_qs.filter(is_worn=False).count()

    if connected_helmets == 0:
        ride_ready_color = 'red'
        motor_permission = 'Blocked'
        motor_reason = 'No helmets online'
        motor_color = 'red'
    elif ride_ready_helmets == connected_helmets:
        ride_ready_color = 'green'
        motor_permission = 'Enabled'
        motor_reason = 'All checks passed'
        motor_color = 'green'
    elif ride_ready_helmets > 0:
        ride_ready_color = 'amber'
        motor_permission = 'Mixed'
        motor_reason = f'{ride_ready_helmets}/{connected_helmets} helmets ready'
        motor_color = 'amber'
    else:
        ride_ready_color = 'red'
        motor_permission = 'Blocked'
        motor_color = 'red'
        if strap_open_count:
            motor_reason = 'Blocked: strap open'
        elif alcohol_high_count:
            motor_reason = 'Blocked: alcohol high'
        elif helmet_missing_count:
            motor_reason = 'Blocked: helmet missing'
        else:
            motor_reason = 'Blocked: checks incomplete'
    
    # New Dashboard Data
    critical_incidents = Incident.objects.filter(resolved=False).count()
    recent_incidents = Incident.objects.order_by('-timestamp')[:5]
    
    refresh_rate = settings.map_refresh_rate_seconds if settings else 5
    
    context = {
        'total_helmets': total_helmets,
        'connected_helmets': connected_helmets,
        'disconnected_helmets': disconnected_helmets,
        'ride_ready_helmets': ride_ready_helmets,
        'ride_ready_color': ride_ready_color,
        'helmet_worn_count': helmet_worn_count,
        'strap_secured_count': strap_secured_count,
        'alcohol_safe_count': alcohol_safe_count,
        'alcohol_limit': alcohol_limit,
        'motor_permission': motor_permission,
        'motor_reason': motor_reason,
        'motor_color': motor_color,
        'refresh_rate': refresh_rate,
        'critical_incidents': critical_incidents,
        'recent_incidents': recent_incidents,
        'active_riders': Rider.objects.select_related('helmet').filter(helmet__isnull=False).order_by('name'),
    }
    return context


@login_required
def dashboard(request):
    return render(request, 'dashboard/index.html', get_dashboard_safety_summary())


@login_required
def risk_overview(request):
    settings_obj = SystemSettings.objects.first()
    refresh_rate = settings_obj.map_refresh_rate_seconds if settings_obj else 5
    return render(request, 'dashboard/risk_overview.html', {'refresh_rate': refresh_rate})


@login_required
def fleet_activity_heatmap(request):
    filter_map = {
        'crash': 'CRASH',
        'alcohol': 'ALC',
        'disconnect': 'DISC',
    }
    selected_filter = request.GET.get('filter', 'all')
    days = ['Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat', 'Sun']
    hours = [f'{hour:02d}h' for hour in range(24)]
    buckets = [[0 for _ in range(24)] for _ in range(7)]

    tz = timezone.get_current_timezone()
    start_date = timezone.localdate() - timedelta(days=6)
    start_at = timezone.make_aware(datetime.combine(start_date, time.min), tz)

    incidents = Incident.objects.filter(timestamp__gte=start_at)
    incident_type = filter_map.get(selected_filter)
    if incident_type:
        incidents = incidents.filter(type=incident_type)

    for incident in incidents.only('timestamp'):
        local_timestamp = timezone.localtime(incident.timestamp, tz)
        buckets[local_timestamp.weekday()][local_timestamp.hour] += 1

    max_count = max((count for row in buckets for count in row), default=0)
    total_incidents = sum(count for row in buckets for count in row)

    if total_incidents:
        peak_day_index, peak_hour_index, _ = max(
            ((day_index, hour_index, count) for day_index, row in enumerate(buckets) for hour_index, count in enumerate(row)),
            key=lambda item: item[2],
        )
        quiet_hour_index, _ = min(
            ((hour_index, sum(row[hour_index] for row in buckets)) for hour_index in range(24)),
            key=lambda item: item[1],
        )
        peak_day = days[peak_day_index]
        peak_hour = hours[peak_hour_index]
        quietest_hour = hours[quiet_hour_index]
    else:
        peak_day = 'None'
        peak_hour = 'None'
        quietest_hour = 'None'

    return JsonResponse({
        'days': days,
        'hours': hours,
        'buckets': buckets,
        'max_count': max_count,
        'summary': {
            'peak_hour': peak_hour,
            'peak_day': peak_day,
            'quietest_hour': quietest_hour,
            'total_incidents': total_incidents,
        },
    })

@login_required
def incidents_list(request):
    incident_id = request.GET.get('id')
    if request.method == 'POST' and 'toggle_id' in request.POST:
        from django.shortcuts import get_object_or_404
        inc = get_object_or_404(Incident, id=request.POST.get('toggle_id'))
        inc.resolved = not inc.resolved
        inc.save()
        return redirect('incidents')
        
    incidents = Incident.objects.all().order_by('-timestamp')
    selected_incident = None
    if incident_id:
        selected_incident = Incident.objects.filter(id=incident_id).first()
        
    return render(request, 'dashboard/incidents.html', {
        'incidents': incidents,
        'selected_incident': selected_incident
    })

@login_required
def maintenance_list(request):
    logs = MaintenanceLog.objects.all().order_by('-date')
    return render(request, 'dashboard/maintenance.html', {'logs': logs})

@login_required
def riders_list(request):
    query = request.GET.get('q')
    if query:
        riders = Rider.objects.filter(
            Q(name__icontains=query) | 
            Q(helmet__helmet_id__icontains=query)
        )
    else:
        riders = Rider.objects.all()
    return render(request, 'dashboard/riders.html', {'riders': riders, 'query': query})

@login_required
def rider_detail(request, rider_id):
    from django.shortcuts import get_object_or_404
    rider = get_object_or_404(Rider, id=rider_id)
    routes = Route.objects.filter(rider=rider).order_by('-start_time')
    return render(request, 'dashboard/rider_detail.html', {'rider': rider, 'routes': routes})

def live_data(request):
    rider_id = request.GET.get('rider_id')
    config = SystemSettings.objects.first()
    alcohol_limit = config.allowed_alcohol_level if config else 0.5
    if rider_id:
        helmets = Helmet.objects.filter(rider_id=rider_id)
    else:
        helmets = Helmet.objects.all() # In production maybe filter by connected
    
    data = []
    for h in helmets:
        # Get history for graphs if specific rider
        history = []
        if rider_id:
            # Fix: GPSPoint filters by route, then route filters by rider
            active_route = Route.objects.filter(rider=h.rider, is_active=True).first()
            if active_route:
                points = GPSPoint.objects.filter(route=active_route).order_by('-timestamp')[:20]
                for p in points:
                    history.append({
                        'time': p.timestamp.strftime('%H:%M:%S'),
                        'speed': p.speed,
                        'alc': p.alcohol_level or 0,
                        'tilt': p.tilt_angle or 0
                    })
                history.reverse()

        alcohol_safe = h.alcohol_level < alcohol_limit
        motor_allowed = h.is_connected and h.is_worn and h.is_strapped and alcohol_safe
        if motor_allowed:
            motor_reason = 'All checks passed'
        elif not h.is_connected:
            motor_reason = 'No helmet link'
        elif not h.is_strapped:
            motor_reason = 'Blocked: strap open'
        elif not alcohol_safe:
            motor_reason = 'Blocked: alcohol high'
        elif not h.is_worn:
            motor_reason = 'Blocked: helmet missing'
        else:
            motor_reason = 'Blocked: checks incomplete'

        data.append({
            'id': h.helmet_id,
            'rider_id': h.rider.id if h.rider else None,
            'rider': h.rider.name if h.rider else 'Unassigned',
            'lat': h.latitude,
            'lon': h.longitude,
            'speed': h.speed,
            'alc': h.alcohol_level,
            'worn': h.is_worn,
            'bat': h.battery_level,
            'state': h.state,
            'tilt': h.tilt_angle,
            'strapped': h.is_strapped,
            'is_connected': h.is_connected,
            'latency': h.latency_ms,
            'signal': h.signal_strength,
            'alcohol_limit': alcohol_limit,
            'alcohol_safe': alcohol_safe,
            'motor_allowed': motor_allowed,
            'motor_reason': motor_reason,
            'gps_fix': bool(h.latitude and h.longitude),
            'history': history
        })
    return JsonResponse(data, safe=False)

@login_required
def mqtt_docs(request):
    return render(request, 'dashboard/mqtt_docs.html')

@login_required
def system_settings(request):
    settings_obj, created = SystemSettings.objects.get_or_create(id=1)
    if request.method == 'POST':
        settings_obj.platform_name = request.POST.get('platform_name', 'HeisenHelmet')
        settings_obj.mqtt_broker_host = request.POST.get('mqtt_broker_host')
        settings_obj.mqtt_broker_port = request.POST.get('mqtt_broker_port') or 1883
        settings_obj.mqtt_topic_helmet_status = request.POST.get('mqtt_topic_helmet_status')
        settings_obj.mqtt_topic_helmet_command = request.POST.get('mqtt_topic_helmet_command')
        settings_obj.mqtt_websocket_host = request.POST.get('mqtt_websocket_host', '')
        settings_obj.mqtt_websocket_port = request.POST.get('mqtt_websocket_port') or 443
        settings_obj.mqtt_use_ssl = request.POST.get('mqtt_use_ssl') == 'on'
        settings_obj.map_refresh_rate_seconds = request.POST.get('map_refresh_rate_seconds')
        settings_obj.allowed_alcohol_level = request.POST.get('allowed_alcohol_level')
        settings_obj.speed_limit = request.POST.get('speed_limit') or 60.0
        settings_obj.save()
        return redirect('settings')
    return render(request, 'dashboard/settings.html', {'settings': settings_obj})

@login_required
def add_rider(request):
    if request.method == 'POST':
        name = request.POST.get('name')
        email = request.POST.get('email')
        # Default bike_id to helmet_id if not provided, or simply use helmet_id as fleet identifier
        helmet_id = request.POST.get('helmet_id')
        bike_id = helmet_id # Since we removed it from the form
        
        rider = Rider.objects.create(name=name, email=email, bike_id=bike_id)
        Helmet.objects.get_or_create(helmet_id=helmet_id, defaults={'rider': rider})
        
        return redirect('riders')
    return render(request, 'dashboard/add_rider.html')
