from django.shortcuts import render, redirect
from django.contrib.auth import authenticate, login
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from .forms import CustomUserCreationForm
from dormitory.models import Dorm  
from django.shortcuts import get_object_or_404
from django.contrib.auth import get_user_model
from django.contrib.auth.forms import AuthenticationForm


def register(request):
    if request.method == "POST":
        form = CustomUserCreationForm(request.POST)

        # Check if username or email already exists
        username = request.POST.get('username')
        email = request.POST.get('email')
        User = get_user_model()

        if User.objects.filter(username=username).exists():
            messages.error(request, "Username already exists. Please choose a different one.")
        elif User.objects.filter(email=email).exists():
            messages.error(request, "Email is already registered. Try logging in instead.")
        elif form.is_valid():
            user = form.save()
            login(request, user)
            messages.success(request, "Registration successful! Welcome, " + user.username)
            return redirect('accounts:dashboard') 
        else:
            messages.error(request, "Registration failed. Please check the form.")

    else:
        form = CustomUserCreationForm()

    return render(request, 'accounts/register.html', {'form': form})  # ✅ Always return response



def user_login(request):
    if request.user.is_authenticated:
        messages.info(request, f"Welcome back, {request.user.username}! You are already logged in.")
        return redirect('accounts:dashboard')

    form = AuthenticationForm(request, data=request.POST or None)

    if request.method == "POST":
        if form.is_valid():
            user = form.get_user()
            login(request, user)
            messages.success(request, f"Welcome, {user.username}! You have successfully logged in.")
            return redirect('accounts:dashboard')
        else:
            messages.error(request, "Invalid username or password. Please try again.")

    return render(request, "accounts/login.html", {'form': form})  # ✅ Pass the form



@login_required
def dashboard(request):
    if not request.session.get('welcome_message_shown', False):
        if request.user.user_type == 'admin':
            pending_dorms = Dorm.objects.filter(approval_status='pending')
            messages.success(request, f"Welcome back admin, {request.user.first_name}!")
        elif request.user.user_type == 'landlord':
            messages.success(request, f"Welcome back landlord, {request.user.first_name}!")
        else:
            dorms = Dorm.objects.filter(approval_status='approved', available=True)
            messages.success(request, f"Welcome back, {request.user.first_name}!")

        # Set a session variable to indicate that the welcome message has been shown
        request.session['welcome_message_shown'] = True
    
    # Admin dashboard
    if request.user.user_type == 'admin':
        pending_dorms = Dorm.objects.filter(approval_status='pending')
        return render(request, 'accounts/admin_dashboard.html', {'pending_dorms': pending_dorms})

    # Landlord dashboard
    elif request.user.user_type == 'landlord':
        return render(request, 'accounts/landlord_dashboard.html')

    # Student dashboard
    else:
        dorms = Dorm.objects.filter(approval_status='approved', available=True)
        return render(request, 'accounts/student_dashboard.html', {'dorms': dorms})

        
@login_required
def approve_dorm(request, dorm_id):
    if request.user.user_type != 'admin':
        messages.error(request, "You are not authorized to approve dorms.")
        return redirect('accounts:dashboard')  # Redirect to the dashboard if not admin

    dorm = get_object_or_404(Dorm, id=dorm_id)
    dorm.approval_status = 'approved'
    dorm.save()
    messages.success(request, f"Dorm '{dorm.name}' has been approved.")
    return redirect('accounts:dashboard')  # Redirect to admin dashboard after approval


@login_required
def reject_dorm(request, dorm_id):
    if request.user.user_type != 'admin':
        messages.error(request, "You are not authorized to reject dorms.")
        return redirect('accounts:dashboard')  # Redirect to the dashboard if not admin

    dorm = get_object_or_404(Dorm, id=dorm_id)
    dorm.approval_status = 'rejected'
    dorm.available = False 
    dorm.save()
    messages.error(request, f"Dorm '{dorm.name}' has been rejected.")
    return redirect('accounts:dashboard')  # Redirect to admin dashboard after rejection

@login_required
def review_dorm(request, dorm_id):
    dorm = get_object_or_404(Dorm, id=dorm_id)

    # Ensure only admins can review dorms
    if request.user.user_type != 'admin':
        return redirect('accounts:dashboard')

    if request.method == 'POST':
        approval_status = request.POST.get('approval_status')
        rejection_reason = request.POST.get('rejection_reason', None)

        if approval_status == 'approved':
            dorm.approval_status = 'approved'
            dorm.save()
            messages.success(request, f"The dorm '{dorm.name}' has been approved.")
        elif approval_status == 'rejected':
            dorm.approval_status = 'rejected'
            dorm.rejection_reason = rejection_reason  
            dorm.save()
            messages.success(request, f"The dorm '{dorm.name}' has been rejected.")
        return redirect('accounts:dashboard')

    return render(request, 'accounts/review_dorm.html', {'dorm': dorm})


@login_required(login_url='/accounts/login/')  # Redirect to login if not authenticated
def role_based_redirect(request):
    """Redirect users based on their role."""
    if request.user.is_superuser:
        return redirect('/admin/')
    elif request.user.user_type == 'landlord':
        return redirect('/accounts/dashboard/')  # Redirect landlords to their dashboard
    elif request.user.user_type == 'student':
        return redirect('/accounts/dashboard/')  # Redirect students to their dashboard
    else:
        return redirect('/accounts/login/')  # Redirect unknown users to login



