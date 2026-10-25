from django.contrib import admin
from .models import Message
admin.site.register(Message, list_display=("booking", "sender", "reported", "created_at"), list_filter=("reported",))
