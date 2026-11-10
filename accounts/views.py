from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.decorators import login_required
from django.shortcuts import render, redirect
from django.utils.http import url_has_allowed_host_and_scheme
from django.views.decorators.http import require_POST
from django.contrib import messages
from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError
from django.contrib.auth import get_user_model
from .models import User
User = get_user_model()

def student_register(request):
    if request.method == 'POST':

        username = request.POST.get('username', '').strip()
        email = request.POST.get('email', '').strip()
        password = request.POST.get('password', '')
        confirm_password = request.POST.get('confirm_password', '')

        if not all([username, email, password, confirm_password]):
            messages.error(request, 'Please fill in all required fields.')
            return redirect('student_register')

        if password != confirm_password:
            messages.error(request, 'Passwords do not match.')
            return redirect('student_register')

        if User.objects.filter(username=username).exists():
            messages.error(request, 'Username already exists.')
            return redirect('student_register')

        if User.objects.filter(email=email).exists():
            messages.error(request, 'Email already exists.')
            return redirect('student_register')

        # Validate password using Django's configured validators.
        candidate_user = User(username=username, email=email)

        try:
            validate_password(password, user=candidate_user)
        except ValidationError as error:
            for message in error.messages:
                messages.error(request, message)
            return redirect('student_register')

        User.objects.create_user(
            username=username,
            email=email,
            password=password,
            role=User.STUDENT
        )

        messages.success(request, 'Student account created successfully.')
        return redirect('login')

    return render(request, 'accounts/student_register.html')


def recruiter_register(request):
    if request.method == "POST":

        username = request.POST.get("username", "").strip()
        email = request.POST.get("email", "").strip()
        password = request.POST.get("password", "")
        confirm_password = request.POST.get("confirm_password", "")

        if not all([username, email, password, confirm_password]):
            messages.error(request, "Please fill in all required fields.")
            return render(request, "accounts/recruiter_register.html")

        if password != confirm_password:
            messages.error(request, "Passwords do not match.")
            return render(request, "accounts/recruiter_register.html")

        if User.objects.filter(username=username).exists():
            messages.error(request, "This username is already taken.")
            return render(request, "accounts/recruiter_register.html")

        if User.objects.filter(email=email).exists():
            messages.error(request, "This email is already registered.")
            return render(request, "accounts/recruiter_register.html")

        # Validate password using Django's configured validators.
        candidate_user = User(username=username, email=email)

        try:
            validate_password(password, user=candidate_user)
        except ValidationError as error:
            for message in error.messages:
                messages.error(request, message)
            return render(request, "accounts/recruiter_register.html")

        try:
            User.objects.create_user(
                username=username,
                email=email,
                password=password,
                role=User.RECRUITER,
                is_recruiter_approved=False,
            )

            messages.success(
                request,
                "Registration successful! Your account is awaiting admin approval."
            )
            return redirect("login")

        except Exception:
            messages.error(
                request,
                "Registration failed. Please check the server terminal for details."
            )

    return render(request, "accounts/recruiter_register.html")




def user_login(request):
    next_url = (
    request.POST.get('next')
    or request.GET.get('next')
    or ''
).strip()
    if request.method == 'POST':
        username = request.POST.get('username')
        password = request.POST.get('password')

        user = authenticate(
            request,
            username=username,
            password=password
        )

        if user is not None:

            # Check recruiter approval.
            if (
                user.role == User.RECRUITER
                and not user.is_recruiter_approved
            ):
                messages.warning(
                    request,
                    'Your recruiter account is awaiting admin approval.'
                )
                return render(
                    request,
                    'accounts/login.html',
                    {'next': next_url}
                )

            # Log in the user.
            login(request, user)

            # Redirect students to the requested job.
            if (
                user.role == User.STUDENT
                and next_url
                and url_has_allowed_host_and_scheme(
                    url=next_url,
                    allowed_hosts={request.get_host()},
                    require_https=request.is_secure()
                )
            ):
                return redirect(next_url)

            # Default dashboard redirects.
            if user.role == User.STUDENT:
                return redirect('dashboard:student_dashboard')

            elif user.role == User.RECRUITER:
                return redirect('dashboard:recruiter_dashboard')

            elif user.is_staff or user.is_superuser:
                return redirect('dashboard:admin_dashboard')

            else:
                return redirect('dashboard:home')

        else:
            messages.error(
                request,
                'Invalid username or password.'
            )

    return render(
        request,
        'accounts/login.html',
        {'next': next_url}
    )



@login_required
@require_POST
def user_logout(request):
    logout(request)
    return redirect('home')
