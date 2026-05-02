from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth import login, logout, authenticate
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.db.models import Q
from django.views.decorators.csrf import ensure_csrf_cookie
from django.utils import timezone
from django.core.mail import EmailMultiAlternatives
from django.template.loader import render_to_string
from django.contrib.auth.hashers import make_password, check_password
from django.conf import settings
import random
from datetime import timedelta
from .forms import (
    EmployerSignUpForm,
    JobSeekerSignUpForm,
    JobSeekerUpdateForm,
    EmployerUpdateForm,
)
from .models import CustomUser, JobSeeker, Employer, EmailOTP
from apps.jobs.models import Application, Job  # Added Job model import
from .recommendations import get_job_recommendations  # Added AI import

OTP_TTL_MINUTES = 10
OTP_MIN_RESEND_SECONDS = 60
OTP_MAX_ATTEMPTS = 5


def _generate_otp_code():
    return f"{random.randint(0, 999999):06d}"

def _normalize_email(email: str) -> str:
    if not email:
        return email
    e = email.strip().lower()
    e = e.replace("@gamil.com", "@gmail.com").replace("@gamail.com", "@gmail.com")
    return e


def _send_otp_email(email, code, purpose):
    subject = "Your verification code"
    if purpose == EmailOTP.PURPOSE_LOGIN:
        subject = "Your login verification code"
    elif purpose == EmailOTP.PURPOSE_SIGNUP:
        subject = "Verify your email (OTP)"

    context = {
        "otp": code,
        "email": email,
        "purpose": purpose,
        "expires_minutes": OTP_TTL_MINUTES,
        "app_name": "Job Portal",
    }

    text_body = render_to_string("accounts/emails/otp.txt", context)
    html_body = render_to_string("accounts/emails/otp.html", context)

    msg = EmailMultiAlternatives(
        subject=subject,
        body=text_body,
        from_email=settings.DEFAULT_FROM_EMAIL,
        to=[email],
    )
    msg.attach_alternative(html_body, "text/html")
    msg.send(fail_silently=False)


def _create_and_send_otp(user, purpose):
    now = timezone.now()

    normalized = _normalize_email(user.email)
    if normalized and normalized != user.email:
        user.email = normalized
        user.save(update_fields=["email"])

    last = (
        EmailOTP.objects.filter(user=user, purpose=purpose)
        .order_by("-created_at")
        .first()
    )
    if last and (now - last.created_at).total_seconds() < OTP_MIN_RESEND_SECONDS:
        return None, int(OTP_MIN_RESEND_SECONDS - (now - last.created_at).total_seconds())

    code = _generate_otp_code()
    otp = EmailOTP.objects.create(
        user=user,
        email=user.email,
        purpose=purpose,
        code_hash=make_password(code),
        expires_at=now + timedelta(minutes=OTP_TTL_MINUTES),
    )
    _send_otp_email(user.email, code, purpose)
    return otp, 0

@ensure_csrf_cookie
def login_view(request):
    if request.method == 'POST':
        username_or_email = request.POST.get('username_or_email')
        password = request.POST.get('password')
        user_type = request.POST.get('user_type', 'job_seeker')

        try:
            user = CustomUser.objects.get(
                Q(username=username_or_email) | Q(email=username_or_email)
            )
            if user_type == 'job_seeker' and not user.is_job_seeker:
                messages.error(request, "Please select the correct user type (Job Seeker).")
                return render(request, 'accounts/login.html')
            elif user_type == 'employer' and not user.is_employer:
                messages.error(request, "Please select the correct user type (Employer).")
                return render(request, 'accounts/login.html')

            user = authenticate(request, username=user.username, password=password)
            if user is not None:
                if not user.email:
                    messages.error(request, "Your account has no email address. Please contact support.")
                    return render(request, 'accounts/login.html')

                try:
                    otp, wait_seconds = _create_and_send_otp(user, EmailOTP.PURPOSE_LOGIN)
                except Exception as e:
                    messages.error(request, f"Could not send OTP email: {e}")
                    if "console" in settings.EMAIL_BACKEND:
                        messages.error(request, "EMAIL_BACKEND is console; OTP is printed in server terminal.")
                    return render(request, 'accounts/login.html')
                if otp is None:
                    messages.error(request, f"Please wait {wait_seconds}s before requesting another OTP.")
                    return render(request, 'accounts/login.html')

                request.session["pending_otp_user_id"] = user.id
                request.session["pending_otp_purpose"] = EmailOTP.PURPOSE_LOGIN
                request.session["pending_otp_user_type"] = user_type
                messages.success(request, f"OTP sent to {user.email}. Please enter it to continue.")
                return redirect("accounts:otp_verify")
            else:
                messages.error(request, "Invalid password.")
        except CustomUser.DoesNotExist:
            messages.error(request, "No account found with these credentials.")
    
    return render(request, 'accounts/login.html')

def logout_view(request):
    logout(request)
    return redirect('/')

@login_required
def profile_view(request):
    if request.user.is_employer:
        return redirect('dashboard:employer_dashboard')
    elif request.user.is_job_seeker:
        return redirect('dashboard:jobseeker_dashboard')
    return redirect('jobs:home')

def employer_signup(request):
    if request.method == 'POST':
        form = EmployerSignUpForm(request.POST, request.FILES)
        if form.is_valid():
            user = form.save()
            if not user.email:
                messages.error(request, "Email is required for OTP verification.")
                user.delete()
                return render(request, 'accounts/signup_employer.html', {'form': form})

            user.is_active = False
            user.save(update_fields=["is_active"])

            try:
                otp, wait_seconds = _create_and_send_otp(user, EmailOTP.PURPOSE_SIGNUP)
            except Exception as e:
                messages.error(request, f"Could not send OTP email: {e}")
                if "console" in settings.EMAIL_BACKEND:
                    messages.error(request, "EMAIL_BACKEND is console; OTP is printed in server terminal.")
                return render(request, 'accounts/signup_employer.html', {'form': form})
            if otp is None:
                messages.error(request, f"Please wait {wait_seconds}s before requesting another OTP.")
                return render(request, 'accounts/signup_employer.html', {'form': form})

            request.session["pending_otp_user_id"] = user.id
            request.session["pending_otp_purpose"] = EmailOTP.PURPOSE_SIGNUP
            request.session["pending_otp_user_type"] = "employer"
            messages.success(request, f"OTP sent to {user.email}. Please verify to activate your account.")
            return redirect("accounts:otp_verify")
    else:
        form = EmployerSignUpForm()
    return render(request, 'accounts/signup_employer.html', {'form': form})

def jobseeker_signup(request):
    if request.method == 'POST':
        form = JobSeekerSignUpForm(request.POST, request.FILES)
        if form.is_valid():
            user = form.save()
            if not user.email:
                messages.error(request, "Email is required for OTP verification.")
                user.delete()
                return render(request, 'accounts/signup_jobseeker.html', {'form': form})

            user.is_active = False
            user.save(update_fields=["is_active"])

            try:
                otp, wait_seconds = _create_and_send_otp(user, EmailOTP.PURPOSE_SIGNUP)
            except Exception as e:
                messages.error(request, f"Could not send OTP email: {e}")
                if "console" in settings.EMAIL_BACKEND:
                    messages.error(request, "EMAIL_BACKEND is console; OTP is printed in server terminal.")
                return render(request, 'accounts/signup_jobseeker.html', {'form': form})
            if otp is None:
                messages.error(request, f"Please wait {wait_seconds}s before requesting another OTP.")
                return render(request, 'accounts/signup_jobseeker.html', {'form': form})

            request.session["pending_otp_user_id"] = user.id
            request.session["pending_otp_purpose"] = EmailOTP.PURPOSE_SIGNUP
            request.session["pending_otp_user_type"] = "job_seeker"
            messages.success(request, f"OTP sent to {user.email}. Please verify to activate your account.")
            return redirect("accounts:otp_verify")
    else:
        form = JobSeekerSignUpForm()
    return render(request, 'accounts/signup_jobseeker.html', {'form': form})

def signup_view(request):
    return render(request, 'accounts/signup_choice.html')


@ensure_csrf_cookie
def otp_verify(request):
    pending_user_id = request.session.get("pending_otp_user_id")
    purpose = request.session.get("pending_otp_purpose")
    user_type = request.session.get("pending_otp_user_type")

    if not pending_user_id or purpose not in (EmailOTP.PURPOSE_SIGNUP, EmailOTP.PURPOSE_LOGIN):
        messages.error(request, "No OTP verification is pending.")
        return redirect("accounts:login")

    user = get_object_or_404(CustomUser, id=pending_user_id)

    if request.method == "POST":
        code = (request.POST.get("otp") or "").strip()
        if not code.isdigit() or len(code) != 6:
            messages.error(request, "Please enter a valid 6-digit OTP.")
            return render(request, "accounts/otp_verify.html", {"email": user.email, "purpose": purpose})

        otp = (
            EmailOTP.objects.filter(user=user, purpose=purpose, consumed_at__isnull=True)
            .order_by("-created_at")
            .first()
        )
        if not otp:
            messages.error(request, "OTP not found. Please request a new code.")
            return render(request, "accounts/otp_verify.html", {"email": user.email, "purpose": purpose})

        if otp.is_expired:
            messages.error(request, "OTP expired. Please request a new code.")
            return render(request, "accounts/otp_verify.html", {"email": user.email, "purpose": purpose})

        if otp.attempts >= OTP_MAX_ATTEMPTS:
            messages.error(request, "Too many attempts. Please request a new OTP.")
            return render(request, "accounts/otp_verify.html", {"email": user.email, "purpose": purpose})

        if not check_password(code, otp.code_hash):
            otp.attempts = otp.attempts + 1
            otp.save(update_fields=["attempts"])
            messages.error(request, "Invalid OTP.")
            return render(request, "accounts/otp_verify.html", {"email": user.email, "purpose": purpose})

        otp.consumed_at = timezone.now()
        otp.save(update_fields=["consumed_at"])

        if purpose == EmailOTP.PURPOSE_SIGNUP and not user.is_active:
            user.is_active = True
            user.save(update_fields=["is_active"])

        login(request, user)
        request.session.pop("pending_otp_user_id", None)
        request.session.pop("pending_otp_purpose", None)
        request.session.pop("pending_otp_user_type", None)

        messages.success(request, "Verification successful.")
        if user.is_employer or user_type == "employer":
            return redirect("dashboard:employer_dashboard")
        return redirect("dashboard:jobseeker_dashboard")

    return render(request, "accounts/otp_verify.html", {"email": user.email, "purpose": purpose})


@ensure_csrf_cookie
def otp_resend(request):
    pending_user_id = request.session.get("pending_otp_user_id")
    purpose = request.session.get("pending_otp_purpose")
    if not pending_user_id or purpose not in (EmailOTP.PURPOSE_SIGNUP, EmailOTP.PURPOSE_LOGIN):
        messages.error(request, "No OTP verification is pending.")
        return redirect("accounts:login")

    user = get_object_or_404(CustomUser, id=pending_user_id)
    otp, wait_seconds = _create_and_send_otp(user, purpose)
    if otp is None:
        messages.error(request, f"Please wait {wait_seconds}s before requesting another OTP.")
        return redirect("accounts:otp_verify")

    messages.success(request, f"New OTP sent to {user.email}.")
    return redirect("accounts:otp_verify")

@login_required
def user_profile(request):
    if not request.user.is_job_seeker:
        messages.error(request, "Access denied. Job seeker account required.")
        return redirect('jobs:home')
    
    # --- AI RECOMMENDATION LOGIC START ---
    seeker = request.user.jobseeker
    # Combine skills and experience for a better AI match
    profile_text = f"{seeker.skills} {seeker.experience}"
    
    # Fetch all active jobs to compare against
    all_active_jobs = list(Job.objects.filter(is_active=True))
    
    # Get top 5 recommendations from our AI script
    recommended_jobs = get_job_recommendations(profile_text, all_active_jobs)[:5]
    # --- AI RECOMMENDATION LOGIC END ---

    context = {
        'user': request.user,
        'jobseeker': seeker,
        'applications': Application.objects.filter(job_seeker=seeker),
        'recommended_jobs': recommended_jobs,  # Added to context
    }
    return render(request, 'accounts/user_profile.html', context)

@login_required
def employer_profile(request):
    if not request.user.is_employer:
        messages.error(request, "Access denied. Employer account required.")
        return redirect('jobs:home')
    
    total_applications = Application.objects.filter(job__employer=request.user.employer).count()

    context = {
        'user': request.user,
        'employer': request.user.employer,
        'jobs': request.user.employer.jobs.all(),
        'total_applications': total_applications,
    }
    return render(request, 'accounts/employer_profile.html', context)


@login_required
def edit_account_details(request):
    if request.user.is_job_seeker:
        profile = request.user.jobseeker
        if request.method == "POST":
            form = JobSeekerUpdateForm(request.POST, request.FILES, instance=profile)
            if form.is_valid():
                form.save()
                messages.success(request, "Your account details were updated.")
                return redirect("accounts:user_profile")
        else:
            form = JobSeekerUpdateForm(instance=profile)
        return render(
            request,
            "accounts/edit_account_details.html",
            {"form": form, "account_type": "job_seeker"},
        )

    if request.user.is_employer:
        profile = request.user.employer
        if request.method == "POST":
            form = EmployerUpdateForm(request.POST, request.FILES, instance=profile)
            if form.is_valid():
                form.save()
                messages.success(request, "Your company details were updated.")
                return redirect("accounts:employer_profile")
        else:
            form = EmployerUpdateForm(instance=profile)
        return render(
            request,
            "accounts/edit_account_details.html",
            {"form": form, "account_type": "employer"},
        )

    messages.error(request, "No editable account details found.")
    return redirect("jobs:home")