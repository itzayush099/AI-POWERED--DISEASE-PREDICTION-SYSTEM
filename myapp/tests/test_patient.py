from django.test import TestCase, Client
from django.contrib.auth.models import User
from django.urls import reverse

class PatientTests(TestCase):
    def setUp(self):
        self.client = Client()
        self.patient_user = User.objects.create_user(username='pat', password='password')

    def test_patient_prediction_loads(self):
        self.client.login(username='pat', password='password')
        response = self.client.get(reverse('prediction'))
        self.assertEqual(response.status_code, 200)

    def test_patient_history_loads(self):
        self.client.login(username='pat', password='password')
        response = self.client.get(reverse('history'))
        self.assertEqual(response.status_code, 200)

    def test_patient_profile_loads(self):
        self.client.login(username='pat', password='password')
        response = self.client.get(reverse('Profile'))
        self.assertEqual(response.status_code, 200)
