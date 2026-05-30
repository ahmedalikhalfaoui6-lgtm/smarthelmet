from django.contrib.auth.models import User
from django.test import TestCase
from django.urls import reverse

from .models import Helmet, Rider, SystemSettings
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
