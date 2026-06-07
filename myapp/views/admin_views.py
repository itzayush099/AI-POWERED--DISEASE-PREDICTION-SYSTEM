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
import pandas as pd
import json
from datetime import datetime, timedelta

from myapp.models import MedicalHistory, Profile, Doctor, Message


# =====================================================
#                  MODEL LOADING
# =====================================================

MODEL = None
LABEL_ENCODER = None


def is_admin_user(user):
    return user.is_superuser

@login_required(login_url="login")
@user_passes_test(is_admin_user, login_url="index")
def admin_dashboard(request):
    total_users = User.objects.count()
    total_history = MedicalHistory.objects.count()

    today = timezone.localdate()
    seven_days_ago = today - timedelta(days=6)

    history_today = MedicalHistory.objects.filter(created_at__date=today).count()
    history_last_7 = MedicalHistory.objects.filter(created_at__date__gte=seven_days_ago).count()
    history_this_month = MedicalHistory.objects.filter(
        created_at__year=today.year,
        created_at__month=today.month
    ).count()

    daily_qs = (
        MedicalHistory.objects
        .filter(created_at__date__gte=seven_days_ago)
        .values("created_at__date")
        .annotate(count=Count("id"))
        .order_by("created_at__date")
    )
    daily_counts_map = {item["created_at__date"]: item["count"] for item in daily_qs}

    chart_labels_days = []
    chart_counts_days = []
    for i in range(7):
        day = seven_days_ago + timedelta(days=i)
        chart_labels_days.append(day.strftime("%d %b"))
        chart_counts_days.append(daily_counts_map.get(day, 0))

    top_users = (
        User.objects
        .annotate(history_count=Count("medicalhistory"))
        .order_by("-history_count")[:5]
    )

    start_date = request.GET.get("start_date")
    end_date = request.GET.get("end_date")
    selected_disease = request.GET.get("disease")

    filtered_qs = MedicalHistory.objects.select_related("user").order_by("-created_at")

    if start_date:
        filtered_qs = filtered_qs.filter(created_at__date__gte=start_date)
    if end_date:
        filtered_qs = filtered_qs.filter(created_at__date__lte=end_date)
    if selected_disease and selected_disease != "all":
        filtered_qs = filtered_qs.filter(res=selected_disease)

    filtered_top_diseases = (
        filtered_qs
        .values("res")
        .annotate(count=Count("id"))
        .order_by("-count")[:7]
    )

    recent_predictions = filtered_qs[:10]

    disease_options = (
        MedicalHistory.objects
        .values_list("res", flat=True)
        .distinct()
        .order_by("res")
    )

    context = {
        "total_users": total_users,
        "total_history": total_history,
        "history_today": history_today,
        "history_last_7": history_last_7,
        "history_this_month": history_this_month,
        "chart_labels_days_json": json.dumps(chart_labels_days),
        "chart_counts_days_json": json.dumps(chart_counts_days),
        "top_users": top_users,
        "start_date": start_date,
        "end_date": end_date,
        "selected_disease": selected_disease,
        "disease_options": disease_options,
        "filtered_top_diseases": filtered_top_diseases,
        "recent_predictions": recent_predictions,
    }
    return render(request, "admin_dashboard.html", context)

@login_required(login_url="login")
@user_passes_test(is_admin_user, login_url="index")
def admin_users(request):
    if request.method == "POST":
        action = request.POST.get("action")
        user_id = request.POST.get("user_id")

        target = get_object_or_404(User, id=user_id)

        if target == request.user and action in ["toggle_active", "remove_staff", "reset_password"]:
            messages.error(request, "You cannot perform this action on your own account.")
            return redirect("admin_users")

        if action == "toggle_active":
            target.is_active = not target.is_active
            target.save()
            state = "activated" if target.is_active else "deactivated"
            messages.success(request, f"User {target.username} has been {state}.")

        elif action == "make_staff":
            target.is_staff = True
            target.save()
            messages.success(request, f"User {target.username} is now staff.")

        elif action == "remove_staff":
            target.is_staff = False
            target.save()
            messages.success(request, f"User {target.username} is no longer staff.")

        elif action == "reset_password":
            temp_password = get_random_string(8)  # ✅ use this instead
            target.set_password(temp_password)
            target.save()
            messages.success(
                request,
                  f"Temporary password for {target.username}: {temp_password}"
             )

        return redirect("admin_users")

    users = (
        User.objects
        .annotate(history_count=Count("medicalhistory"))
        .order_by("-date_joined")
    )
    return render(request, "admin_users.html", {"users": users})

@login_required(login_url="login")
@user_passes_test(is_admin_user, login_url="index")
def admin_doctors(request):
    doctors = Doctor.objects.select_related("user").all()

    if request.method == "POST":
        name = request.POST.get("name", "").strip()
        specialization = request.POST.get("specialization", "").strip()
        email = request.POST.get("email", "").strip()
        phone = request.POST.get("phone", "").strip()

        if not email:
            messages.error(request, "Doctor email is required.")
        else:
            existing_user = User.objects.filter(email=email).first()
            if existing_user:
                if not existing_user.is_staff:
                    existing_user.is_staff = True
                    existing_user.save()
                doctor_user = existing_user
                messages.success(request, f"Existing user {existing_user.username} marked as staff.")
            else:
                temp_password = get_random_string(8)
                doctor_user = User.objects.create_user(
                    username=email, email=email, password=temp_password, first_name=name
                )
                doctor_user.is_staff = True
                doctor_user.save()
                messages.success(request, f"Doctor added and staff user created. Login: {email} / {temp_password}")
            
            profile, _ = Profile.objects.get_or_create(user=doctor_user)
            if phone:
                profile.phone = phone
                profile.save()
            
            doctor, created = Doctor.objects.get_or_create(user=doctor_user)
            doctor.specialization = specialization
            doctor.save()

            return redirect("admin_doctors")

    return render(request, "admin_doctors.html", {"doctors": doctors})

@login_required(login_url="login")
@user_passes_test(is_admin_user, login_url="index")
def admin_doctor_applications(request):
    # Optional: only superuser can approve/reject
    # if not request.user.is_superuser:
    #     messages.error(request, "Only superadmins can manage doctor applications.")
    #     return redirect("admin_dashboard")

    if request.method == "POST":
        app_id = request.POST.get("application_id")
        action = request.POST.get("action")
        admin_notes = request.POST.get("admin_notes", "").strip()

        application = get_object_or_404(DoctorApplication, id=app_id)

        if application.status != "pending":
            messages.warning(request, "This application has already been processed.")
            return redirect("admin_doctor_applications")

        user = application.user

        if action == "approve":
            application.status = "approved"
            application.reviewed_by = request.user
            application.reviewed_at = timezone.now()
            application.admin_notes = admin_notes

            # Promote this user to doctor/staff
            user.is_staff = True
            user.save()

            # Ensure a Doctor record exists
            phone_val = ""
            profile = getattr(user, "profile", None)
            if profile and profile.phone:
                phone_val = profile.phone

            profile, _ = Profile.objects.get_or_create(user=user)
            if not profile.phone:
                profile.phone = phone_val
                profile.save()

            doctor, created = Doctor.objects.get_or_create(user=user)
            if not created and not doctor.specialization:
                doctor.specialization = application.specialization
                doctor.save()
            elif created:
                doctor.specialization = application.specialization
                doctor.save()

            application.save()
            messages.success(
                request,
                f"Application from {user.username} approved and user promoted to doctor."
            )

        elif action == "reject":
            application.status = "rejected"
            application.reviewed_by = request.user
            application.reviewed_at = timezone.now()
            application.admin_notes = admin_notes
            application.save()
            messages.info(
                request,
                f"Application from {application.user.username} has been rejected."
            )

        return redirect("admin_doctor_applications")

    applications = DoctorApplication.objects.select_related("user").order_by("-created_at")
    return render(request, "admin_doctor_applications.html", {
        "applications": applications,
    })

@login_required(login_url="login")
@user_passes_test(is_admin_user, login_url="index")
def admin_delete_doctor(request, doctor_id):
    doctor = get_object_or_404(Doctor, id=doctor_id)

    if request.method == "POST":
        linked_user = doctor.user
        if linked_user:
            linked_user.is_staff = False
            linked_user.save()

        doctor.delete()
        messages.success(request, "Doctor deleted and staff access removed.")
        return redirect("admin_doctors")

    # GET -> simple confirm page
    return render(request, "confirm_delete_doctor.html", {"doctor": doctor})

@login_required(login_url="login")
@user_passes_test(is_admin_user, login_url="index")
def admin_delete_user(request, user_id):
    user_to_delete = get_object_or_404(User, id=user_id)

    if user_to_delete == request.user:
        messages.error(request, "You cannot delete your own admin account.")
        return redirect("admin_users")

    if request.method == "POST":
        user_to_delete.delete()
        messages.success(request, "User deleted successfully.")
        return redirect("admin_users")

    return render(request, "confirm_delete_user.html", {"user_obj": user_to_delete})

@user_passes_test(is_admin_user, login_url="index")
def admin_patients(request):
    histories = MedicalHistory.objects.select_related("user").order_by("-id")

    query = request.GET.get("q")
    if query:
        histories = histories.filter(user__username__icontains=query)

    return render(request, "admin_patients.html", {
        "histories": histories
    })

@user_passes_test(is_admin_user, login_url="index")
def admin_reports(request):
    total_users = User.objects.count()
    total_predictions = MedicalHistory.objects.count()

    disease_stats = (
        MedicalHistory.objects
        .values("res")
        .annotate(count=Count("res"))
        .order_by("-count")
    )

    last_7_days = timezone.now() - timedelta(days=7)
    daily_stats = (
        MedicalHistory.objects
        .filter(created_at__gte=last_7_days)
        .extra(select={"day": "date(created_at)"})
        .values("day")
        .annotate(count=Count("id"))
        .order_by("day")
    )

    return render(request, "admin_reports.html", {
        "total_users": total_users,
        "total_predictions": total_predictions,
        "disease_stats": disease_stats,
        "daily_stats": daily_stats,
    })

