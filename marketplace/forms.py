from django import forms
from django.core.files.uploadedfile import UploadedFile
from core.images import clean_image
from django.forms import inlineformset_factory
from .models import AvailabilityBlock, Business, BusinessHours, Review, Service


class BusinessForm(forms.ModelForm):
    class Meta:
        model = Business
        fields = ["name", "slug", "description", "categories", "phone", "area",
                  "latitude", "longitude", "show_exact_location"]
        widgets = {"categories": forms.CheckboxSelectMultiple}


class BusinessEditForm(forms.ModelForm):
    class Meta:
        model = Business
        fields = ["logo", "cover_image", "description", "categories", "phone", "area", "latitude", "longitude",
                  "show_exact_location", "buffer_minutes", "deposit_percent", "cancellation_policy"]
        widgets = {"categories": forms.CheckboxSelectMultiple}

    def _img(self, name, px):  # validate and re-encode new uploads (strips location metadata)
        f = self.cleaned_data.get(name)
        return clean_image(f, max_px=px) if isinstance(f, UploadedFile) else f

    def clean_logo(self):
        return self._img("logo", 600)

    def clean_cover_image(self):
        return self._img("cover_image", 2000)


class ServiceForm(forms.ModelForm):
    class Meta:
        model = Service
        fields = ["name", "description", "price", "duration_minutes", "is_active"]


HoursFormSet = inlineformset_factory(
    Business, BusinessHours, fields=["weekday", "opens", "closes"], extra=3, can_delete=True,
    widgets={"opens": forms.TimeInput(attrs={"type": "time"}), "closes": forms.TimeInput(attrs={"type": "time"})})


class BlockForm(forms.ModelForm):
    class Meta:
        model = AvailabilityBlock
        fields = ["start", "end", "reason"]
        widgets = {"start": forms.DateTimeInput(attrs={"type": "datetime-local"}),
                   "end": forms.DateTimeInput(attrs={"type": "datetime-local"})}


class ReviewForm(forms.ModelForm):
    class Meta:
        model = Review
        fields = ["rating", "comment"]
