from django.contrib import admin
from .models import Category, Product, UserInteraction, Coupon

admin.site.register(Category)
admin.site.register(Product)
admin.site.register(UserInteraction)


admin.site.register(Coupon)