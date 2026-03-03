import pandas as pd
from sklearn.metrics.pairwise import cosine_similarity
from django.db.models import Count
from .models import UserInteraction, Product


# ==============================
# BUILD USER-PRODUCT MATRIX
# ==============================
def build_matrix():
    interactions = UserInteraction.objects.all().values(
        "user_id", "product_id", "interaction_type"
    )

    if not interactions:
        return None

    df = pd.DataFrame(list(interactions))

    # Weight purchase higher than view
    df["weight"] = df["interaction_type"].apply(
        lambda x: 3 if x == "purchase" else 1
    )

    matrix = df.pivot_table(
        index="user_id",
        columns="product_id",
        values="weight",
        aggfunc="sum",
        fill_value=0
    )

    return matrix


# ==============================
# ITEM-BASED RECOMMENDATION
# ==============================

def get_recommendations(product_id):
    from django.db.models import Count

    # Users who interacted with this product
    users_who_viewed = UserInteraction.objects.filter(
        product_id=product_id
    ).values_list("user_id", flat=True)

    # Other products those users interacted with
    recommended_products = Product.objects.filter(
        userinteraction__user_id__in=users_who_viewed
    ).exclude(
        id=product_id
    ).annotate(
        interaction_count=Count("userinteraction")
    ).order_by("-interaction_count")

    if recommended_products.exists():
        return recommended_products[:4]

    # fallback
    return Product.objects.exclude(id=product_id).order_by("-id")[:4]

from django.db.models import Count
from .models import UserInteraction, Product


def get_people_also_bought(product_id):
    """
    Returns products that were purchased by users
    who purchased the given product.
    """

    # Users who purchased this product
    users = UserInteraction.objects.filter(
        product_id=product_id,
        interaction_type="purchase"
    ).values_list("user_id", flat=True)

    if not users:
        return Product.objects.none()

    # Other products purchased by those users
    products = UserInteraction.objects.filter(
        user_id__in=users,
        interaction_type="purchase"
    ).exclude(product_id=product_id)

    product_ids = (
        products.values("product_id")
        .annotate(count=Count("product_id"))
        .order_by("-count")[:5]
    )

    recommended_ids = [item["product_id"] for item in product_ids]

    return Product.objects.filter(id__in=recommended_ids)

# ==============================
# USER-BASED RECOMMENDATION
# ==============================
def get_user_based_recommendations(user_id):
    matrix = build_matrix()

    # If no interaction data exists
    if matrix is None:
        return get_trending_products()

    # If user has no interactions yet
    if user_id not in matrix.index:
        return get_trending_products()

    similarity = cosine_similarity(matrix)

    similarity_df = pd.DataFrame(
        similarity,
        index=matrix.index,
        columns=matrix.index
    )

    similar_users = similarity_df[user_id].sort_values(ascending=False)
    similar_users = similar_users.drop(user_id)

    top_users = similar_users.head(3).index.tolist()

    recommended_products = Product.objects.filter(
        userinteraction__user_id__in=top_users
    ).distinct()

    viewed_products = matrix.loc[user_id]
    viewed_product_ids = viewed_products[viewed_products > 0].index.tolist()

    recommended_products = recommended_products.exclude(
        id__in=viewed_product_ids
    )

    if not recommended_products.exists():
        return get_trending_products()

    return recommended_products[:5]


# ==============================
# TRENDING PRODUCTS (Fallback)
# ==============================
def get_trending_products():
    return Product.objects.annotate(
        purchase_count=Count("order")
    ).order_by("-purchase_count")[:4]