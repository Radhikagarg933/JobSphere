from django.core.management.base import BaseCommand
from django.contrib.auth import get_user_model

from apps.accounts.models import EmailOTP
from apps.accounts.views import _create_and_send_otp


class Command(BaseCommand):
    help = "Send an OTP email using the same code path as login/signup."

    def add_arguments(self, parser):
        parser.add_argument("--username", help="Username to send OTP to")
        parser.add_argument("--email", help="Email address to find user by")

    def handle(self, *args, **options):
        username = options.get("username")
        email = options.get("email")

        if not username and not email:
            raise SystemExit("Provide --username or --email")

        User = get_user_model()
        user = None
        if username:
            user = User.objects.filter(username=username).first()
        if user is None and email:
            user = User.objects.filter(email__iexact=email).first()

        if user is None:
            raise SystemExit("User not found")

        self.stdout.write(f"User: {user.username} <{user.email}>")
        self.stdout.write(f"Purpose: {EmailOTP.PURPOSE_LOGIN}")

        otp, wait = _create_and_send_otp(user, EmailOTP.PURPOSE_LOGIN)
        if otp is None:
            raise SystemExit(f"Rate limited. Wait {wait}s and try again.")

        self.stdout.write(self.style.SUCCESS("OTP email send attempted (check inbox + spam)."))
