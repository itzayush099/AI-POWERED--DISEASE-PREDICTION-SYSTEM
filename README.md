# AI-Powered Disease Prediction System

A robust, machine-learning-driven healthcare web application built with **Django**. This system allows patients to input their symptoms to receive AI-based disease predictions, while also providing a comprehensive dashboard for doctors and administrators to manage patient records and securely communicate via chat.

---

## 🌟 Key Features

* **🤖 AI Disease Prediction:** Utilizes a Scikit-Learn Random Forest model to predict potential diseases based on an array of user-inputted symptoms.
* **🔒 Secure Authentication:** Implements strict Role-Based Access Control (RBAC) separating Standard Users, Doctors, and Superuser Admins.
* **🔑 Secure Password Recovery:** Features a robust 6-digit OTP password reset flow sent securely via SMTP.
* **💬 Doctor-Patient Chat:** A built-in messaging system enabling secure communication between patients and assigned medical professionals.
* **🏥 Medical Dashboards:** Dedicated, modular portals for Patients (to view history), Doctors (to review cases), and Admins (to oversee applications and metrics).
* **✨ Modern UI:** Features a highly-polished, responsive "Glassmorphism" interface built with modern CSS paradigms.
* **🚀 Production Ready:** Configured with `dj-database-url` and `whitenoise` for seamless deployment to Vercel Serverless environments.

---

## 🛠️ Technology Stack

* **Backend:** Python 3.9+, Django 5.x
* **Machine Learning:** Scikit-Learn, Pandas, NumPy, Joblib
* **Frontend:** HTML5, Vanilla CSS3 (Glassmorphism design system), JavaScript
* **Database:** SQLite (Local Development) / PostgreSQL (Production)
* **Hosting:** Vercel (Serverless Deployment)

---

## 🚀 Local Development Setup

Follow these instructions to run the project locally on your machine.

### 1. Clone the repository
```bash
git clone https://github.com/itzayush099/AI-POWERED--DISEASE-PREDICTION-SYSTEM.git
cd AI-POWERED--DISEASE-PREDICTION-SYSTEM
```

### 2. Create a Virtual Environment
```bash
python -m venv venv
source venv/bin/activate  # On Windows use: venv\Scripts\activate
```

### 3. Install Dependencies
```bash
pip install -r requirements.txt
```

### 4. Setup Environment Variables
Create a `.env` file in the root directory:
```env
DEBUG=True
SECRET_KEY=your-super-secret-key-here
EMAIL_HOST_USER=your_email@gmail.com
EMAIL_HOST_PASSWORD=your_app_password
```

### 5. Run Migrations & Collect Static Files
```bash
python manage.py migrate
python manage.py collectstatic --noinput
```

### 6. Create a Superuser
```bash
python manage.py createsuperuser
```

### 7. Run the Server
```bash
python manage.py runserver
```
Visit `http://localhost:8000` in your browser.

---

## ☁️ Live Deployment

The project is fully deployed and hosted on Vercel! You can view the live, production-ready application here:

👉 **[Live Demo on Vercel](https://ai-powered-disease-prediction-syste-amber.vercel.app/)** *(Note: Ephemeral memory is enabled, so test data resets periodically)*

---

## 📝 License
This project is for educational and portfolio purposes. Do not use AI predictions as a substitute for professional medical advice.
