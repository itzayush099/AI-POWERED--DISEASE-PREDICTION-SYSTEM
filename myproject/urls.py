from django.contrib import admin
from django.urls import path
from myapp import views
from django.conf import settings
from django.conf.urls.static import static

urlpatterns = [
    path('admin/', admin.site.urls),

    path('', views.index, name='index'),
    path('prediction/', views.prediction, name='prediction'),
    path('history/', views.history, name='history'),
    path('login/', views.login_view, name='login'),
    path('signup/', views.signup_view, name='signup'),
    path('logout/', views.logout_view, name='logout'),

    path("download-history/", views.download_history_csv, name="download_history"),
    path("history/pdf/", views.download_history_pdf, name="download_history_pdf"),
    path("history/<int:id>/", views.history_detail, name="history_detail"),
    path("history/<int:id>/pdf/", views.history_detail_pdf, name="history_detail_pdf"),
    path("history/delete/<int:id>/", views.delete_history, name="delete_history"),

    path("Profile/", views.profile_view, name="Profile"),
    path("reset-password/", views.reset_password_view, name="reset_password"),

    path("admin-dashboard/", views.admin_dashboard, name="admin_dashboard"),
    path("admin-users/", views.admin_users, name="admin_users"),
    path("admin-users/<int:user_id>/delete/", views.admin_delete_user, name="admin_delete_user"),

    path("admin-doctors/", views.admin_doctors, name="admin_doctors"),
    path("admin-doctors/<int:doctor_id>/delete/", views.admin_delete_doctor, name="admin_delete_doctor"),
    path("admin-patients/", views.admin_patients, name="admin_patients"),
    path("admin-reports/", views.admin_reports, name="admin_reports"),
    path("doctor/patient/<int:user_id>/", views.doctor_patient_history, name="doctor_patient_history"),
    path(
    "doctor/history/<int:history_id>/",
    views.doctor_history_review,
    name="doctor_history_review"
    ),
    path("messages/", views.conversations_list, name="conversations_list"),
    path("chat/<int:user_id>/", views.chat_view, name="chat_view"),
    path("doctor-patients/", views.doctor_patients_list, name="doctor_patients_list"),
    path("doctor-apply/", views.doctor_apply_view, name="doctor_apply"),
    path("admin-doctor-applications/", views.admin_doctor_applications, name="admin_doctor_applications"),


    path("doctor-dashboard/", views.doctor_dashboard, name="doctor_dashboard"),
]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
