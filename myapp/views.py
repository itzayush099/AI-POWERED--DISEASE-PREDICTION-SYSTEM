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
from .models import MedicalHistory, Profile, Doctor, Message, DoctorApplication


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

from .models import MedicalHistory, Profile, Doctor, Message


# =====================================================
#                  MODEL LOADING
# =====================================================

MODEL = None
LABEL_ENCODER = None


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


FEATURES = [
    "fever", "headache", "nausea", "vomiting", "fatigue",
    "joint_pain", "skin_rash", "cough", "weight_loss", "yellow_eyes"
]

# =====================================================
#   DISEASE → SPECIALIST + ADVICE (for recommendation)
# =====================================================

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

DISEASE_ADVICE_MAP = {
    "aids": (
        "Get regular follow-ups with an infectious disease specialist. "
        "Take prescribed medicines regularly and avoid unprotected sex or needle sharing. "
        "If you notice fever, weight loss, or new infections, seek medical help quickly."
    ),
    "acne": (
        "Avoid squeezing or scratching pimples. Use gentle, non-oily skin products and keep your face clean. "
        "If acne is severe or leaves marks, consult a dermatologist for proper treatment."
    ),
    "alcoholic hepatitis": (
        "Completely avoid alcohol and follow a liver-friendly diet. "
        "This condition can be serious, so consult a gastroenterologist or liver specialist as soon as possible."
    ),
    "allergy": (
        "Try to identify and avoid the trigger (dust, food, medicine, etc.). "
        "For repeated or severe reactions like swelling, breathing difficulty, or rashes, see an allergist or doctor immediately."
    ),
    "arthritis": (
        "Gentle exercise, weight control, and avoiding stress on joints can help. "
        "If you have persistent joint pain, swelling, or stiffness, consult a rheumatologist or orthopedic specialist."
    ),
    "bronchial asthma": (
        "Avoid triggers like smoke, dust, and strong perfumes. Use your inhaler as prescribed. "
        "If you feel tightness in chest or difficulty in breathing, seek medical help urgently."
    ),
    "cervical spondylosis": (
        "Maintain good posture, avoid long periods of looking down at screens, and do neck exercises as advised. "
        "If pain radiates to arms, or there is weakness or numbness, consult an orthopedic or spine specialist."
    ),
    "chronic cholestasis": (
        "This suggests long-term liver or bile duct issues. Avoid alcohol and fatty foods. "
        "Consult a gastroenterologist or hepatologist for detailed evaluation and tests."
    ),
    "dengue": (
        "Take plenty of fluids, rest, and avoid self-medication with painkillers like ibuprofen without medical advice. "
        "If you notice bleeding, severe stomach pain, or extreme weakness, go to a hospital immediately."
    ),
    "diabetes": (
        "Follow a balanced, low-sugar diet, exercise regularly, and check your blood sugar as advised. "
        "Consult an endocrinologist or physician to adjust medicines and avoid complications."
    ),
    "dimorphic hemorrhoids(piles)": (
        "Avoid constipation by drinking water and eating fiber-rich foods. "
        "If pain, bleeding, or swelling continue, consult a general or colorectal surgeon for proper treatment."
    ),
    "drug reaction": (
        "Stop the suspected medicine only after talking to a doctor. "
        "Do not restart medicines that caused severe rashes or swelling. "
        "If there is breathing difficulty, swelling of lips/face, or high fever, seek emergency care."
    ),
    "gerd": (
        "Avoid spicy, oily, and very late-night meals. Do not lie down immediately after eating. "
        "If you have frequent burning in the chest or sour taste in mouth, consult a gastroenterologist."
    ),
    "gastroenteritis": (
        "Take plenty of clean fluids to avoid dehydration and eat light food. "
        "If vomiting or loose motions are severe, or there is blood in stool, consult a doctor quickly."
    ),
    "heart attack": (
        "This is a medical emergency. Pain or heaviness in chest, sweating, breathing difficulty, or pain radiating to arm/jaw "
        "needs immediate hospital care and cardiology consultation."
    ),
    "hepatitis a": (
        "Usually spreads through contaminated food or water. Take rest, avoid oily food and alcohol, and drink safe water. "
        "Follow a gastroenterologist’s advice and get liver function tests as recommended."
    ),
    "hepatitis b": (
        "Can affect the liver for a long time. Avoid alcohol, do not share razors/needles, and follow your doctor’s advice about antiviral treatment. "
        "Family members may also need screening and vaccination."
    ),
    "hepatitis c": (
        "This can become chronic. Regular follow-up with a liver specialist is important. "
        "Avoid alcohol and get tests as advised to monitor liver health."
    ),
    "hepatitis d": (
        "Often occurs along with hepatitis B. This needs specialist care. "
        "Follow your hepatologist’s advice carefully and avoid alcohol and unsafe injections."
    ),
    "hepatitis e": (
        "Usually spreads through contaminated water. Take rest, avoid alcohol and heavy food, and drink clean, boiled or filtered water. "
        "Pregnant women with jaundice must seek urgent medical attention."
    ),
    "hypertension": (
        "Reduce salt intake, manage stress, exercise regularly, and take prescribed tablets regularly. "
        "Do not stop blood pressure medicines on your own. Regular blood pressure checks are important."
    ),
    "hyperthyroidism": (
        "Watch for symptoms like weight loss, palpitations, or anxiety. "
        "Consult an endocrinologist to control hormone levels and adjust medicines as needed."
    ),
    "hypoglycemia": (
        "Low blood sugar can be dangerous. Keep some quick sugar source like glucose or sweet juice with you. "
        "If episodes are frequent, meet your doctor to adjust diabetes or other medicines."
    ),
    "hypothyroidism": (
        "Take thyroid medicine regularly on an empty stomach as advised. "
        "Do not change dose without consulting your doctor. Regular thyroid tests help keep levels stable."
    ),
    "impetigo": (
        "This is a contagious skin infection. Maintain good hygiene and avoid sharing towels or clothes. "
        "Consult a dermatologist or doctor for proper antibiotics."
    ),
    "jaundice": (
        "Yellow eyes/skin suggest a liver or bile problem. Avoid alcohol and heavy food. "
        "Consult a doctor or gastroenterologist for tests to find the cause of jaundice."
    ),
    "malaria": (
        "Take plenty of fluids and rest. Antimalarial treatment must be guided by a doctor. "
        "High fever with chills, vomiting, or confusion need urgent medical care."
    ),
    "migraine": (
        "Rest in a dark, quiet room, avoid loud noise and screen strain, and stay hydrated. "
        "Track triggers like certain foods or lack of sleep. A neurologist can help with preventive medicines."
    ),
    "osteoarthritis": (
        "Maintain a healthy weight, keep joints active with gentle exercise, and avoid overloading painful joints. "
        "If pain is persistent or movement is limited, consult an orthopedic specialist or rheumatologist."
    ),
    "paralysis (brain hemorrhage)": (
        "Sudden weakness of face, arm, or leg; difficulty in speaking; or sudden loss of balance is an emergency. "
        "Immediate hospital care and neurologist evaluation are critical."
    ),
    "peptic ulcer disease": (
        "Avoid spicy, acidic foods, smoking, and alcohol. Do not take painkillers like NSAIDs without medical advice. "
        "Consult a gastroenterologist for proper tests and treatment."
    ),
    "pneumonia": (
        "Cough with fever, chest pain, and breathing difficulty can be serious. "
        "Plenty of rest, fluids, and early medical treatment from a pulmonologist or physician are important."
    ),
    "psoriasis": (
        "Avoid harsh soaps and keep skin moisturized. Stress and smoking can worsen symptoms. "
        "A dermatologist can advise creams, tablets, or other therapies for long-term control."
    ),
    "tuberculosis": (
        "Take anti-TB medicines exactly as prescribed and do not stop early. "
        "Cover your mouth while coughing and ensure good ventilation. Follow up regularly with your doctor."
    ),
    "typhoid": (
        "Drink clean, boiled or filtered water and avoid roadside or unhygienic food. "
        "Complete the full antibiotic course if prescribed and take adequate rest."
    ),
    "urinary tract infection": (
        "Drink plenty of water and do not hold urine for long periods. "
        "If you have burning urination, fever, or side/back pain, consult a doctor or urologist for proper antibiotics."
    ),
    "varicose veins": (
        "Avoid standing for very long, elevate your legs when resting, and maintain a healthy weight. "
        "Compression stockings and a vascular surgeon’s opinion can help in advanced cases."
    ),
    "vertigo (benign paroxysmal positional vertigo)": (
        "Avoid sudden head movements and get up slowly from lying or sitting positions. "
        "If vertigo is frequent, consult a neurologist or ENT specialist for proper exercises and evaluation."
    ),
}


# =====================================================
#                    BASIC VIEWS
# =====================================================

@login_required(login_url="login")
def index(request):
    return render(request, "index.html")


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
        user.last_name = phone  # store phone here too
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


# =====================================================
#                    PREDICTION
#   (NOW WITH SPECIALIST, ADVICE, RECOMMENDED DOCTOR)
# =====================================================

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


# =====================================================
#                HISTORY + EXPORT
# =====================================================

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


def logout_view(request):
    logout(request)
    messages.info(request, "You have been logged out.")
    return redirect("login")


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


# =====================================================
#               PASSWORD RESET & PROFILE
# =====================================================

def reset_password_view(request):
    if request.method == "POST":
        email = request.POST.get("email", "").strip()
        password = request.POST.get("password", "")
        confirm = request.POST.get("confirm_password", "")

        if not email or not password or not confirm:
            messages.error(request, "Please fill all the fields.")
            return render(request, "reset_password.html")

        if password != confirm:
            messages.error(request, "Passwords do not match.")
            return render(request, "reset_password.html", {"email": email})

        if len(password) < 6:
            messages.error(request, "Password must be at least 6 characters long.")
            return render(request, "reset_password.html", {"email": email})

        user = User.objects.filter(email=email).first()
        if not user:
            messages.error(request, "No account found with this email.")
            return render(request, "reset_password.html", {"email": email})

        user.set_password(password)
        user.save()

        messages.success(request, "Password reset successfully. You can now log in.")
        return redirect("login")

    return render(request, "reset_password.html")


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


# =====================================================
#                  ADMIN & STAFF HELPERS
# =====================================================

def is_staff_user(user):
    return user.is_staff or user.is_superuser


@login_required(login_url="login")
@user_passes_test(is_staff_user, login_url="index")
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


# =====================================================
#                  DOCTOR DASHBOARD
# =====================================================

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


# =====================================================
#                    ADMIN USERS
# =====================================================

@login_required(login_url="login")
@user_passes_test(is_staff_user, login_url="index")
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


# =====================================================
#                 ADMIN DOCTORS
#    (NOW ALSO CREATES STAFF USER FOR DOCTOR)
# =====================================================

@login_required(login_url="login")
@user_passes_test(is_staff_user, login_url="index")
def admin_doctors(request):
    doctors = Doctor.objects.all().order_by("name")

    if request.method == "POST":
        name = request.POST.get("name", "").strip()
        specialization = request.POST.get("specialization", "").strip()
        email = request.POST.get("email", "").strip()
        phone = request.POST.get("phone", "").strip()

        if not name:
            messages.error(request, "Doctor name is required.")
        else:
            doctor = Doctor.objects.create(
                name=name,
                specialization=specialization,
                email=email,
                phone=phone,
            )

            # ✅ ALSO CREATE A STAFF USER FOR THIS DOCTOR (IF EMAIL PROVIDED)
            if email:
                existing_user = User.objects.filter(email=email).first()
                if existing_user:
                    # If already exists, just make sure they are staff
                    if not existing_user.is_staff:
                        existing_user.is_staff = True
                        existing_user.save()
                    messages.success(
                        request,
                        f"Doctor added. Existing user {existing_user.username} marked as staff."
                    )
                else:
                    temp_password = get_random_string(8)  # ✅ Django-safe random password
                    doctor_user = User.objects.create_user(
                    username=email,
                    email=email,
                    password=temp_password,
                    first_name=name,
                    )

                    doctor_user.is_staff = True
                    doctor_user.save()

                    messages.success(
                        request,
                        f"Doctor added and staff user created. Login: {email} / {temp_password}"
                    )
            else:
                messages.warning(
                    request,
                    "Doctor added without email. No login account created."
                )

            return redirect("admin_doctors")

    return render(request, "admin_doctors.html", {"doctors": doctors})

@login_required(login_url="login")
@user_passes_test(is_staff_user, login_url="index")
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

            doctor, created = Doctor.objects.get_or_create(
                email=user.email,
                defaults={
                    "name": application.full_name or user.first_name or user.username,
                    "specialization": application.specialization,
                    "phone": phone_val,
                },
            )

            # If doctor already existed but had no specialization, optionally update
            if not created and not doctor.specialization:
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
@user_passes_test(is_staff_user, login_url="index")
def admin_delete_doctor(request, doctor_id):
    doctor = get_object_or_404(Doctor, id=doctor_id)

    if request.method == "POST":
        # 🔹 Try to find the related Django user by email (preferred)
        linked_user = None
        if doctor.email:
            linked_user = User.objects.filter(email=doctor.email).first()

        # 🔹 If not found by email, optionally try by phone (you stored phone in last_name)
        if not linked_user and doctor.phone:
            linked_user = User.objects.filter(last_name=doctor.phone).first()

        # 🔹 If a matching user is found, remove staff (doctor) access
        if linked_user:
            linked_user.is_staff = False
            # Do NOT touch is_superuser here, only staff
            linked_user.save()

        # 🔹 Finally delete the Doctor record
        doctor.delete()
        messages.success(request, "Doctor deleted and staff access removed.")
        return redirect("admin_doctors")

    # GET -> simple confirm page
    return render(request, "confirm_delete_doctor.html", {"doctor": doctor})

# =====================================================
#                ADMIN DELETE USER
# =====================================================

@login_required(login_url="login")
@user_passes_test(is_staff_user, login_url="index")
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


# =====================================================
#                ADMIN PATIENTS & REPORTS
# =====================================================

@staff_member_required
def admin_patients(request):
    users = User.objects.all()
    histories = MedicalHistory.objects.all().order_by("-id")

    query = request.GET.get("q")
    if query:
        histories = histories.filter(user__username__icontains=query)

    return render(request, "admin_patients.html", {
        "users": users,
        "histories": histories
    })


@staff_member_required
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

from django.db.models import Q

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
    from .models import Doctor  # ensure Doctor is imported at top too
    doctor_obj = Doctor.objects.filter(email__iexact=doctor_user.email).first()

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

    # Build data for template
    patients = []
    for p in patients_qs:
        history_count = MedicalHistory.objects.filter(user=p).count()
        unread_count = Message.objects.filter(
            sender=p,
            receiver=doctor_user,
            is_read=False
        ).count()
        last_msg = Message.objects.filter(
            Q(sender=p, receiver=doctor_user) |
            Q(sender=doctor_user, receiver=p)
        ).order_by("-timestamp").first()

        patients.append({
            "obj": p,
            "history_count": history_count,
            "unread_count": unread_count,
            "last_message": last_msg,
        })

    return render(request, "doctor_patients_list.html", {
        "patients": patients,
    })

# =====================================================
#          DOCTOR: VIEW PATIENT HISTORY + REVIEW
# =====================================================

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


# =====================================================
#              CHAT: CONVERSATION LIST
# =====================================================

@login_required(login_url="login")
def conversations_list(request):
    user = request.user

    def can_chat(a, b):
        if a.is_superuser:
            return True
        if a.is_staff and not a.is_superuser:
            return (not b.is_staff) and (not b.is_superuser)
        if (not a.is_staff) and (not a.is_superuser):
            return b.is_staff or b.is_superuser
        return False

    msgs = (
        Message.objects
        .filter(Q(sender=user) | Q(receiver=user))
        .select_related("sender", "receiver")
        .order_by("-timestamp")
    )

    conversations = {}

    for m in msgs:
        other = m.receiver if m.sender == user else m.sender
        if not can_chat(user, other):
            continue
        if other.id not in conversations:
            unread_count = Message.objects.filter(
                sender=other,
                receiver=user,
                is_read=False,
            ).count()
            conversations[other.id] = {
                "other_user": other,
                "last_message": m,
                "unread_count": unread_count,
            }

    return render(request, "conversations_list.html", {
        "conversations": conversations.values(),
    })


# =====================================================
#                      CHAT VIEW
# =====================================================

@login_required(login_url="login")
def chat_view(request, user_id):
    other_user = get_object_or_404(User, id=user_id)
    user = request.user

    def can_chat(a, b):
        if a.is_superuser:
            return True
        if a.is_staff and not a.is_superuser:
            return (not b.is_staff) and (not b.is_superuser)
        if (not a.is_staff) and (not a.is_superuser):
            return b.is_staff or b.is_superuser
        return False

    if not can_chat(user, other_user):
        messages.error(request, "You are not allowed to chat with this user.")
        return redirect("conversations_list")

    if request.method == "POST":
        content = request.POST.get("content", "").strip()
        if content:
            Message.objects.create(
                sender=user,
                receiver=other_user,
                content=content,
            )
        return redirect("chat_view", user_id=other_user.id)

    msgs = (
        Message.objects
        .filter(
            Q(sender=user, receiver=other_user) |
            Q(sender=other_user, receiver=user)
        )
        .order_by("timestamp")
    )

    msgs.filter(receiver=user, is_read=False).update(is_read=True)

    return render(request, "chat.html", {
        "other_user": other_user,
        "messages": msgs,
    })
