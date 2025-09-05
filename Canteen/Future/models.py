import qrcode
from io import BytesIO
from datetime import time
from django.db import models
from django.utils import timezone
from django.core.files import File


class Day(models.Model):
    name = models.CharField(max_length=10, unique=True)

    def __str__(self):
        return self.name


class Employee(models.Model):
    name = models.CharField(max_length=100)
    email = models.EmailField(unique=True)
    department = models.CharField(max_length=100)
    photo = models.ImageField(upload_to='employee_photos/', null=True, blank=True)
    pin = models.CharField(max_length=128)
    qr_code = models.ImageField(upload_to='employee_qr/', blank=True, null=True)
    wallet_amount = models.DecimalField(max_digits=10, decimal_places=2, default=0.00)

    def __str__(self):
        return self.name

    def generate_qr_code(self):
        base_url = "http://127.0.0.1:8000"  # Replace with your production URL
        qr_data = f"{base_url}/verify-employee/{self.id}/"
        qr = qrcode.make(qr_data)
        buffer = BytesIO()
        qr.save(buffer, format='PNG')
        filename = f"{self.name}_qr.png"
        self.qr_code.save(filename, File(buffer), save=False)

    def save(self, *args, **kwargs):
        is_new = not self.pk
        super().save(*args, **kwargs)
        if is_new or not self.qr_code:
            self.generate_qr_code()
            super().save(update_fields=['qr_code'])


class MenuItem(models.Model):
    name = models.CharField(max_length=100)
    description = models.TextField()
    price = models.DecimalField(max_digits=6, decimal_places=2)
    photo = models.ImageField(upload_to='menu_photos/', blank=True, null=True)
    available_days = models.ManyToManyField(Day)
    start_time = models.TimeField(default=time(0, 0))
    end_time = models.TimeField(default=time(23, 59))
    quantity = models.PositiveIntegerField(default=0)

    def __str__(self):
        return self.name

    def is_currently_available(self):
        now_time = timezone.localtime().time()
        return self.start_time <= now_time <= self.end_time and self.quantity > 0


class Order(models.Model):
    employee = models.ForeignKey(Employee, on_delete=models.CASCADE)
    items = models.ManyToManyField(MenuItem, through='OrderItem')
    total_amount = models.DecimalField(max_digits=10, decimal_places=2)
    created_at = models.DateTimeField(default=timezone.now)
    daily_order_number = models.PositiveIntegerField(default=1)

    def save(self, *args, **kwargs):
        if not self.daily_order_number:
            today = timezone.now().date()
            last_order = Order.objects.filter(created_at__date=today).order_by('-daily_order_number').first()
            self.daily_order_number = (last_order.daily_order_number + 1) if last_order else 1
        super().save(*args, **kwargs)

    def __str__(self):
        return f"Order #{self.daily_order_number} ({self.created_at.date()})"


class OrderItem(models.Model):
    order = models.ForeignKey(Order, on_delete=models.CASCADE)
    menu_item = models.ForeignKey(MenuItem, on_delete=models.CASCADE)
    quantity = models.PositiveIntegerField(null=True, blank=True)

    def __str__(self):
        return f"{self.menu_item.name} x {self.quantity} (Order #{self.order.id})"


class CartItem(models.Model):
    employee = models.ForeignKey(Employee, on_delete=models.CASCADE, blank=True, null=True)
    menu_item = models.ForeignKey(MenuItem, on_delete=models.CASCADE)
    quantity = models.PositiveIntegerField(default=1)
    order = models.ForeignKey(Order, on_delete=models.SET_NULL, null=True, blank=True)

    @property
    def total_price(self):
        return self.menu_item.price * self.quantity

    def __str__(self):
        return f"{self.menu_item.name} x {self.quantity}"
