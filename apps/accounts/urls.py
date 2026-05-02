from django.urls import path
from . import views
from django.contrib.auth import views as auth_views

app_name = 'accounts'

urlpatterns = [
    path('signup/', views.signup_view, name='signup'),
    path('login/', views.login_view, name='login'),
    path('logout/', views.logout_view, name='logout'),
    path('signup/employer/', views.employer_signup, name='employer_signup'),
    path('signup/jobseeker/', views.jobseeker_signup, name='jobseeker_signup'),
    path('otp/', views.otp_verify, name='otp_verify'),
    path('otp/resend/', views.otp_resend, name='otp_resend'),
    path('profile/', views.user_profile, name='user_profile'),
    path('employer/profile/', views.employer_profile, name='employer_profile'),
    path('account/edit/', views.edit_account_details, name='edit_account_details'),
    path('password_reset/', 
         auth_views.PasswordResetView.as_view(template_name='accounts/password_reset.html'),
         name='password_reset'),
    path('password_reset/done/',
         auth_views.PasswordResetDoneView.as_view(template_name='accounts/password_reset_done.html'),
         name='password_reset_done'),
    path('reset/<uidb64>/<token>/',
         auth_views.PasswordResetConfirmView.as_view(template_name='accounts/password_reset_confirm.html'),
         name='password_reset_confirm'),
    path('reset/done/',
         auth_views.PasswordResetCompleteView.as_view(template_name='accounts/password_reset_complete.html'),
         name='password_reset_complete'),
]