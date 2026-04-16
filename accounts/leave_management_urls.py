from django.urls import path
from . import views

urlpatterns = [
    path('', views.company_leaves, name='company-leaves'),
    path('<str:date>/', views.delete_company_leave, name='delete-company-leave'),
    path('../saturday-overrides/', views.saturday_overrides, name='saturday-overrides'),
]
