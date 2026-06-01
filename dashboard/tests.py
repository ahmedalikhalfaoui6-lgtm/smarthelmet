from django.contrib.auth.models import User
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone
from datetime import datetime, time, timedelta

from .models import Helmet, Incident, Rider, SystemSettings
from .views import get_dashboard_safety_summary


class DashboardSafetySummaryTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username='operator', password='pass')
        self.client.login(username='operator', password='pass')
        SystemSettings.objects.create(allowed_alcohol_level=0.5)

    def create_helmet(self, helmet_id, **kwargs):
        rider = Rider.objects.create(
            name=f'Rider {helmet_id}',
            email=f'{helmet_id}@example.com',
            bike_id=f'BIKE-{helmet_id}',
        )
        defaults = {
            'rider': rider,
            'is_connected': True,
            'is_worn': True,
            'is_strapped': True,
            'alcohol_level': 0.1,
        }
        defaults.update(kwargs)
        return Helmet.objects.create(helmet_id=helmet_id, **defaults)

    def test_dashboard_marks_all_safe_connected_helmets_as_enabled(self):
        self.create_helmet('HH-1')

        summary = get_dashboard_safety_summary()

        self.assertEqual(summary['ride_ready_helmets'], 1)
        self.assertEqual(summary['connected_helmets'], 1)
        self.assertEqual(summary['motor_permission'], 'Enabled')
        self.assertEqual(summary['motor_reason'], 'All checks passed')

    def test_dashboard_blocks_motor_with_priority_reason(self):
        self.create_helmet('HH-1', is_strapped=False)
        self.create_helmet('HH-2', alcohol_level=0.9)

        summary = get_dashboard_safety_summary()

        self.assertEqual(summary['ride_ready_helmets'], 0)
        self.assertEqual(summary['motor_permission'], 'Blocked')
        self.assertEqual(summary['motor_reason'], 'Blocked: strap open')

    def test_dashboard_handles_no_connected_helmets(self):
        self.create_helmet('HH-1', is_connected=False)

        summary = get_dashboard_safety_summary()

        self.assertEqual(summary['connected_helmets'], 0)
        self.assertEqual(summary['disconnected_helmets'], 1)
        self.assertEqual(summary['motor_permission'], 'Blocked')
        self.assertEqual(summary['motor_reason'], 'No helmets online')

    def test_live_data_includes_motor_and_gps_safety_fields(self):
        helmet = self.create_helmet('HH-1', latitude=36.8, longitude=10.2)

        response = self.client.get(reverse('live_data'))
        payload = response.json()[0]

        self.assertEqual(payload['id'], helmet.helmet_id)
        self.assertTrue(payload['motor_allowed'])
        self.assertEqual(payload['motor_reason'], 'All checks passed')
        self.assertTrue(payload['gps_fix'])


class RiderManagementTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username='operator', password='pass')
        self.client.login(username='operator', password='pass')
        self.rider = Rider.objects.create(
            name='Delete Me',
            email='delete@example.com',
            bike_id='BIKE-DEL',
        )
        self.helmet = Helmet.objects.create(helmet_id='HH-DEL', rider=self.rider)

    def test_delete_rider_requires_post(self):
        response = self.client.get(reverse('delete_rider', args=[self.rider.id]))

        self.assertEqual(response.status_code, 405)
        self.assertTrue(Rider.objects.filter(id=self.rider.id).exists())

    def test_delete_rider_removes_rider_and_unassigns_helmet(self):
        response = self.client.post(reverse('delete_rider', args=[self.rider.id]))

        self.assertEqual(response.status_code, 302)
        self.assertEqual(response['Location'], reverse('riders'))
        self.assertFalse(Rider.objects.filter(id=self.rider.id).exists())
        self.helmet.refresh_from_db()
        self.assertIsNone(self.helmet.rider)


class FleetActivityHeatmapTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username='operator', password='pass')
        self.client.login(username='operator', password='pass')
        SystemSettings.objects.create(allowed_alcohol_level=0.5)
        self.rider = Rider.objects.create(
            name='Rider One',
            email='rider@example.com',
            bike_id='BIKE-1',
        )
        self.helmet = Helmet.objects.create(helmet_id='HH-1', rider=self.rider)

    def create_incident(self, incident_type, local_when):
        incident = Incident.objects.create(
            rider=self.rider,
            helmet=self.helmet,
            type=incident_type,
            latitude=36.8,
            longitude=10.2,
        )
        Incident.objects.filter(id=incident.id).update(timestamp=local_when)
        incident.refresh_from_db()
        return incident

    def local_datetime(self, day_offset, hour):
        local_date = timezone.localdate() - timedelta(days=day_offset)
        return timezone.make_aware(datetime.combine(local_date, time(hour=hour)), timezone.get_current_timezone())

    def test_heatmap_groups_all_incidents_by_local_weekday_and_hour(self):
        first = self.create_incident('CRASH', self.local_datetime(0, 14))
        self.create_incident('ALC', self.local_datetime(0, 14))
        second_day = self.create_incident('DISC', self.local_datetime(1, 9))

        response = self.client.get(reverse('fleet_activity_heatmap'))
        payload = response.json()

        first_local = timezone.localtime(first.timestamp)
        second_local = timezone.localtime(second_day.timestamp)
        self.assertEqual(payload['buckets'][first_local.weekday()][14], 2)
        self.assertEqual(payload['buckets'][second_local.weekday()][9], 1)
        self.assertEqual(payload['max_count'], 2)
        self.assertEqual(payload['summary']['peak_hour'], '14h')
        self.assertEqual(payload['summary']['total_incidents'], 3)

    def test_heatmap_filters_by_incident_type(self):
        self.create_incident('CRASH', self.local_datetime(0, 6))
        alcohol = self.create_incident('ALC', self.local_datetime(0, 10))
        self.create_incident('DISC', self.local_datetime(0, 15))

        response = self.client.get(reverse('fleet_activity_heatmap'), {'filter': 'alcohol'})
        payload = response.json()

        alcohol_local = timezone.localtime(alcohol.timestamp)
        self.assertEqual(payload['buckets'][alcohol_local.weekday()][10], 1)
        self.assertEqual(payload['summary']['total_incidents'], 1)
        self.assertEqual(payload['summary']['peak_hour'], '10h')

    def test_heatmap_returns_zeroed_grid_when_history_is_empty(self):
        response = self.client.get(reverse('fleet_activity_heatmap'))
        payload = response.json()

        self.assertEqual(len(payload['buckets']), 7)
        self.assertTrue(all(len(row) == 24 for row in payload['buckets']))
        self.assertEqual(payload['max_count'], 0)
        self.assertEqual(payload['summary'], {
            'peak_hour': 'None',
            'peak_day': 'None',
            'quietest_hour': 'None',
            'total_incidents': 0,
        })
