from django.core.management.base import BaseCommand
from django.contrib.auth.models import User
from store.models import Category, Product
from random import randint


class Command(BaseCommand):
    help = "Seed database with sample data"

    def handle(self, *args, **kwargs):

        # Create Categories
        categories = ["Electronics", "Fashion", "Books", "Sports"]

        for cat in categories:
            Category.objects.get_or_create(name=cat)

        self.stdout.write(self.style.SUCCESS("Categories created"))

        # Create Products
        all_categories = Category.objects.all()

        for i in range(1, 21):
            Product.objects.get_or_create(
                name=f"Product {i}",
                description="Sample product description",
                price=randint(500, 5000),
                category=all_categories[randint(0, len(all_categories)-1)]
            )

        self.stdout.write(self.style.SUCCESS("Products created"))

        # Create Test Users
        users = ["cust1", "cust2", "cust3"]

        for username in users:
            if not User.objects.filter(username=username).exists():
                User.objects.create_user(
                    username=username,
                    password="test1234"
                )

        self.stdout.write(self.style.SUCCESS("Users created"))