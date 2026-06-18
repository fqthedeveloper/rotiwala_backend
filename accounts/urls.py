from django.urls import path

from .views import (
    FirebaseLoginView,
    CustomerRegisterView,
    SaveFCMTokenView,
    PasswordLoginView,
    CreateManagerView,
    ManagerListView,
    AssignManagerView,
    ManagerDetailView
    
)

urlpatterns = [

    path(
        "register/",
        CustomerRegisterView.as_view()
    ),

    path(
        "firebase-login/",
        FirebaseLoginView.as_view()
    ),

    path(
        "password-login/",
        PasswordLoginView.as_view()
    ),


    path(
        "save-fcm-token/",
        SaveFCMTokenView.as_view()
    ),
        path(
        "managers/",
        ManagerListView.as_view()
    ),

    path(
        "create-manager/",
        CreateManagerView.as_view()
    ),
    path(
        "assign-manager/",
        AssignManagerView.as_view()
    ),
    
    path(
        "managers/<int:pk>/",
        ManagerDetailView.as_view()
    ),

]