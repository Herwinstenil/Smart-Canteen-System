from datetime import datetime
from django.utils import timezone
from django.db import transaction
from django.contrib import messages
from django.http import HttpResponse
from django.core.mail import send_mail
from django.template.loader import render_to_string
from django.views.decorators.http import require_POST
from django.shortcuts import render, redirect, get_object_or_404

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer

from .forms import OrderForm
from .models import MenuItem, Order, Employee, CartItem


def qr_scanner(request):
    return render(request, "qr_scanner.html")


def order_success(request, order_id):
    order = get_object_or_404(Order, id=order_id)
    return render(request, 'order_success.html', {'order': order})


def home(request):
    now_time = timezone.localtime().time()
    today = timezone.localdate().strftime('%A')

    available_items = MenuItem.objects.filter(
        available_days__name=today,
        start_time__lte=now_time,
        end_time__gte=now_time,
    ).distinct()

    form = OrderForm(menu_items=available_items)

    employee = None
    employee_id = request.session.get('employee_id')
    if employee_id:
        try:
            employee = Employee.objects.get(id=employee_id)
        except Employee.DoesNotExist:
            employee = None

    return render(request, 'home.html', {
        'menu_items': available_items,
        'form': form,
        'employee': employee
    })


def get_daily_order_number():
    today = timezone.now().date()
    last_order = Order.objects.filter(created_at__date=today).order_by('-daily_order_number').first()
    if last_order:
        return last_order.daily_order_number + 1
    return 1


@require_POST
def place_order(request):
    cart = request.session.get('cart', {})
    if not cart:
        messages.error(request, "Your cart is empty.")
        return redirect('home')

    employee_id = request.session.get('employee_id')
    if not employee_id:
        messages.error(request, "Employee not recognized. Please scan QR again.")
        return redirect('home')

    employee = get_object_or_404(Employee, id=employee_id)
    total = 0
    items_to_order = []

    for item_id, qty in cart.items():
        item = MenuItem.objects.filter(id=item_id).first()
        if not item:
            messages.warning(request, f"Item with ID {item_id} is no longer available and was removed from your cart.")
            continue

        if item.quantity < qty:
            messages.error(request, f"Not enough quantity for {item.name}. Only {item.quantity} left.")
            return redirect('cart')

        total += item.price * qty
        items_to_order.append((item, qty))

    if not items_to_order:
        messages.error(request, "No valid items in your cart.")
        request.session['cart'] = {}
        return redirect('home')

    if employee.wallet_amount < total:
        messages.error(request, f"Insufficient balance! You need ₹{total}, but have only ₹{employee.wallet_amount}.")
        return redirect('cart')

    with transaction.atomic():
        daily_order_num = get_daily_order_number()
        order = Order.objects.create(employee=employee, total_amount=0, daily_order_number=daily_order_num)

        for item, qty in items_to_order:
            item.quantity -= qty
            item.save()

            CartItem.objects.create(
                employee=employee,
                menu_item=item,
                quantity=qty,
                order=order
            )

        employee.wallet_amount -= total
        employee.save()

        order.total_amount = total
        order.save()

    send_order_email(employee, order)

    request.session['cart'] = {}
    messages.success(request, f"Order placed successfully! Remaining Balance: ₹{employee.wallet_amount}")
    return redirect('order_success', order.id)


def order_history(request):
    employee_id = request.session.get('employee_id')
    if not employee_id:
        messages.error(request, "Employee not found. Please scan your QR.")
        return redirect('home')

    employee = get_object_or_404(Employee, id=employee_id)
    orders = Order.objects.filter(employee=employee).order_by('-created_at')
    return render(request, 'order_history.html', {'orders': orders})


def verify_employee(request, employee_id):
    employee = get_object_or_404(Employee, id=employee_id)

    if request.method == 'POST':
        entered_pin = request.POST.get('pin')
        if entered_pin and entered_pin.strip() == str(employee.pin):
            request.session['employee_id'] = employee.id
            messages.success(request, f"Welcome, {employee.name}!")
            return redirect('home')
        else:
            messages.error(request, "Incorrect PIN.")

    return render(request, 'verify_employee.html', {'employee': employee})


@require_POST
def add_to_cart(request, item_id):
    cart = request.session.get('cart', {})
    quantity = int(request.POST.get('quantity', 1))
    if quantity <= 0:
        quantity = 1

    item_id_str = str(item_id)
    cart[item_id_str] = cart.get(item_id_str, 0) + quantity

    request.session['cart'] = cart
    messages.success(request, "Item added to cart.")
    return redirect('home')


def remove_from_cart(request, item_id):
    cart = request.session.get('cart', {})
    cart.pop(str(item_id), None)
    request.session['cart'] = cart
    messages.success(request, "Item removed from cart.")
    return redirect('cart')


def cart_view(request):
    cart = request.session.get('cart', {})
    cart_items = []
    total = 0

    for item_id, qty in cart.items():
        try:
            item = MenuItem.objects.get(id=item_id)
            amount = item.price * qty
            cart_items.append({
                'item': item,
                'quantity': qty,
                'amount': amount
            })
            total += amount
        except MenuItem.DoesNotExist:
            continue

    return render(request, 'cart.html', {
        'cart_items': cart_items,
        'total': total
    })


def export_daily_report_pdf(request):
    date_str = request.GET.get('date')
    if not date_str:
        return HttpResponse("Date is required.", status=400)

    try:
        date = datetime.strptime(date_str, "%Y-%m-%d").date()
    except ValueError:
        return HttpResponse("Invalid date format.", status=400)

    orders = Order.objects.filter(created_at__date=date)

    response = HttpResponse(content_type='application/pdf')
    response['Content-Disposition'] = f'attachment; filename="daily_report_{date_str}.pdf"'

    doc = SimpleDocTemplate(response, pagesize=A4)
    elements = []
    styles = getSampleStyleSheet()
    elements.append(Paragraph(f"📝 Daily Report for {date.strftime('%d-%m-%Y')}", styles['Title']))
    elements.append(Spacer(1, 12))

    data = [['Employee', 'Items Ordered', 'Total Amount', 'Time']]
    for order in orders:
        items = ", ".join([f"{item.menu_item.name} × {item.quantity}" for item in order.cartitem_set.all()])
        time = order.created_at.strftime('%I:%M %p')
        data.append([order.employee.name, items, f"₹{order.total_amount}", time])

    table = Table(data, hAlign='LEFT', colWidths=[120, 220, 80, 80])
    table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.lightgrey),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.black),
        ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, -1), 9),
        ('BOTTOMPADDING', (0, 0), (-1, 0), 8),
        ('GRID', (0, 0), (-1, -1), 0.5, colors.grey),
    ]))

    elements.append(table)
    doc.build(elements)

    return response


def send_order_email(employee, order):
    subject = f"Order Confirmation - Order #{order.daily_order_number} - {order.created_at.strftime('%Y-%m-%d')}"
    recipient = employee.email

    cart_items = CartItem.objects.filter(order=order)
    context = {
        'user': employee,
        'order': order,
        'cart_items': cart_items,
    }
    message = render_to_string('email/order_email.html', context)

    send_mail(
        subject,
        '',
        None,  # or your settings.DEFAULT_FROM_EMAIL if configured
        [recipient],
        html_message=message,
        fail_silently=False
    )


def delete_orders_by_date(request):
    if request.method == "POST":
        date_str = request.POST.get("date")  
        
        if not date_str:
            messages.error(request, "No date provided.")
            return redirect('admin:order_change_list')

        try:
            
            date = timezone.datetime.strptime(date_str, "%Y-%m-%d").date()
        except ValueError:
            messages.error(request, "Invalid date format.")
            return redirect('admin:order_change_list')

        deleted_count, _ = Order.objects.filter(created_at__date=date).delete()
        messages.success(request, f"{deleted_count} orders from {date.strftime('%d-%m-%Y')} deleted successfully.")
        return redirect('admin:order_change_list')

    return redirect('admin:order_change_list')