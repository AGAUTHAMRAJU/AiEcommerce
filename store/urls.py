from django.urls import include, path
from . import views

urlpatterns = [
    path('', views.product_list, name='product_list'),    
    path('product/<int:pk>/', views.product_detail, name='product_detail'),
    path('accounts/', include('django.contrib.auth.urls')),  # ADD THIS
    path('api/products/', views.product_list_api),
    path('api/recommend/<int:product_id>/', views.recommended_api),
    path('register/', views.register, name='register'),
    path('my-orders/', views.my_orders, name='my_orders'),
    path('dashboard/', views.analytics_dashboard, name='dashboard'),
    path('dashboard/', views.analytics_dashboard, name='dashboard'),
    path('cart/', views.view_cart, name='cart'),
    path('payment/', views.payment_page, name='payment'),
]