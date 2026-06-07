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

DISEASE_SPECIALITY_MAP = {
    "aids": "Infectious Disease Specialist",
    "acne": "Dermatologist",
    "alcoholic hepatitis": "Gastroenterologist / Hepatologist",
    "allergy": "Allergist / Immunologist",
    "arthritis": "Rheumatologist / Orthopedic Specialist",
    "bronchial asthma": "Pulmonologist / Allergist",
    "cervical spondylosis": "Orthopedic / Spine Specialist",
    "chronic cholestasis": "Gastroenterologist / Hepatologist",
    "dengue": "Internal Medicine / Infectious Disease Specialist",
    "diabetes": "Endocrinologist",
    "dimorphic hemorrhoids(piles)": "General Surgeon / Colorectal Surgeon",
    "drug reaction": "Dermatologist / Allergist",
    "gerd": "Gastroenterologist",
    "gastroenteritis": "Gastroenterologist",
    "heart attack": "Cardiologist",
    "hepatitis a": "Gastroenterologist / Hepatologist",
    "hepatitis b": "Gastroenterologist / Hepatologist",
    "hepatitis c": "Gastroenterologist / Hepatologist",
    "hepatitis d": "Gastroenterologist / Hepatologist",
    "hepatitis e": "Gastroenterologist / Hepatologist",
    "hypertension": "Cardiologist / Internal Medicine Specialist",
    "hyperthyroidism": "Endocrinologist",
    "hypoglycemia": "Endocrinologist / Internal Medicine Specialist",
    "hypothyroidism": "Endocrinologist",
    "impetigo": "Dermatologist",
    "jaundice": "Gastroenterologist / Hepatologist",
    "malaria": "Internal Medicine / Infectious Disease Specialist",
    "migraine": "Neurologist",
    "osteoarthritis": "Orthopedic Specialist / Rheumatologist",
    "paralysis (brain hemorrhage)": "Neurologist / Neurosurgeon",
    "peptic ulcer disease": "Gastroenterologist",
    "pneumonia": "Pulmonologist / Internal Medicine Specialist",
    "psoriasis": "Dermatologist",
    "tuberculosis": "Pulmonologist / Infectious Disease Specialist",
    "typhoid": "Internal Medicine Specialist",
    "urinary tract infection": "Urologist / Internal Medicine Specialist",
    "varicose veins": "Vascular Surgeon",
    "vertigo (benign paroxysmal positional vertigo)": "Neurologist / ENT Specialist",
}


@login_required(login_url="login")
def index(request):
    return render(request, "index.html")

@login_required(login_url="login")
def prediction(request):
    MODEL, LABEL_ENCODER = load_model()

    # default context values
    res = None
    speciality = None
    disease_advice = None
    recommended_doctors = []
    chat_doctor_user_id = None

    if request.method == "POST":
        try:
            values = [int(request.POST.get(f, 0)) for f in FEATURES]
        except ValueError:
            messages.error(request, "Invalid input values. Please select the options correctly.")
            return render(request, "prediction.html")

        df = pd.DataFrame([values], columns=FEATURES)

        if MODEL:
            try:
                pred = MODEL.predict(df)
                if LABEL_ENCODER:
                    try:
                        res = LABEL_ENCODER.inverse_transform(pred)[0]
                    except Exception:
                        res = str(pred[0])
                else:
                    res = str(pred[0])
            except Exception as e:
                messages.error(request, f"Model prediction error: {e}")

        # -----------------------------
        #      SAVE MEDICAL HISTORY
        # -----------------------------
        try:
            MedicalHistory.objects.create(
                user=request.user,
                fever=request.POST.get("fever", ""),
                headache=request.POST.get("headache", ""),
                nausea=request.POST.get("nausea", ""),
                vomiting=request.POST.get("vomiting", ""),
                fatigue=request.POST.get("fatigue", ""),
                joint_pain=request.POST.get("joint_pain", ""),
                skin_rash=request.POST.get("skin_rash", ""),
                cough=request.POST.get("cough", ""),
                weight_loss=request.POST.get("weight_loss", ""),
                yellow_eyes=request.POST.get("yellow_eyes", ""),
                res=res if res else "",
            )
        except Exception as e:
            messages.warning(request, f"Could not save history: {e}")

        # -----------------------------
        #    SPECIALIST + ADVICE + DOCTOR
        # -----------------------------
        if res:
            key = res.strip().lower()

            speciality = DISEASE_SPECIALITY_MAP.get(key)
            disease_advice = DISEASE_ADVICE_MAP.get(key)

            # Find recommended doctors based on specialization text
            if speciality:
                base_spec = speciality.split("/")[0].strip()
                recommended_doctors = Doctor.objects.filter(
                    specialization__icontains=base_spec
                )

                # pick first doctor that has a staff User with same email
                for d in recommended_doctors:
                    doc_user = User.objects.filter(email=d.email, is_staff=True).first()
                    if doc_user:
                        chat_doctor_user_id = doc_user.id
                        break

        return render(
            request,
            "prediction.html",
            {
                "res": res,
                "speciality": speciality,
                "disease_advice": disease_advice,
                "recommended_doctors": recommended_doctors,
                "chat_doctor_user_id": chat_doctor_user_id,
            },
        )

    # GET request -> just show form
    return render(request, "prediction.html")

@login_required(login_url="login")
def history(request):
    history_qs = MedicalHistory.objects.filter(user=request.user).order_by("-id")

    query = request.GET.get("q")
    start_date = request.GET.get("start_date")
    end_date = request.GET.get("end_date")
    selected_result = request.GET.get("result_filter")

    if query:
        history_qs = history_qs.filter(res__icontains=query)

    if start_date and end_date:
        history_qs = history_qs.filter(created_at__date__range=[start_date, end_date])

    if selected_result and selected_result != "all":
        history_qs = history_qs.filter(res=selected_result)

    result_options = (
        MedicalHistory.objects.filter(user=request.user)
        .values_list("res", flat=True)
        .distinct()
    )

    paginator = Paginator(history_qs, 10)
    page_number = request.GET.get("page")
    page_obj = paginator.get_page(page_number)

    return render(
        request,
        "history.html",
        {
            "his": page_obj,
            "query": query,
            "start_date": start_date,
            "end_date": end_date,
            "selected_result": selected_result,
            "result_options": result_options,
        },
    )

@login_required(login_url="login")
def delete_history(request, id):
    history_entry = get_object_or_404(MedicalHistory, id=id, user=request.user)
    history_entry.delete()
    messages.success(request, "History record deleted successfully.")
    return redirect("history")

@login_required(login_url="login")
def download_history_csv(request):
    history_qs = MedicalHistory.objects.filter(user=request.user).order_by("-id")

    response = HttpResponse(content_type="text/csv")
    response["Content-Disposition"] = 'attachment; filename="medical_history.csv"'

    writer = csv.writer(response)
    writer.writerow([
        "ID", "Fever", "Headache", "Nausea", "Vomiting", "Fatigue",
        "Joint Pain", "Skin Rash", "Cough", "Weight Loss", "Yellow Eyes", "Result", "Created At"
    ])

    for entry in history_qs:
        writer.writerow([
            entry.id,
            entry.fever,
            entry.headache,
            entry.nausea,
            entry.vomiting,
            entry.fatigue,
            entry.joint_pain,
            entry.skin_rash,
            entry.cough,
            entry.weight_loss,
            entry.yellow_eyes,
            entry.res,
            entry.created_at.strftime("%Y-%m-%d %H:%M:%S") if hasattr(entry, "created_at") else ""
        ])

    return response

@login_required(login_url="login")
def history_detail(request, id):
    entry = get_object_or_404(MedicalHistory, id=id, user=request.user)
    return render(request, "history_detail.html", {"entry": entry})

@login_required(login_url="login")
def history_detail_pdf(request, id):
    entry = get_object_or_404(MedicalHistory, id=id, user=request.user)

    response = HttpResponse(content_type="application/pdf")
    response["Content-Disposition"] = f'attachment; filename="history_{entry.id}.pdf"'

    p = canvas.Canvas(response, pagesize=A4)
    width, height = A4

    p.setFont("Helvetica-Bold", 16)
    p.drawString(100, height - 80, "Patient Medical History Report")

    y = height - 120
    p.setFont("Helvetica", 12)
    user = entry.user
    p.drawString(100, y, f"Name: {user.first_name}")
    y -= 20
    p.drawString(100, y, f"Email: {user.email}")
    y -= 20
    profile = getattr(user, "profile", None)
    if profile and hasattr(profile, "phone"):
        p.drawString(100, y, f"Phone: {profile.phone}")
        y -= 20

    y -= 20
    p.setFont("Helvetica-Bold", 14)
    p.drawString(100, y, "Symptoms")
    p.setFont("Helvetica", 12)
    y -= 20
    fields = [
        ("Fever", entry.fever),
        ("Headache", entry.headache),
        ("Nausea", entry.nausea),
        ("Vomiting", entry.vomiting),
        ("Fatigue", entry.fatigue),
        ("Joint Pain", entry.joint_pain),
        ("Skin Rash", entry.skin_rash),
        ("Cough", entry.cough),
        ("Weight Loss", entry.weight_loss),
        ("Yellow Eyes", entry.yellow_eyes),
    ]
    for label, value in fields:
        p.drawString(120, y, f"{label}: {value}")
        y -= 18

    y -= 20
    p.setFont("Helvetica-Bold", 14)
    p.drawString(100, y, f"Prediction Result: {entry.res}")

    p.showPage()
    p.save()
    return response

@login_required(login_url="login")
def download_history_pdf(request):
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=A4)
    elements = []
    styles = getSampleStyleSheet()

    logo_path = os.path.join(settings.BASE_DIR, "myapp", "static", "images", "logo.png")
    if os.path.exists(logo_path):
        logo = Image(logo_path, width=80, height=80)
        elements.append(logo)
    elements.append(Spacer(1, 12))

    title = Paragraph("<b>Medical History Report</b>", styles["Title"])
    elements.append(title)
    elements.append(Spacer(1, 12))

    patient_name = request.user.first_name or request.user.username
    patient_email = request.user.email or "N/A"
    patient_phone = request.user.last_name or "N/A"

    patient_info = Paragraph(
        f"<b>Patient Name:</b> {patient_name}<br/>"
        f"<b>Email:</b> {patient_email}<br/>"
        f"<b>Phone:</b> {patient_phone}",
        styles["Normal"]
    )
    elements.append(patient_info)
    elements.append(Spacer(1, 12))

    history_qs = MedicalHistory.objects.filter(user=request.user).order_by("-id")
    data = [["#", "Date/Time", "Fever", "Headache", "Nausea", "Vomiting",
             "Fatigue", "Joint Pain", "Skin Rash", "Cough",
             "Weight Loss", "Yellow Eyes", "Result"]]

    for i, h in enumerate(history_qs, start=1):
        data.append([
            i,
            h.created_at.strftime("%d-%m-%Y %H:%M"),
            h.fever,
            h.headache,
            h.nausea,
            h.vomiting,
            h.fatigue,
            h.joint_pain,
            h.skin_rash,
            h.cough,
            h.weight_loss,
            h.yellow_eyes,
            h.res
        ])

    table = Table(data, repeatRows=1)
    table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#4a90e2")),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("ALIGN", (0, 0), (-1, -1), "CENTER"),
        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
        ("FONTSIZE", (0, 0), (-1, 0), 10),
        ("BOTTOMPADDING", (0, 0), (-1, 0), 8),
        ("GRID", (0, 0), (-1, -1), 0.5, colors.grey),
    ]))

    elements.append(table)
    elements.append(Spacer(1, 20))
    footer = Paragraph("<i>Generated by Disease Prediction System</i>", styles["Italic"])
    elements.append(footer)

    doc.build(elements)
    buffer.seek(0)

    response = HttpResponse(buffer, content_type="application/pdf")
    response["Content-Disposition"] = "attachment; filename=medical_history.pdf"
    return response

@login_required(login_url="login")
def profile_view(request):
    user = request.user
    profile, created = Profile.objects.get_or_create(user=user)

    if request.method == "POST":
        # ✅ Save phone
        phone = request.POST.get("phone", "").strip()
        profile.phone = phone

        # ✅ Save uploaded profile photo
        if "profile_pic" in request.FILES:
            profile.profile_pic = request.FILES["profile_pic"]

        profile.save()
        messages.success(request, "Profile updated successfully.")

        # ✅ Optional: Change password
        password = request.POST.get("password", "")
        confirm = request.POST.get("confirm_password", "")

        if password:
            if password != confirm:
                messages.error(request, "Passwords do not match.")
            elif len(password) < 6:
                messages.error(request, "Password must be at least 6 characters.")
            else:
                user.set_password(password)
                user.save()
                update_session_auth_hash(request, user)
                messages.success(request, "Password changed successfully.")

        return redirect("Profile")  # URL name is Profile

    # 👇 recent doctor reviews for this user (if you have doctor_notes fields)
    reviewed_histories = (
        MedicalHistory.objects
        .filter(user=user, doctor_notes__isnull=False)
        .order_by("-reviewed_at")[:5]
    )

    # 👇 NEW: latest doctor application for this user (if any)
    latest_application = (
        DoctorApplication.objects
        .filter(user=user)
        .order_by("-created_at")
        .first()
    )

    return render(request, "Profile.html", {
        "user": user,
        "profile": profile,
        "reviewed_histories": reviewed_histories,
        "latest_application": latest_application,
    })

def _get_model_paths():
    base_dir = os.path.dirname(__file__)  # myapp directory
    model_path = os.path.join(base_dir, "best_model.pkl")
    le_path = os.path.join(base_dir, "label_encoder.pkl")
    return model_path, le_path

def load_model():
    global MODEL, LABEL_ENCODER
    if MODEL is None or LABEL_ENCODER is None:
        model_path, le_path = _get_model_paths()
        MODEL = joblib.load(model_path) if os.path.exists(model_path) else None
        LABEL_ENCODER = joblib.load(le_path) if os.path.exists(le_path) else None
    return MODEL, LABEL_ENCODER

