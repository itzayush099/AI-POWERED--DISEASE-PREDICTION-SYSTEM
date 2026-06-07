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


@login_required(login_url="login")
def doctor_apply_view(request):
    user = request.user

    # If already doctor or admin – no need to apply
    if user.is_staff or user.is_superuser:
        messages.info(request, "You already have staff/doctor access.")
        if user.is_superuser:
            return redirect("admin_dashboard")
        else:
            return redirect("doctor_dashboard")

    # Check if a pending application already exists
    existing_pending = DoctorApplication.objects.filter(
        user=user, status="pending"
    ).first()

    if request.method == "POST":
        if existing_pending:
            messages.warning(request, "You already have a pending application.")
            return redirect("doctor_apply")

        full_name = request.POST.get("full_name", "").strip() or user.first_name or user.username
        specialization = request.POST.get("specialization", "").strip()
        qualifications = request.POST.get("qualifications", "").strip()
        education = request.POST.get("education", "").strip()
        experience_years = request.POST.get("experience_years", "0").strip()
        additional_info = request.POST.get("additional_info", "").strip()
        resume_file = request.FILES.get("resume")

        if not specialization:
            messages.error(request, "Please enter your specialization.")
            return render(request, "doctor_apply.html", {
                "user": user,
                "existing_pending": existing_pending,
                "full_name": full_name,
                "specialization": specialization,
                "qualifications": qualifications,
                "education": education,
                "experience_years": experience_years,
                "additional_info": additional_info,
            })

        try:
            exp_int = int(experience_years)
            if exp_int < 0:
                exp_int = 0
        except ValueError:
            exp_int = 0

        DoctorApplication.objects.create(
            user=user,
            full_name=full_name,
            specialization=specialization,
            qualifications=qualifications,
            education=education,
            experience_years=exp_int,
            resume=resume_file,
            additional_info=additional_info,
        )

        messages.success(
            request,
            "Your application has been submitted to the admin. You’ll be notified once it is reviewed."
        )
        return redirect("Profile")  # or "index" or "prediction" if you prefer

    return render(request, "doctor_apply.html", {
        "user": user,
        "existing_pending": existing_pending,
    })

@login_required(login_url="login")
def doctor_dashboard(request):
    if not request.user.is_staff or request.user.is_superuser:
        return redirect("index")

    doctor = request.user

    total_predictions = MedicalHistory.objects.count()
    total_patients = (
        MedicalHistory.objects.values("user").distinct().count()
    )

    top_diseases = (
        MedicalHistory.objects
        .values("res")
        .annotate(count=Count("id"))
        .order_by("-count")[:5]
    )

    recent_history = (
        MedicalHistory.objects
        .select_related("user")
        .order_by("-created_at")[:15]
    )

    unread_qs = (
        Message.objects
        .filter(receiver=doctor, is_read=False)
        .select_related("sender")
        .order_by("-timestamp")
    )

    unread_count = unread_qs.count()

    conversations = {}
    for m in unread_qs:
        patient = m.sender
        if patient.id not in conversations:
            conversations[patient.id] = {
                "patient": patient,
                "last_message": m,
            }

    recent_unread_conversations = list(conversations.values())[:5]

    return render(
        request,
        "doctor_dashboard.html",
        {
            "total_predictions": total_predictions,
            "total_patients": total_patients,
            "top_diseases": top_diseases,
            "recent_history": recent_history,
            "unread_count": unread_count,
            "recent_unread_conversations": recent_unread_conversations,
        },
    )

@login_required(login_url="login")
def doctor_patients_list(request):
    # Only allow staff (doctors), not superusers and not normal users
    if not request.user.is_staff or request.user.is_superuser:
        return redirect("index")

    doctor_user = request.user

    # -------- 1) Patients who have CHATTED with this doctor --------
    chat_patients = User.objects.filter(
        Q(sent_messages__receiver=doctor_user) |
        Q(received_messages__sender=doctor_user)
    ).exclude(id=doctor_user.id).distinct()

    # -------- 2) Patients whose disease is typically handled by THIS doctor --------
    from myapp.views.patient_views import DISEASE_SPECIALITY_MAP
    doctor_obj = getattr(doctor_user, 'doctor_profile', None)

    rec_patients = User.objects.none()
    if doctor_obj:
        doc_spec = (doctor_obj.specialization or "").lower().strip()
        if doc_spec:
            # Build a queryset of histories whose disease maps to this specialization
            rec_history_qs = MedicalHistory.objects.none()
            for disease_lower, spec in DISEASE_SPECIALITY_MAP.items():
                spec_l = spec.lower()
                # if doctor specialization and mapped speciality "match enough"
                if doc_spec in spec_l or spec_l in doc_spec:
                    rec_history_qs = rec_history_qs | MedicalHistory.objects.filter(
                        res__iexact=disease_lower  # case-insensitive match
                    )

            rec_patients = User.objects.filter(
                medicalhistory__in=rec_history_qs
            ).distinct()

    # -------- 3) Combine both sources --------
    patients_qs = (chat_patients | rec_patients).distinct().order_by("first_name", "username")
    patient_ids = list(patients_qs.values_list('id', flat=True))

    # Bulk fetch history counts
    history_counts = dict(
        MedicalHistory.objects.filter(user_id__in=patient_ids)
        .values('user_id')
        .annotate(count=Count('id'))
        .values_list('user_id', 'count')
    )

    # Bulk fetch unread counts
    unread_counts = dict(
        Message.objects.filter(sender_id__in=patient_ids, receiver=doctor_user, is_read=False)
        .values('sender_id')
        .annotate(count=Count('id'))
        .values_list('sender_id', 'count')
    )

    # Bulk fetch last messages
    # We can fetch all messages between the doctor and these patients and find the latest
    all_msgs = Message.objects.filter(
        Q(sender_id__in=patient_ids, receiver=doctor_user) |
        Q(sender=doctor_user, receiver_id__in=patient_ids)
    ).order_by('-timestamp')
    
    last_msgs = {}
    for msg in all_msgs:
        # The patient is either the sender or receiver
        pat_id = msg.sender_id if msg.sender_id != doctor_user.id else msg.receiver_id
        if pat_id not in last_msgs:
            last_msgs[pat_id] = msg

    # Build data for template
    patients = []
    for p in patients_qs:
        patients.append({
            "obj": p,
            "history_count": history_counts.get(p.id, 0),
            "unread_count": unread_counts.get(p.id, 0),
            "last_message": last_msgs.get(p.id, None),
        })

    return render(request, "doctor_patients_list.html", {
        "patients": patients,
    })

@login_required(login_url="login")
def doctor_patient_history(request, user_id):
    if not request.user.is_staff or request.user.is_superuser:
        return redirect("index")

    patient = get_object_or_404(User, id=user_id)
    histories = (
        MedicalHistory.objects
        .filter(user=patient)
        .order_by("-created_at")
    )

    return render(request, "doctor_patient_history.html", {
        "patient": patient,
        "histories": histories,
    })

@login_required(login_url="login")
def doctor_history_review(request, history_id):
    if not request.user.is_staff or request.user.is_superuser:
        return redirect("index")

    entry = get_object_or_404(MedicalHistory, id=history_id)

    if request.method == "POST":
        notes = request.POST.get("doctor_notes", "").strip()
        entry.doctor_notes = notes
        entry.reviewed_by = request.user
        entry.reviewed_at = timezone.now()
        entry.save()
        messages.success(request, "Doctor notes saved for this prediction.")
        return redirect("doctor_patient_history", user_id=entry.user.id)

    return render(request, "doctor_history_review.html", {
        "entry": entry,
    })

