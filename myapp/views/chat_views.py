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

