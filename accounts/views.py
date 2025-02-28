from django.shortcuts import render, redirect
from django.contrib.auth import login
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from .forms import CustomUserCreationForm
from dormitory.models import Dorm  
from django.shortcuts import get_object_or_404


def register(request):
    if request.method == "POST":
        form = CustomUserCreationForm(request.POST)
        if form.is_valid():
            user = form.save()
            login(request, user)
            messages.success(request, "Registration successful! Welcome, " + user.username)
            return redirect('accounts:dashboard')  # ✅ Redirect after successful registration
        else:
            messages.error(request, "Registration failed. Please check the form.")
    else:
        form = CustomUserCreationForm()

    return render(request, 'accounts/register.html', {'form': form})  # ✅ Ensure it always returns a response
    
def user_login(request):
    if request.method == "POST":
        username = request.POST["username"]
        password = request.POST["password"]
        user = authenticate(request, username=username, password=password)

        if user is not None:
            login(request, user)
            messages.success(request, f"Welcome, {user.username}! You have successfully logged in.")
            
            if user.user_type == 'admin':
                return redirect('accounts:admin_dashboard')
            elif user.user_type == 'landlord':
                return redirect('accounts:landlord_dashboard')
            else:  # Student
                return redirect('accounts:student_dashboard')

        else:
            messages.error(request, "Invalid username or password. Please try again.")

    return render(request, "accounts/login.html")

@login_required
def dashboard(request):
    if request.user.user_type == 'admin':
        return render(request, 'accounts/admin_dashboard.html')
    elif request.user.user_type == 'landlord':
        return render(request, 'accounts/landlord_dashboard.html')
    else:  # Student Dashboard
        dorms = Dorm.objects.filter(available=True)  # Fetch only available dorms
        return render(request, 'accounts/student_dashboard.html', {'dorms': dorms})
