from django.db.models.signals import post_save
from django.dispatch import receiver

from apps.accountability.models import CentroCompetencia

from .at_services import inicializar_produtos_at


@receiver(post_save, sender=CentroCompetencia, dispatch_uid="projects.produtos_at_centro")
def produtos_do_novo_centro(sender, instance, created, raw, using, **kwargs):
    if created and not raw:
        inicializar_produtos_at(instance, using=using)
