"""
URL configuration for Canteen project.

The `urlpatterns` list routes URLs to views. For more information please see:
    https://docs.djangoproject.com/en/5.2/topics/http/urls/
Examples:
Function views
    1. Add an import:  from my_app import views
    2. Add a URL to urlpatterns:  path('', views.home, name='home')
Class-based views
    1. Add an import:  from other_app.views import Home
    2. Add a URL to urlpatterns:  path('', Home.as_view(), name='home')
Including another URLconf
    1. Import the include() function: from django.urls import include, path
    2. Add a URL to urlpatterns:  path('blog/', include('blog.urls'))
"""
from django.urls import path
from django.conf import settings
from django.conf.urls.static import static
from django.contrib import admin
from django.contrib.auth.views import LogoutView

from Future import views
from Future.views import qr_scanner, export_daily_report_pdf

urlpatterns = [
    path('admin/', admin.site.urls),
    path('home', views.home, name='home'),
    path('', qr_scanner, name='qr_scanner'),
    path('cart/', views.cart_view, name='cart'),
    path('place_order/', views.place_order, name='place_order'),
    path('order_history/', views.order_history, name='order_history'),
    path('add-to-cart/<int:item_id>/', views.add_to_cart, name='add_to_cart'),
    path('logout/', LogoutView.as_view(next_page='qr_scanner'), name='logout'),
    path('order_success/<int:order_id>/', views.order_success, name='order_success'),
    path('export-daily-report/pdf/', export_daily_report_pdf, name='export_daily_report'),
    path('remove-from-cart/<int:item_id>/', views.remove_from_cart, name='remove_from_cart'),
    path('verify-employee/<int:employee_id>/', views.verify_employee, name='verify_employee'),
    path('delete-orders-by-date/', views.delete_orders_by_date, name='delete_orders_by_date'),
]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
