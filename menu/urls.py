# menu/urls.py

from django.urls import path
from .views import (
    PublicCategoryListView,
    PublicShopCategoryView,
    PublicMenuItemListView,
    PublicMenuItemDetailView,
    PublicCategoryItemsView,
    CategoryListCreateView,
    CategoryDetailView,
    MenuItemListCreateView,
    MenuItemDetailView,
)

urlpatterns = [
    # ==================================
    # PUBLIC CUSTOMER ROUTES
    # ==================================
    path("public/categories/", PublicCategoryListView.as_view()),
    path("public/shop/<int:shop_id>/categories/", PublicShopCategoryView.as_view()),
    path("shop/<int:shop_id>/categories/", PublicShopCategoryView.as_view()),
    path("public/items/", PublicMenuItemListView.as_view()),
    path("public/item/<int:pk>/", PublicMenuItemDetailView.as_view()),
    path("public/category/<int:category_id>/items/", PublicCategoryItemsView.as_view()),

    # ==================================
    # ADMIN / MANAGER
    # ==================================
    path("categories/", CategoryListCreateView.as_view()),
    path("categories/<int:pk>/", CategoryDetailView.as_view()),
    path("items/", MenuItemListCreateView.as_view()),
    path("items/<int:pk>/", MenuItemDetailView.as_view()),
]