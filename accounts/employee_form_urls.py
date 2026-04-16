from django.urls import path
from .employee_form_views import (
    submit_employee_form,
    get_employee_form_data,
    update_employee_form,
    get_all_employee_forms,
    delete_employee_document,
    request_form_revision,
    clear_revision_request
)
from .employee_toggle_view import toggle_employee_status

urlpatterns = [
    path('submit/', submit_employee_form, name='submit_employee_form'),
    path('get/', get_employee_form_data, name='get_employee_form_data'),
    path('update/', update_employee_form, name='update_employee_form'),
    path('all/', get_all_employee_forms, name='get_all_employee_forms'),
    path('document/delete/<str:document_type>/', delete_employee_document, name='delete_employee_document'),
    path('toggle-status/<int:employee_id>/', toggle_employee_status, name='toggle_employee_status'),
    path('request-revision/<int:employee_id>/', request_form_revision, name='request_form_revision'),
    path('clear-revision/', clear_revision_request, name='clear_revision_request'),
]
