import os

from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.core.management.base import BaseCommand

from service.access import ADMIN_GROUP, DEV_GROUP, TEAM_GROUP


class Command(BaseCommand):
    help = "Cria os grupos de acesso usados pelo HigiFlow."

    def add_arguments(self, parser):
        parser.add_argument("--dev-username", default=os.getenv("HIGIFLOW_DEV_USERNAME"))
        parser.add_argument("--dev-password", default=os.getenv("HIGIFLOW_DEV_PASSWORD"))
        parser.add_argument("--dev-email", default=os.getenv("HIGIFLOW_DEV_EMAIL", ""))

    def handle(self, *args, **options):
        for name in [DEV_GROUP, ADMIN_GROUP, TEAM_GROUP]:
            group, created = Group.objects.get_or_create(name=name)
            status = "criado" if created else "ja existia"
            self.stdout.write(self.style.SUCCESS(f"Grupo '{group.name}' {status}."))

        username = (options.get("dev_username") or "").strip()
        password = options.get("dev_password") or ""
        email = (options.get("dev_email") or "").strip().lower()
        if not username:
            return
        if not password:
            self.stdout.write(self.style.WARNING("Dev inicial nao criado: informe HIGIFLOW_DEV_PASSWORD."))
            return

        user_model = get_user_model()
        user, created = user_model.objects.get_or_create(username=username)
        user.email = email
        user.is_active = True
        user.is_staff = True
        user.is_superuser = True
        user.set_password(password)
        user.save()
        dev_group = Group.objects.get(name=DEV_GROUP)
        user.groups.add(dev_group)
        status = "criado" if created else "atualizado"
        self.stdout.write(self.style.SUCCESS(f"Usuario dev '{username}' {status}."))
