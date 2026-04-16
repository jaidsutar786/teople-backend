from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .admin_notes_views import AdminNoteViewSet

router = DefaultRouter()
router.register(r'admin-notes', AdminNoteViewSet)

urlpatterns = [
    path('', include(router.urls)),
]