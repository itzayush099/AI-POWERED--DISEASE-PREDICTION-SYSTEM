from django.test import TestCase, Client
from django.contrib.auth.models import User
from django.urls import reverse

class AuthTests(TestCase):
    def setUp(self):
        self.client = Client()
        self.user = User.objects.create_user(username='testuser', email='test@example.com', password='password123')

    def test_login_page_loads(self):
        response = self.client.get(reverse('login'))
        self.assertEqual(response.status_code, 200)

    def test_signup_page_loads(self):
        response = self.client.get(reverse('signup'))
        self.assertEqual(response.status_code, 200)

    def test_user_login(self):
        response = self.client.post(reverse('login'), {'username': 'test@example.com', 'password': 'password123'})
        self.assertEqual(response.status_code, 302)

    def test_user_signup(self):
        response = self.client.post(reverse('signup'), {
            'fullname': 'New User',
            'email': 'new@example.com',
            'phone': '1234567890',
            'password': 'password123',
            'confirm_password': 'password123'
        })
        self.assertEqual(response.status_code, 302)
        new_user = User.objects.get(email='new@example.com')
        self.assertEqual(new_user.profile.phone, '1234567890')
        self.assertNotEqual(new_user.last_name, '1234567890') # verify phone abuse is fixed

    def test_user_logout(self):
        self.client.login(username='testuser', password='password123')
        response = self.client.get(reverse('logout'))
        self.assertEqual(response.status_code, 302)
