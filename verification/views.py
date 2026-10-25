import secrets
from django.contrib.auth.decorators import login_required
from django.http import FileResponse, Http404
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone

from accounts.decorators import phone_verified_required
from core.services import audit, rate_limit
from .forms import VerificationForm, id_hash
from .models import ProviderVerification


@login_required
@phone_verified_required()
@rate_limit("verify", 5, 3600)
def submit(request):
    biz = getattr(request.user, "business", None)
    if not biz:
        raise Http404
    v = getattr(biz, "verification", None)
    if v and v.status in ("PENDING", "APPROVED"):
        return render(request, "verification/status.html", {"v": v})
    request.session.setdefault("vcode", f"{secrets.randbelow(10**4):04d}")
    form = VerificationForm(request.POST or None, request.FILES or None)
    if form.is_valid():
        cd = form.cleaned_data
        h = id_hash(cd["doc_type"], cd["doc_number"])
        if ProviderVerification.objects.filter(id_hash=h).exclude(business=biz).exists():
            audit(request.user, "verification.duplicate_document", biz.pk)  # flagged for staff
            form.add_error("doc_number", "This document can't be used. Contact support if you think this is a mistake.")
        else:
            obj = v or ProviderVerification(business=biz)
            for f in ("id_front", "id_back", "selfie"):  # drop any older files on resubmission
                if getattr(obj, f):
                    getattr(obj, f).delete(save=False)
            obj.doc_type, obj.full_name, obj.id_hash = cd["doc_type"], cd["full_name"], h
            obj.id_last4 = cd["doc_number"][-4:]
            obj.id_front, obj.selfie = cd["id_front"], cd["selfie"]
            if cd.get("id_back"):
                obj.id_back = cd["id_back"]
            obj.challenge_code = request.session.pop("vcode")
            obj.consent_at, obj.status = timezone.now(), "PENDING"
            obj.reviewed_by = obj.reviewed_at = None
            obj.reject_reason, obj.images_purged_at = "", None
            obj.save()
            audit(request.user, "verification.submitted", biz.pk)
            return redirect("verification")
    return render(request, "verification/form.html", {"form": form, "code": request.session["vcode"], "v": v})


@login_required
def private_file(request, pk, field):
    """Reviewer-only, every view is audited. Production: serve via short-lived signed URLs instead."""
    if field not in ("id_front", "id_back", "selfie") or not request.user.has_perm("verification.review_verification"):
        raise Http404
    v = get_object_or_404(ProviderVerification, pk=pk)
    f = getattr(v, field)
    if not f:
        raise Http404
    audit(request.user, "verification.document_viewed", v.pk, field=field)
    r = FileResponse(f.open("rb"), content_type="image/jpeg")
    r["Cache-Control"] = "no-store"
    r["X-Content-Type-Options"] = "nosniff"
    return r
