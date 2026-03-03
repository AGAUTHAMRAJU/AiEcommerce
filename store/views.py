from django.utils import timezone
from django.shortcuts import render, get_object_or_404
from .recommender import get_recommendations, get_user_based_recommendations
from rest_framework.decorators import api_view
from rest_framework.response import Response
from .serializers import ProductSerializer
from django.contrib.auth.forms import UserCreationForm
from django.shortcuts import redirect
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.contrib.admin.views.decorators import staff_member_required
from django.contrib.auth.models import User
from django.db.models import Count, Sum
from .models import Coupon, CouponUsage, Product, Order, UserInteraction, Cart
from django.db.models.functions import TruncMonth
import json
from django.core.mail import send_mail
from django.conf import settings
from django.db.models import F
from django.contrib import messages
from django.shortcuts import get_object_or_404, redirect, render
from .models import Product, Cart, UserInteraction
from .recommender import get_recommendations



def register(request):
    if request.method == 'POST':
        form = UserCreationForm(request.POST)
        if form.is_valid():
            form.save()
            return redirect('/accounts/login/')
    else:
        form = UserCreationForm()

    return render(request, 'registration/register.html', {'form': form})


from django.core.paginator import Paginator
from django.shortcuts import render
from .models import Product


def product_list(request):
    query = request.GET.get("q")
    products = Product.objects.all().order_by("-id")

    if query:
        products = products.filter(name__icontains=query)

    personalized_products = None

    if request.user.is_authenticated:
        personalized_products = get_user_based_recommendations(request.user.id)

    return render(request, "store/product_list.html", {
        "products": products,
        "query": query,
        "personalized_products": personalized_products
    })
    
    

from django.shortcuts import render, get_object_or_404, redirect
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from .models import Product, UserInteraction, Cart, Review
from .recommender import (
    get_recommendations,
    get_user_based_recommendations,
    get_people_also_bought
)


def product_detail(request, pk):
    product = get_object_or_404(Product, pk=pk)

    # 🔹 Track view interaction
    if request.user.is_authenticated:
        UserInteraction.objects.create(
            user=request.user,
            product=product,
            interaction_type="view"
        )

    # 🔹 Handle POST actions
    if request.method == "POST":

        # -------- Add to Cart --------
        if request.POST.get("add_to_cart"):
            if not request.user.is_authenticated:
                return redirect("login")

            cart_item, created = Cart.objects.get_or_create(
                user=request.user,
                product=product
            )

            if not created:
                cart_item.quantity += 1
                cart_item.save()

            messages.success(request, "Added to cart successfully!")
            return redirect("product_detail", pk=product.id)

        # -------- Buy Now --------
        if request.POST.get("buy_now"):
            if not request.user.is_authenticated:
                return redirect("login")

            request.session["buy_now_product"] = product.id
            return redirect("payment")

        # -------- Add Review --------
        if request.POST.get("add_review"):
            if not request.user.is_authenticated:
                return redirect("login")

            rating = request.POST.get("rating")
            comment = request.POST.get("comment")

            Review.objects.create(
                user=request.user,
                product=product,
                rating=rating,
                comment=comment
            )

            messages.success(request, "Review added successfully!")
            return redirect("product_detail", pk=product.id)

    # 🔹 Recommendations

    # Item-based (Customers Also Viewed)
    recommended_products = get_recommendations(product.id)

    # Purchase-only (People Also Bought)
    people_also_bought = get_people_also_bought(product.id)

    # User-based (For You)
    personalized_products = None
    if request.user.is_authenticated:
        personalized_products = get_user_based_recommendations(request.user.id)

    # Reviews
    reviews = Review.objects.filter(product=product).order_by("-created_at")

    return render(request, "store/product_detail.html", {
        "product": product,
        "recommended_products": recommended_products,
        "people_also_bought": people_also_bought,
        "personalized_products": personalized_products,
        "reviews": reviews,
    })



   
    
def get_trending_products():
    return Product.objects.annotate(
        purchase_count=Count('order')
    ).order_by('-purchase_count')[:5]
    
    
@api_view(['GET'])
def product_list_api(request):
    products = Product.objects.all()
    serializer = ProductSerializer(products, many=True)
    return Response(serializer.data)


@api_view(['GET'])
def recommended_api(request, product_id):
    recommended_products = get_recommendations(product_id)
    serializer = ProductSerializer(recommended_products, many=True)
    return Response(serializer.data)






@login_required
def view_cart(request):
    cart_items = Cart.objects.filter(user=request.user)

    # 🔹 Handle actions
    if request.method == "POST":

        # Increase quantity
        if "increase" in request.POST:
            cart_id = request.POST.get("increase")
            item = Cart.objects.get(id=cart_id, user=request.user)
            item.quantity += 1
            item.save()

        # Decrease quantity
        elif "decrease" in request.POST:
            cart_id = request.POST.get("decrease")
            item = Cart.objects.get(id=cart_id, user=request.user)

            if item.quantity > 1:
                item.quantity -= 1
                item.save()
            else:
                item.delete()

        # Remove item
        elif "remove" in request.POST:
            cart_id = request.POST.get("remove")
            Cart.objects.filter(id=cart_id, user=request.user).delete()

        # Checkout
        elif "checkout" in request.POST:
            for item in cart_items:
                Order.objects.create(
                    user=request.user,
                    product=item.product
                )

                UserInteraction.objects.create(
                    user=request.user,
                    product=item.product,
                    interaction_type="purchase"
                )

            cart_items.delete()
            messages.success(request, "Order placed successfully!")
            return redirect("my_orders")

        return redirect("cart")

    total = sum(item.product.price * item.quantity for item in cart_items)

    return render(request, "store/cart.html", {
        "cart_items": cart_items,
        "total": total
    })
    
 


from .models import Product




@login_required
def payment_page(request):

    # =========================
    # CHECK BUY NOW SESSION
    # =========================
    buy_now_product_id = request.session.get("buy_now_product")

    if buy_now_product_id:
        # Flipkart style - single product checkout
        try:
            single_product = Product.objects.get(id=buy_now_product_id)
            cart_items = None
            subtotal = single_product.price
        except Product.DoesNotExist:
            single_product = None
            cart_items = Cart.objects.filter(user=request.user)
            subtotal = sum(item.product.price * item.quantity for item in cart_items)
    else:
        # Normal cart checkout
        single_product = None
        cart_items = Cart.objects.filter(user=request.user)
        subtotal = sum(item.product.price * item.quantity for item in cart_items)

    discount = 0
    total = subtotal
    message = ""

    # =========================
    # GET VALID COUPONS
    # =========================
    coupons = Coupon.objects.filter(
        active=True,
        expiry_date__gt=timezone.now(),
        used_count__lt=F("usage_limit")
    )

    if request.method == "POST":

        # =========================
        # APPLY COUPON
        # =========================
        if "apply_coupon" in request.POST:

            code = request.POST.get("coupon_code")

            if not code:
                message = "Please select a coupon."
            else:
                try:
                    coupon = Coupon.objects.get(code=code, active=True)

                    if coupon.expiry_date < timezone.now():
                        message = "Coupon expired."

                    elif coupon.used_count >= coupon.usage_limit:
                        message = "Coupon usage limit reached."

                    elif subtotal < coupon.minimum_amount:
                        message = f"Minimum cart amount ₹{coupon.minimum_amount} required."

                    elif CouponUsage.objects.filter(user=request.user, coupon=coupon).exists():
                        message = "You already used this coupon."

                    else:
                        discount = subtotal * (coupon.discount_percentage / 100)
                        total = subtotal - discount

                        request.session["coupon_id"] = coupon.id
                        request.session["discount"] = float(discount)
                        request.session["total"] = float(total)

                        message = "Coupon applied successfully."

                except Coupon.DoesNotExist:
                    message = "Invalid coupon."

        # =========================
        # CONFIRM ORDER (COD ONLY)
        # =========================
        elif "pay_now" in request.POST:

            discount = request.session.get("discount", 0)
            total = request.session.get("total", subtotal)
            coupon_id = request.session.get("coupon_id")

            # 🔹 BUY NOW FLOW
            if single_product:
                Order.objects.create(
                    user=request.user,
                    product=single_product,
                    status="Processing"
                )

                UserInteraction.objects.create(
                    user=request.user,
                    product=single_product,
                    interaction_type="purchase"
                )

                request.session.pop("buy_now_product", None)

            # 🔹 NORMAL CART FLOW
            else:
                for item in cart_items:
                    Order.objects.create(
                        user=request.user,
                        product=item.product,
                        status="Processing"
                    )

                    UserInteraction.objects.create(
                        user=request.user,
                        product=item.product,
                        interaction_type="purchase"
                    )

                cart_items.delete()

            # 🔹 Update coupon usage
            if coupon_id:
                try:
                    coupon = Coupon.objects.get(id=coupon_id)
                    coupon.used_count += 1
                    coupon.save()

                    CouponUsage.objects.create(
                        user=request.user,
                        coupon=coupon
                    )
                except:
                    pass

            # Clear coupon session
            request.session.pop("coupon_id", None)
            request.session.pop("discount", None)
            request.session.pop("total", None)

            # Send confirmation email
            if request.user.email:
                send_mail(
                    subject="Order Confirmation - GM Store",
                    message=f"""
Hi {request.user.username},

Your Cash On Delivery order has been placed successfully.

Total Amount: ₹{total}

Thank you for shopping with GM Store.
""",
                    from_email=settings.EMAIL_HOST_USER,
                    recipient_list=[request.user.email],
                    fail_silently=True,
                )

            return redirect("my_orders")

    return render(request, "store/payment.html", {
        "subtotal": subtotal,
        "discount": discount,
        "total": total,
        "message": message,
        "coupons": coupons,
        "single_product": single_product,
        "cart_items": cart_items,
    })
  
  
   
   
   
        
@login_required
def my_orders(request):
    orders = Order.objects.filter(user=request.user).order_by('-created_at')
    return render(request, 'store/my_orders.html', {
        'orders': orders
    })
    
    

@staff_member_required
def analytics_dashboard(request):
    total_users = User.objects.count()
    total_products = Product.objects.count()
    total_orders = Order.objects.count()
    total_interactions = UserInteraction.objects.count()

    top_products = Product.objects.annotate(
        purchase_count=Count('order')
    ).order_by('-purchase_count')[:5]

    return render(request, 'store/dashboard.html', {
        'total_users': total_users,
        'total_products': total_products,
        'total_orders': total_orders,
        'total_interactions': total_interactions,
        'top_products': top_products
    })
    
   
   
   
@staff_member_required
def analytics_dashboard(request):
    total_users = User.objects.count()
    total_products = Product.objects.count()
    total_orders = Order.objects.count()
    total_interactions = UserInteraction.objects.count()

    total_revenue = Order.objects.aggregate(
        revenue=Sum('product__price')
    )['revenue'] or 0

    top_products = Product.objects.annotate(
        purchase_count=Count('order')
    ).order_by('-purchase_count')[:5]

    # 🔹 Monthly Revenue
    monthly_revenue = (
        Order.objects
        .annotate(month=TruncMonth('created_at'))
        .values('month')
        .annotate(total=Sum('product__price'))
        .order_by('month')
    )

    revenue_labels = [item['month'].strftime("%b %Y") for item in monthly_revenue]
    revenue_data = [float(item['total']) for item in monthly_revenue]

    # 🔹 Monthly User Activity (Interactions)
    monthly_activity = (
        UserInteraction.objects
        .annotate(month=TruncMonth('created_at'))
        .values('month')
        .annotate(total=Count('id'))
        .order_by('month')
    )

    activity_labels = [item['month'].strftime("%b %Y") for item in monthly_activity]
    activity_data = [item['total'] for item in monthly_activity]

    return render(request, 'store/dashboard.html', {
        'total_users': total_users,
        'total_products': total_products,
        'total_orders': total_orders,
        'total_interactions': total_interactions,
        'total_revenue': total_revenue,
        'top_products': top_products,
        'revenue_labels': json.dumps(revenue_labels),
        'revenue_data': json.dumps(revenue_data),
        'activity_labels': json.dumps(activity_labels),
        'activity_data': json.dumps(activity_data),
    })
    
    
    
