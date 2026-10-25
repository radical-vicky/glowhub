from django.contrib.auth.models import Group, Permission
from django.core.management.base import BaseCommand

GROUPS = {
    "Finance": ["approve_refund", "approve_payout", "approve_withdrawal"],
    "Verification reviewers": ["review_verification"],
}


class Command(BaseCommand):
    help = "Create least-privilege staff groups (run after migrate)"

    def handle(self, *a, **kw):
        for name, codes in GROUPS.items():
            g, _ = Group.objects.get_or_create(name=name)
            g.permissions.set(Permission.objects.filter(codename__in=codes))
        self.stdout.write("Groups ready. Staff also need is_staff and the admin model permissions they use.")
