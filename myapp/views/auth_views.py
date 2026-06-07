from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth import authenticate, login as auth_login, logout, update_session_auth_hash
from django.contrib import messages
from django.contrib.auth.decorators import login_required, user_passes_test
from django.contrib.auth.models import User
from django.conf import settings
from django.http import HttpResponse
from django.core.paginator import Paginator
from django.utils import timezone
from django.contrib.admin.views.decorators import staff_member_required
from django.db.models import Count, Q
from django.utils.crypto import get_random_string
from myapp.models import MedicalHistory, Profile, Doctor, Message, DoctorApplication


from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer, Image
from reportlab.pdfgen import canvas
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet

import io
import csv
import os
import joblib

def not_logged_in_required(view_func):
    def _wrapped_view_func(request, *args, **kwargs):
        if request.user.is_authenticated:
            return redirect('index')
        return view_func(request, *args, **kwargs)
    return _wrapped_view_func


import pandas as pd
import json
from datetime import datetime, timedelta

from myapp.models import MedicalHistory, Profile, Doctor, Message


# =====================================================
#                  MODEL LOADING
# =====================================================

MODEL = None
LABEL_ENCODER = None


def signup_view(request):
    if request.method == "POST":
        fullname = request.POST.get("fullname", "").strip()
        email = request.POST.get("email", "").strip()
        phone = request.POST.get("phone", "").strip()
        password = request.POST.get("password", "")
        confirm = request.POST.get("confirm_password", "")

        if not all([fullname, email, password, confirm]):
            messages.error(request, "Please fill all required fields.")
            return render(request, "signup.html")

        if password != confirm:
            messages.error(request, "Passwords do not match.")
            return render(request, "signup.html")

        username = email
        if User.objects.filter(username=username).exists():
            messages.error(
                request,
                "An account with that email already exists. Please login or use a different email."
            )
            return render(request, "signup.html")

        user = User.objects.create_user(username=username, email=email, password=password)
        user.first_name = fullname
        # user.last_name = phone  # Removed anti-pattern
        user.save()

        profile, _ = Profile.objects.get_or_create(user=user)
        profile.phone = phone
        profile.save()

        messages.success(request, "Account created successfully. Please login.")
        return redirect("login")

    return render(request, "signup.html")

def login_view(request):
    if request.method == "POST":
        username_input = request.POST.get("username", "").strip()
        password = request.POST.get("password", "")

        user = authenticate(request, username=username_input, password=password)
        if user is None:
            user_obj = User.objects.filter(email=username_input).first()
            if user_obj:
                user = authenticate(request, username=user_obj.username, password=password)

        if user is not None:
            auth_login(request, user)
            messages.success(request, f"Welcome, {user.first_name or user.username}!")

            if user.is_superuser:
                return redirect("admin_dashboard")
            elif user.is_staff:
                return redirect("doctor_dashboard")
            else:
                return redirect("prediction")
        else:
            messages.error(
                request,
                "Invalid credentials. Try again. (Use your email as username if you signed up with email.)"
            )
            return render(request, "login.html")

    return render(request, "login.html")

def logout_view(request):
    logout(request)
    messages.info(request, "You have been logged out.")
    return redirect("login")

@not_logged_in_required
def reset_password_view(request):
    if request.method == "POST":
        if not request.session.get('reset_otp_sent'):
            # Step 1: Send OTP
            email = request.POST.get("email", "").strip()
            if not email:
                messages.error(request, "Please provide an email.")
                return render(request, "reset_password.html")
                
            user = User.objects.filter(email=email).first()
            if not user:
                # To prevent email enumeration, we pretend it succeeded,
                # but since this is a small app, we can keep the explicit error for UX.
                messages.error(request, "No account found with this email.")
                return render(request, "reset_password.html", {"email": email})
            
            otp = str(random.randint(100000, 999999))
            request.session['reset_otp'] = otp
            request.session['reset_email'] = email
            request.session['reset_otp_sent'] = True
            
            try:
                send_mail(
                    'Password Reset OTP - Health SaaS',
                    f'Your password reset OTP is {otp}',
                    settings.DEFAULT_FROM_EMAIL,
                    [email],
                    fail_silently=True,  # Set to True for testing environments without real SMTP
                )
            except Exception as e:
                # For safety in test environments
                print("Failed to send email:", e)
                
            messages.success(request, "OTP sent to your email.")
            return render(request, "reset_password.html")
        else:
            # Step 2: Verify OTP and reset password
            otp_entered = request.POST.get("otp", "").strip()
            password = request.POST.get("password", "")
            confirm = request.POST.get("confirm_password", "")
            email = request.session.get('reset_email')
            
            if otp_entered != request.session.get('reset_otp'):
                messages.error(request, "Invalid OTP.")
                return render(request, "reset_password.html")
                
            if password != confirm:
                messages.error(request, "Passwords do not match.")
                return render(request, "reset_password.html")

            if len(password) < 6:
                messages.error(request, "Password must be at least 6 characters long.")
                return render(request, "reset_password.html")

            user = User.objects.filter(email=email).first()
            if user:
                user.set_password(password)
                user.save()
                messages.success(request, "Password reset successfully. You can now log in.")
                
            # Clear session
            for key in ['reset_otp', 'reset_email', 'reset_otp_sent']:
                if key in request.session:
                    del request.session[key]
            
            return redirect("login")
            
    else:
        # GET request: clear session state
        for key in ['reset_otp', 'reset_email', 'reset_otp_sent']:
            if key in request.session:
                del request.session[key]
        return render(request, "reset_password.html")
