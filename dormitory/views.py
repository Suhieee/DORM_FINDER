from django.shortcuts import render, redirect
from django.contrib.auth.decorators import login_required
from .models import Dorm
from .forms import DormForm
from django.shortcuts import get_object_or_404


@login_required
def add_dorm(request):
    if request.user.user_type != 'landlord':
        return redirect('accounts:dashboard')  # ✅ Use correct namespace

    if request.method == "POST":
        form = DormForm(request.POST, request.FILES)
        if form.is_valid():
            dorm = form.save(commit=False)
            dorm.landlord = request.user
            dorm.save()
            return redirect('accounts:dashboard')  # ✅ Redirect to landlord dashboard
    else:
        form = DormForm()

    return render(request, 'dormitory/add_dorm.html', {'form': form})

@login_required
def dorm_list(request):
    dorms = Dorm.objects.filter(available=True)  # Ensure you use the correct model
    return render(request, 'dormitory/dorm_list.html', {'dorms': dorms})  # Fix variable name

@login_required
def dorm_detail(request, dorm_id):
    dorm = get_object_or_404(Dorm, id=dorm_id)
    return render(request, 'dormitory/dorm_detail.html', {'dorm': dorm})

@login_required
def my_dorms(request):
    if request.user.user_type != 'landlord':
        return redirect('accounts:dashboard')  # Ensure only landlords can access

    my_dorms = Dorm.objects.filter(landlord=request.user)  # Fetch only their dorms
    return render(request, 'dormitory/my_dorms.html', {'my_dorms': my_dorms})