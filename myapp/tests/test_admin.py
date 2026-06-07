from django.test import TestCase, Client
from django.urls import reverse
from django.contrib.auth.models import User
from myapp.models import Doctor

class AdminTests(TestCase):
    def setUp(self):
        self.client = Client()
        self.admin_user = User.objects.create_superuser(username='admin', password='password')
        self.doctor_user = User.objects.create_user(username='doc', password='password', is_staff=True)
        self.doctor = Doctor.objects.create(user=self.doctor_user, specialization='General')
        self.patient_user = User.objects.create_user(username='pat', password='password')

    def test_admin_dashboard_loads(self):
        self.client.login(username='admin', password='password')
        response = self.client.get(reverse('admin_dashboard'))
        self.assertEqual(response.status_code, 200)

    def test_admin_doctors_loads(self):
        self.client.login(username='admin', password='password')
        response = self.client.get(reverse('admin_doctors'))
        self.assertEqual(response.status_code, 200)

    def test_admin_users_loads(self):
        self.client.login(username='admin', password='password')
        response = self.client.get(reverse('admin_users'))
        self.assertEqual(response.status_code, 200)

    def test_admin_doctor_applications_loads(self):
        self.client.login(username='admin', password='password')
        response = self.client.get(reverse('admin_doctor_applications'))
        self.assertEqual(response.status_code, 200)

    def test_admin_patients_loads(self):
        self.client.login(username='admin', password='password')
        response = self.client.get(reverse('admin_patients'))
        self.assertEqual(response.status_code, 200)

    def test_admin_reports_loads(self):
        self.client.login(username='admin', password='password')
        response = self.client.get(reverse('admin_reports'))
        self.assertEqual(response.status_code, 200)

    def test_doctor_cannot_access_admin_dashboard(self):
        self.client.login(username='doc', password='password')
        response = self.client.get(reverse('admin_dashboard'))
        # Should redirect to index or login since they don't have is_superuser
        self.assertNotEqual(response.status_code, 200)

    def test_patient_cannot_access_admin_dashboard(self):
        self.client.login(username='pat', password='password')
        response = self.client.get(reverse('admin_dashboard'))
        self.assertNotEqual(response.status_code, 200)
