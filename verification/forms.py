import hashlib, hmac, re
from django import forms
from django.conf import settings
from core.images import clean_image
from .models import ProviderVerification as PV


def id_hash(doc_type, number):
    return hmac.new(settings.ID_HASH_KEY.encode(), f"{doc_type}:{number}".encode(), hashlib.sha256).hexdigest()


class VerificationForm(forms.Form):
    doc_type = forms.ChoiceField(choices=PV.DocType.choices, label="Document")
    full_name = forms.CharField(max_length=120, label="Full name exactly as on the document")
    doc_number = forms.CharField(max_length=20, label="Document number")
    id_front = forms.ImageField(label="Photo of the front")
    id_back = forms.ImageField(label="Photo of the back (National ID only)", required=False)
    selfie = forms.ImageField(label="Selfie holding the code")
    consent = forms.BooleanField(label="I consent to GlowHub processing my ID and face image to verify my identity and prevent fraud, as described in the privacy notice.")

    def clean_doc_number(self):
        n = re.sub(r"[^A-Z0-9]", "", self.cleaned_data["doc_number"].upper())
        if not 6 <= len(n) <= 15:
            raise forms.ValidationError("Enter the document number as printed.")
        return n

    def _img(self, name, required=True):
        f = self.cleaned_data.get(name)
        return clean_image(f) if f else None

    def clean_id_front(self): return self._img("id_front")
    def clean_id_back(self): return self._img("id_back")
    def clean_selfie(self): return self._img("selfie")

    def clean(self):
        cd = super().clean()
        if cd.get("doc_type") == "NATIONAL_ID" and not cd.get("id_back") and "id_back" not in self.errors:
            self.add_error("id_back", "The back of the National ID is required.")
        return cd
