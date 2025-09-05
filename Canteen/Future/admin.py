from datetime import datetime
from django.contrib import admin
from django.shortcuts import render
from django.urls import path, reverse
from django.db.models import DateField
from django.utils.html import format_html
from django.db.models.functions import Cast
from django.utils.timezone import localtime
from django.core.exceptions import ObjectDoesNotExist
from django.core.files.storage import default_storage
from .models import Employee, MenuItem, Order, CartItem
from django.http import HttpResponse, HttpResponseRedirect


@admin.register(Employee)
class EmployeeAdmin(admin.ModelAdmin):
    list_display = (
        'name', 'email', 'department', 'masked_pin', 'wallet_amount',
        'photo_preview', 'qr_code_preview', 'qr_code_actions'
    )
    readonly_fields = ('qr_code_preview', 'photo_preview')

    def masked_pin(self, obj):
        return "****"
    masked_pin.short_description = 'PIN'

    def photo_preview(self, obj):
        if obj.photo:
            return format_html('<img src="{}" style="height: 80px;" />', obj.photo.url)
        return "No Photo"

    def qr_code_preview(self, obj):
        if obj.qr_code:
            return format_html('<img src="{}" width="100" height="100" />', obj.qr_code.url)
        return "No QR Code"
    qr_code_preview.short_description = 'QR Code Preview'

    def qr_code_actions(self, obj):
        if obj.qr_code:
            url = reverse('admin:download_qr', args=[obj.pk])
            return format_html(
                '<a class="button" href="{}" target="_blank">Download QR</a>',
                url
            )
        return "No QR"
    qr_code_actions.short_description = "QR Code"

    def get_urls(self):
        urls = super().get_urls()
        custom_urls = [
            path(
                'download-qr/<int:employee_id>/',
                self.admin_site.admin_view(self.download_qr),
                name="download_qr"
            ),
        ]
        return custom_urls + urls

    def download_qr(self, request, employee_id):
        employee = self.get_object(request, employee_id)
        if not employee or not employee.qr_code:
            return HttpResponse("QR Code not found.", status=404)

        file_path = employee.qr_code.path
        if not default_storage.exists(file_path):
            return HttpResponse("QR file missing.", status=404)

        with open(file_path, 'rb') as f:
            response = HttpResponse(f.read(), content_type="image/png")
            response['Content-Disposition'] = f'attachment; filename="{employee.name}_qr.png"'
            return response


@admin.register(MenuItem)
class MenuItemAdmin(admin.ModelAdmin):
    change_list_template = 'admin/menuitem_change_list.html'
    list_display = ('name', 'price', 'quantity', 'start_time', 'end_time', 'photo_preview')
    search_fields = ('name',)
    list_filter = ('available_days',)

    def get_urls(self):
        urls = super().get_urls()
        custom_urls = [
            path('view-items/<str:day>/', self.admin_site.admin_view(self.view_items_by_day), name='view_items_by_day'),
        ]
        return custom_urls + urls

    def changelist_view(self, request, extra_context=None):
        if request.GET:
            return super().changelist_view(request, extra_context)

        days = ['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday', 'Sunday']
        data = [{'day': day, 'url': reverse('admin:view_items_by_day', args=[day])} for day in days]

        context = dict(
            self.admin_site.each_context(request),
            days=data,
            has_add_permission=self.has_add_permission(request),
        )
        return render(request, 'admin/menuitem_change_list.html', context)

    def view_items_by_day(self, request, day):
        items = MenuItem.objects.filter(available_days__name=day)
        context = dict(
            self.admin_site.each_context(request),
            items=items,
            day=day,
        )
        return render(request, 'admin/menuitem_list_by_day.html', context)

    def photo_preview(self, obj):
        if obj.photo:
            return format_html('<img src="{}" width="60" height="60" style="object-fit: cover;" />', obj.photo.url)
        return "No Image"
    photo_preview.short_description = 'Image'

    def response_post_save_change(self, request, obj):
        return self._redirect_to_day_view(obj)

    def response_add(self, request, obj, post_url_continue=None):
        return self._redirect_to_day_view(obj)

    def response_delete(self, request, obj_display, obj_id):
        try:
            obj = MenuItem.objects.get(pk=obj_id)
            return self._redirect_to_day_view(obj)
        except MenuItem.DoesNotExist:
            return super().response_delete(request, obj_display, obj_id)

    def _redirect_to_day_view(self, obj):
        days = obj.available_days.all()
        if days:
            day_name = days[0].name
            url = reverse('admin:view_items_by_day', args=[day_name])
            return HttpResponseRedirect(url)
        return HttpResponseRedirect(reverse('admin:Future_menuitem_changelist'))


@admin.register(Order)
class OrderAdmin(admin.ModelAdmin):
    change_list_template = 'admin/order_change_list.html'
    date_hierarchy = 'created_at'
    ordering = ('-created_at',)
    list_filter = ('employee',)
    search_fields = ('employee__name',)

    def get_urls(self):
        urls = super().get_urls()
        custom_urls = [
            path('view-orders/<str:date>/', self.admin_site.admin_view(self.view_orders), name='view_orders_by_date'),
        ]
        return custom_urls + urls

    def changelist_view(self, request, extra_context=None):
        order_dates = Order.objects.dates('created_at', 'day', order='DESC')
        data = [{'date': date, 'url': reverse('admin:view_orders_by_date', args=[date])} for date in order_dates]

        context = dict(
            self.admin_site.each_context(request),
            dates=data,
        )
        return render(request, 'admin/order_change_list.html', context)

    def view_orders(self, request, date):
        orders = Order.objects.filter(created_at__date=date).order_by('-created_at')
        for order in orders:
            order.time = localtime(order.created_at).strftime('%I:%M %p')

        context = dict(
            self.admin_site.each_context(request),
            orders=orders,
            selected_date=date,
        )
        return render(request, 'admin/view_orders_by_date.html', context)


@admin.register(CartItem)
class CartItemAdmin(admin.ModelAdmin):
    list_display = ('order_number_display', 'employee', 'items_list', 'total_order_price')
    readonly_fields = ('items_list', 'total_order_price')

    def get_urls(self):
        urls = super().get_urls()
        custom_urls = [
            path(
                'view-cartitems/<str:date>/',
                self.admin_site.admin_view(self.view_cartitems_by_date),
                name='view_cartitems_by_date'
            ),
        ]
        return custom_urls + urls

    def changelist_view(self, request, extra_context=None):
        cart_dates = (
            CartItem.objects
            .annotate(order_date=Cast('order__created_at', DateField()))
            .exclude(order_date__isnull=True)
            .values_list('order_date', flat=True)
            .distinct()
            .order_by('-order_date')
        )

        data = [{'date': date, 'url': reverse('admin:view_cartitems_by_date', args=[date])} for date in cart_dates]

        context = dict(
            self.admin_site.each_context(request),
            dates=data,
        )
        return render(request, 'admin/cartitems_by_list.html', context)

    def view_cartitems_by_date(self, request, date):
        date_obj = datetime.strptime(date, "%Y-%m-%d").date()
        cart_items = (
            CartItem.objects
            .filter(order__created_at__date=date_obj)
            .select_related('order', 'employee')
            .order_by('order__created_at')
        )

        for idx, item in enumerate(cart_items, start=1):
            item.daily_order_number = idx
            item.total_order_price_value = sum(
                ci.total_price for ci in item.order.cartitem_set.all()
            )

        context = dict(
            self.admin_site.each_context(request),
            cart_items=cart_items,
            selected_date=date,
        )
        return render(request, 'admin/cartitems_by_date.html', context)

    def order_number_display(self, obj):
        if hasattr(obj, 'daily_order_number'):
            return f"Order #{obj.daily_order_number}"
        return f"Order #{obj.order.id}"
    order_number_display.short_description = "Order #"

    def items_list(self, obj):
        try:
            return ", ".join(
                f"{item.menu_item.name} (x{item.quantity})"
                for item in obj.order.cartitem_set.all()
            )
        except ObjectDoesNotExist:
            return "-"
    items_list.short_description = 'Items'

    def total_order_price(self, obj):
        try:
            return sum(item.total_price for item in obj.order.cartitem_set.all())
        except ObjectDoesNotExist:
            return 0
    total_order_price.short_description = 'Total Price'
