from django.contrib.auth.decorators import login_required
from django.db import transaction
from django.db.models import F
from django.http import Http404
from django.shortcuts import get_object_or_404, redirect, render
from .forms import ItemForm, MovementForm
from .models import InventoryItem


def _biz(request):
    from subscriptions.services import require_feature
    b = getattr(request.user, "business", None)
    if not b:
        raise Http404
    require_feature(b, "inventory_enabled")  # server-side entitlement
    return b


@login_required
def item_list(request):
    return render(request, "inventory/list.html", {"items": _biz(request).items.filter(is_active=True)})


@login_required
def item_create(request):
    form = ItemForm(request.POST or None)
    if form.is_valid():
        i = form.save(commit=False)
        i.business = _biz(request)
        i.save()
        return redirect("inventory")
    return render(request, "marketplace/form.html", {"form": form, "title": "Add inventory item"})


@login_required
def move_stock(request, pk):
    item = get_object_or_404(InventoryItem, pk=pk, business=_biz(request))
    form = MovementForm(request.POST or None)
    if form.is_valid():
        with transaction.atomic():
            item = InventoryItem.objects.select_for_update().get(pk=item.pk)
            m = form.save(commit=False)
            m.item, m.actor = item, request.user
            if item.quantity + m.delta < 0:
                form.add_error("delta", "Stock can't go below zero.")
            else:
                m.save()
                InventoryItem.objects.filter(pk=item.pk).update(quantity=F("quantity") + m.delta)
                return redirect("inventory")
    return render(request, "marketplace/form.html", {"form": form, "title": f"Stock movement: {item.name}"})
