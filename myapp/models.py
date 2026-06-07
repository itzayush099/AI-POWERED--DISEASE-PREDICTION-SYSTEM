from django.db import models
from django.contrib.auth.models import User
from django.db.models.signals import post_save
from django.dispatch import receiver

class MedicalHistory(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE)  # 👈 link to logged-in user
    fever = models.CharField(max_length=10)
    headache = models.CharField(max_length=10)
    nausea = models.CharField(max_length=10)
    vomiting = models.CharField(max_length=10)
    fatigue = models.CharField(max_length=10)
    joint_pain = models.CharField(max_length=10)
    skin_rash = models.CharField(max_length=10)
    cough = models.CharField(max_length=10)
    weight_loss = models.CharField(max_length=10)
    yellow_eyes = models.CharField(max_length=10)
    res = models.CharField(max_length=100)

    # 🔹 New doctor-related fields
    doctor_notes = models.TextField(blank=True, null=True)
    reviewed_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        blank=True,
        null=True,
        related_name="reviewed_histories"
    )
    reviewed_at = models.DateTimeField(blank=True, null=True)

    created_at = models.DateTimeField(auto_now_add=True)  # track when saved

    def __str__(self):
        return f"{self.user.username} - {self.res}"

class Message(models.Model):
    sender = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name="sent_messages"
    )
    receiver = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name="received_messages"
    )
    content = models.TextField()
    timestamp = models.DateTimeField(auto_now_add=True)
    is_read = models.BooleanField(default=False)

    class Meta:
        ordering = ["timestamp"]

    def __str__(self):
        return f"From {self.sender.username} to {self.receiver.username} at {self.timestamp}"
    
# Profile to store extra user info (like phone, profile pic)
class Profile(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE)
    phone = models.CharField(max_length=20, blank=True, null=True)
    profile_pic = models.ImageField(upload_to='profile_pics/', default='profile_pics/default.png')

    def __str__(self):
        return f"Profile of {self.user.username}"


@receiver(post_save, sender=User)
def create_or_update_profile(sender, instance, created, **kwargs):
    # Ensure Profile exists for every user
    try:
        Profile.objects.get_or_create(user=instance)
    except Exception:
        # If Profile model not yet created / migrations not applied, ignore for now.
        pass


# ✅ NEW: Doctor model for admin-only doctor panel
class Doctor(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name="doctor_profile", null=True, blank=True)
    specialization = models.CharField(max_length=100, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        name = self.user.get_full_name() or self.user.username if self.user else "Unknown Doctor"
        if self.specialization:
            return f"{name} ({self.specialization})"
        return name

from django.db import models
from django.contrib.auth.models import User

# ... your existing models (MedicalHistory, Profile, Doctor, Message, etc.) ...


class DoctorApplication(models.Model):
    STATUS_CHOICES = [
        ("pending", "Pending"),
        ("approved", "Approved"),
        ("rejected", "Rejected"),
    ]

    user = models.ForeignKey(
        User, on_delete=models.CASCADE, related_name="doctor_applications"
    )
    full_name = models.CharField(max_length=150)
    specialization = models.CharField(max_length=150)
    qualifications = models.CharField(max_length=255, blank=True)
    education = models.CharField(max_length=255, blank=True)
    experience_years = models.PositiveIntegerField(default=0)
    resume = models.FileField(upload_to="doctor_resumes/", blank=True, null=True)
    additional_info = models.TextField(blank=True)

    status = models.CharField(
        max_length=20, choices=STATUS_CHOICES, default="pending"
    )
    created_at = models.DateTimeField(auto_now_add=True)
    reviewed_at = models.DateTimeField(blank=True, null=True)
    reviewed_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="reviewed_doctor_applications",
    )
    admin_notes = models.TextField(blank=True)

    def __str__(self):
        return f"DoctorApplication({self.user.username}, {self.status})"
