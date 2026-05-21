from django.contrib.auth.models import Group
from django.core.management.base import BaseCommand

from service.access import ADMIN_GROUP, TEAM_GROUP


class Command(BaseCommand):
    help = "Cria os grupos de acesso usados pelo HigiFlow."

    def handle(self, *args, **options):
        for name in [ADMIN_GROUP, TEAM_GROUP]:
            group, created = Group.objects.get_or_create(name=name)
            status = "criado" if created else "ja existia"
            self.stdout.write(self.style.SUCCESS(f"Grupo '{group.name}' {status}."))
