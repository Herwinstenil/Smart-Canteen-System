from .models import Employee
from django.dispatch import receiver
from django.db.models.signals import post_save

@receiver(post_save, sender=Employee)
def generate_qr(sender, instance, created, **kwargs):
    if created and not instance.qr_code:
        instance.generate_qr_code()
        instance.save()
