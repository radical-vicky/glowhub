from django import forms
from django.contrib.auth.decorators import login_required
from django.shortcuts import get_object_or_404, redirect, render

from bookings.models import Booking
from core.services import notify, rate_limit
from .models import SupportTicket, TicketReply


class TicketForm(forms.ModelForm):
    class Meta:
        model = SupportTicket
        fields = ["kind", "booking", "subject", "body"]

    def __init__(self, user, *a, **kw):
        super().__init__(*a, **kw)
        from django.db.models import Q
        self.fields["booking"].queryset = Booking.objects.filter(
            Q(customer=user) | Q(business__owner=user))  # only your own bookings
        self.fields["booking"].required = False


@login_required
@rate_limit("ticket", 5)
def tickets(request):
    form = TicketForm(request.user, request.POST or None)
    if form.is_valid():
        t = form.save(commit=False)
        t.user = request.user
        t.save()
        notify(request.user, f"We received your request #{t.pk}", "Our team will reply by email and in your support inbox.")
        return redirect("ticket", t.pk)
    return render(request, "support/list.html", {"form": form, "tickets": request.user.tickets.order_by("-created_at")})


@login_required
def ticket(request, pk):
    t = get_object_or_404(SupportTicket, pk=pk, user=request.user)
    if request.method == "POST" and request.POST.get("body", "").strip() and t.status != "RESOLVED":
        TicketReply.objects.create(ticket=t, author=request.user, body=request.POST["body"][:3000])
        return redirect("ticket", t.pk)
    return render(request, "support/detail.html", {"t": t})
