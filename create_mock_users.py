import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'myproject.settings')
django.setup()

from django.contrib.auth.models import User
from myapp.models import Doctor

def create_user(username, email, password, is_staff=False, is_superuser=False):
    user, created = User.objects.get_or_create(username=username, email=email)
    if created:
        user.set_password(password)
        user.is_staff = is_staff
        user.is_superuser = is_superuser
        user.save()
        print(f"Created {username} with password '{password}' (staff={is_staff}, super={is_superuser})")
    else:
        print(f"User {username} already exists.")
    return user

print("Creating mock users...")
admin_user = create_user("admin_test", "admin@test.com", "Password123!", is_staff=True, is_superuser=True)
doctor_user = create_user("doctor_test", "doctor@test.com", "Password123!", is_staff=True, is_superuser=False)
patient_user = create_user("patient_test", "patient@test.com", "Password123!", is_staff=False, is_superuser=False)

# Add doctor to Doctor model if not exists
doctor_profile, created = Doctor.objects.get_or_create(email="doctor@test.com", defaults={"name": "Dr. Test", "specialization": "General"})
if created:
    print("Added Doctor profile for doctor_test.")
else:
    print("Doctor profile already exists.")

print("Done.")
