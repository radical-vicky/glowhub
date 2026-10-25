from django import forms
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.forms import inlineformset_factory
from django.http import Http404
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_POST

from core.images import clean_image
from core.services import rate_limit
from subscriptions.services import require_feature
from .models import Branch, BusinessPhoto, Staff, StaffHours


def _biz(request, feature=None):
    b = getattr(request.user, "business", None)
    if not b:
        raise Http404
    if feature:
        require_feature(b, feature)  # server-side entitlement
    return b


class BranchForm(forms.ModelForm):
    class Meta:
        model = Branch
        fields = ["name", "area", "phone", "latitude", "longitude", "is_active"]


class StaffForm(forms.ModelForm):
    class Meta:
        model = Staff
        fields = ["name", "branch", "services", "is_active"]
        widgets = {"services": forms.CheckboxSelectMultiple}

    def __init__(self, biz, *a, **kw):
        super().__init__(*a, **kw)
        self.fields["services"].queryset = biz.services.all()  # only your own records
        self.fields["branch"].queryset = biz.branches.all()


StaffHoursFormSet = inlineformset_factory(
    Staff, StaffHours, fields=["weekday", "opens", "closes"], extra=3, can_delete=True,
    widgets={"opens": forms.TimeInput(attrs={"type": "time"}), "closes": forms.TimeInput(attrs={"type": "time"})})


class PhotoForm(forms.Form):
    image = forms.ImageField()
    caption = forms.CharField(max_length=120, required=False)

    def clean_image(self):
        return clean_image(self.cleaned_data["image"])


@login_required
def team(request):
    b = _biz(request)
    return render(request, "marketplace/team.html", {"b": b, "staff": b.staff.all(), "branches": b.branches.all()})


@login_required
def staff_edit(request, pk=None):
    b = _biz(request, "staff_enabled")
    obj = get_object_or_404(Staff, pk=pk, business=b) if pk else None
    form = StaffForm(b, request.POST or None, instance=obj)
    if form.is_valid():
        s = form.save(commit=False)
        s.business = b
        s.save()
        form.save_m2m()
        return redirect("team")
    return render(request, "marketplace/form.html", {"form": form, "title": "Staff member"})


@login_required
def staff_hours(request, pk):
    b = _biz(request, "staff_enabled")
    s = get_object_or_404(Staff, pk=pk, business=b)
    fs = StaffHoursFormSet(request.POST or None, instance=s)
    if fs.is_valid():
        fs.save()
        return redirect("team")
    return render(request, "marketplace/hours.html", {"fs": fs})


@login_required
def branch_edit(request, pk=None):
    b = _biz(request, "branches_enabled")
    obj = get_object_or_404(Branch, pk=pk, business=b) if pk else None
    form = BranchForm(request.POST or None, instance=obj)
    if form.is_valid():
        x = form.save(commit=False)
        x.business = b
        x.save()
        return redirect("team")
    return render(request, "marketplace/form.html", {"form": form, "title": "Branch"})


@login_required
@rate_limit("photo", 10)
def photos(request):
    b = _biz(request)
    form = PhotoForm(request.POST or None, request.FILES or None)
    if request.method == "POST":
        if b.photos.count() >= 8:
            messages.error(request, "You can upload up to 8 photos.")
        elif form.is_valid():
            BusinessPhoto.objects.create(business=b, image=form.cleaned_data["image"], caption=form.cleaned_data["caption"])
            return redirect("photos")
    return render(request, "marketplace/photos.html", {"form": form, "photos": b.photos.all()})


@login_required
@require_POST
def photo_delete(request, pk):
    p = get_object_or_404(BusinessPhoto, pk=pk, business=_biz(request))
    p.image.delete(save=False)
    p.delete()
    return redirect("photos")
