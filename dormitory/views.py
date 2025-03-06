from django.shortcuts import render, redirect
from django.contrib.auth.decorators import login_required
from .models import Dorm
from .forms import DormForm
from django.shortcuts import get_object_or_404
from django.contrib import messages



#addind dorm for landlord's page
@login_required
def add_dorm(request):
    if request.user.user_type != 'landlord':
        return redirect('accounts:dashboard')  
    if request.method == "POST":
        form = DormForm(request.POST, request.FILES)
        if form.is_valid():
            dorm = form.save(commit=False)
            dorm.landlord = request.user
            dorm.save()
            messages.success(request, "Dorm successfully created!")  
            return redirect('accounts:dashboard')  
    else:
        form = DormForm()

    return render(request, 'dormitory/add_dorm.html', {'form': form})

#List of dorm shown in students dashboard
@login_required
def dorm_list(request):
    dorms = Dorm.objects.filter(available=True, approval_status='approved')  # Filter for approved and available dorms
    return render(request, 'dormitory/dorm_list.html', {'dorms': dorms})

#Dorm details
@login_required
def dorm_detail(request, dorm_id):
    dorm = get_object_or_404(Dorm, id=dorm_id)
    return render(request, 'dormitory/dorm_detail.html', {'dorm': dorm})

#Landlord's Dorm
@login_required
def my_dorms(request):
    if request.user.user_type != 'landlord':
        return redirect('accounts:dashboard')  # Ensure only landlords can access

    my_dorms = Dorm.objects.filter(landlord=request.user)  # Fetch only their dorms
    return render(request, 'dormitory/my_dorms.html', {'my_dorms': my_dorms})

#Editing Dorm
@login_required
def edit_dorm(request, dorm_id):
    dorm = get_object_or_404(Dorm, id=dorm_id, landlord=request.user)

    if request.method == "POST":
        form = DormForm(request.POST, request.FILES, instance=dorm)
        if form.is_valid():
            form.save()
            messages.success(request, "Dorm successfully updated!")  # Add success message
            return redirect('accounts:dashboard')  # Redirect to the landlord's dashboard
    else:
        form = DormForm(instance=dorm)

    return render(request, 'dormitory/edit_dorm.html', {'form': form, 'dorm': dorm})

 #Deleting Dorm
@login_required
def delete_dorm(request, dorm_id):
    dorm = get_object_or_404(Dorm, id=dorm_id, landlord=request.user)

    if request.method == "POST":
        dorm.delete()
        messages.success(request, "Dorm successfully deleted!")  # Add success message
        return redirect('accounts:dashboard')  # Redirect back after deletion

    return render(request, 'dormitory/confirm_delete.html', {'dorm': dorm})