from django import forms
from .mpesa import normalize_phone


class BookingForm(forms.Form):
    slot = forms.DateTimeField()
    contact_name = forms.CharField(max_length=120)
    contact_phone = forms.CharField(max_length=20)
    notes = forms.CharField(widget=forms.Textarea, required=False, max_length=500)
    agree = forms.BooleanField(error_messages={"required": "Please accept the cancellation policy."})

    def clean_contact_phone(self):
        try:
            return normalize_phone(self.cleaned_data["contact_phone"])
        except ValueError as e:
            raise forms.ValidationError(str(e))
