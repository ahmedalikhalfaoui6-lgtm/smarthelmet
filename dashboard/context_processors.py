from .models import SystemSettings, Incident

def app_settings(request):
    settings = SystemSettings.objects.first()
    critical_incidents_count = Incident.objects.filter(resolved=False).count()
    return {
        'app_settings': settings,
        'global_critical_incidents': critical_incidents_count
    }
