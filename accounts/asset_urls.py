from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .asset_views import AssetViewSet, AssetAssignmentViewSet

router = DefaultRouter()
router.register(r'assets', AssetViewSet)
router.register(r'asset-assignments', AssetAssignmentViewSet)

urlpatterns = [
    path('', include(router.urls)),
]