from django.test import TestCase, Client
from django.contrib.auth.models import User
from django.urls import reverse
from myapp.models import Doctor

class DoctorTests(TestCase):
    def setUp(self):
        self.client = Client()
        self.doctor_user = User.objects.create_user(username='doc', email='doc@doc.com', password='password', is_staff=True)
        self.doctor = Doctor.objects.create(user=self.doctor_user, specialization='General')
        self.patient_user = User.objects.create_user(username='pat', password='password')

    def test_doctor_dashboard_loads(self):
        self.client.login(username='doc', password='password')
        response = self.client.get(reverse('doctor_dashboard'))
        self.assertEqual(response.status_code, 200)

    def test_doctor_patients_list_loads(self):
        self.client.login(username='doc', password='password')
        response = self.client.get(reverse('doctor_patients_list'))
        self.assertEqual(response.status_code, 200)

    def test_patient_cannot_access_doctor_dashboard(self):
        self.client.login(username='pat', password='password')
        response = self.client.get(reverse('doctor_dashboard'))
        self.assertNotEqual(response.status_code, 200)

    def test_admin_cannot_access_doctor_dashboard(self):
        User.objects.create_superuser(username='admin', password='password')
        self.client.login(username='admin', password='password')
        response = self.client.get(reverse('doctor_dashboard'))
        self.assertNotEqual(response.status_code, 200)
