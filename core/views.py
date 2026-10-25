from django.http import HttpResponse
from django.shortcuts import render


def robots(request):
    txt = "User-agent: *\nDisallow: /admin/\nDisallow: /dashboard/\nDisallow: /book/\nDisallow: /accounts/\nDisallow: /messages/\nDisallow: /support/\nDisallow: /inventory/\n"
    return HttpResponse(txt, content_type="text/plain")


def legal(request, page):
    titles = {"privacy": "Privacy notice", "terms": "Terms of service", "cancellation": "Booking, cancellation and refund terms"}
    if page not in titles:
        from django.http import Http404
        raise Http404
    return render(request, f"core/{page}.html", {"title": titles[page]})
