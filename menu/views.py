from rest_framework import generics
from rest_framework.permissions import AllowAny, IsAuthenticated
from .models import MenuCategory, MenuItem
from .serializers import MenuItemSerializer ,MenuCategorySerializer
from rest_framework.parsers import (
    MultiPartParser,
    FormParser
)


class PublicCategoryListView(
    generics.ListAPIView
):

    serializer_class = MenuCategorySerializer

    permission_classes = [
        AllowAny
    ]

    def get_queryset(self):

        return MenuCategory.objects.filter(
            is_active=True
        )

class PublicShopCategoryView(
    generics.ListAPIView
):

    serializer_class = MenuCategorySerializer

    permission_classes = [
        AllowAny
    ]

    def get_queryset(self):

        shop_id = self.kwargs["shop_id"]

        return MenuCategory.objects.filter(
            shop_id=shop_id,
            is_active=True
        )
        
class PublicMenuItemListView(
    generics.ListAPIView
):

    serializer_class = MenuItemSerializer

    permission_classes = [
        AllowAny
    ]

    def get_queryset(self):

        queryset = MenuItem.objects.filter(
            is_available=True
        )

        category_id = self.request.GET.get(
            "category"
        )

        if category_id:

            queryset = queryset.filter(
                category_id=category_id
            )

        return queryset
    
    
class PublicMenuItemDetailView(
    generics.RetrieveAPIView
):

    queryset = MenuItem.objects.filter(
        is_available=True
    )

    serializer_class = MenuItemSerializer

    permission_classes = [
        AllowAny
    ]
   
    
class PublicCategoryItemsView(
    generics.ListAPIView
):

    serializer_class = MenuItemSerializer

    permission_classes = [
        AllowAny
    ]

    def get_queryset(self):

        category_id = self.kwargs[
            "category_id"
        ]

        return MenuItem.objects.filter(
            category_id=category_id,
            is_available=True
        )
        

class CategoryListView(
    generics.ListAPIView
):

    serializer_class = MenuCategorySerializer

    permission_classes = [
        IsAuthenticated
    ]

    def get_queryset(self):

        return MenuCategory.objects.filter(
            is_active=True
        )
        
class CategoryListCreateView(
    generics.ListCreateAPIView
):

    serializer_class = MenuCategorySerializer

    permission_classes = [
        IsAuthenticated
    ]

    def get_queryset(self):

        user = self.request.user

        if user.role == "superadmin":
            return MenuCategory.objects.all()

        if user.role == "manager":

            try:

                shop = (
                    user.manager_profile.shop
                )

                return MenuCategory.objects.filter(
                    shop=shop
                )

            except:
                return MenuCategory.objects.none()

        return MenuCategory.objects.none()

    def perform_create(
        self,
        serializer
    ):

        user = self.request.user

        if user.role == "manager":

            serializer.save(
                shop=user.manager_profile.shop
            )

        else:

            serializer.save()
            
            
    
class CategoryDetailView(
    generics.RetrieveUpdateDestroyAPIView
):

    serializer_class = (
        MenuCategorySerializer
    )

    permission_classes = [
        IsAuthenticated
    ]

    parser_classes = [
        MultiPartParser,
        FormParser
    ]

    queryset = (
        MenuCategory.objects.all()
    )


class MenuItemListView(
    generics.ListAPIView
):

    serializer_class = MenuItemSerializer

    permission_classes = [
        IsAuthenticated
    ]

    def get_queryset(self):

        category_id = self.kwargs["category_id"]

        return MenuItem.objects.filter(
            category_id=category_id,
            is_available=True
        )
        
class MenuItemListCreateView(
    generics.ListCreateAPIView
):

    serializer_class = MenuItemSerializer

    permission_classes = [
        IsAuthenticated
    ]

    def get_queryset(self):

        user = self.request.user

        if user.role == "superadmin":
            return MenuItem.objects.all()

        if user.role == "manager":

            try:

                shop = (
                    user.manager_profile.shop
                )

                return MenuItem.objects.filter(
                    shop=shop
                )

            except:
                return MenuItem.objects.none()

        return MenuItem.objects.none()

    def perform_create(
        self,
        serializer
    ):

        user = self.request.user

        if user.role == "manager":

            serializer.save(
                shop=user.manager_profile.shop
            )

        else:

            serializer.save()


class MenuItemDetailView(
    generics.RetrieveUpdateDestroyAPIView
):

    queryset = MenuItem.objects.all()

    serializer_class = MenuItemSerializer

    permission_classes = [
        IsAuthenticated
    ]

    parser_classes = [
        MultiPartParser,
        FormParser
    ]