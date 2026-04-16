from django.urls import path, include
from .profile_picture_view import upload_profile_picture
from .views import (
    register,
    verify_otp_and_register,
    resend_otp,
    login,
    EmployeeAPIView,
    profile_view,
    SalaryViewSet,
    save_monthly_salary,
    calculate_monthly_salary,
    auto_mark_paid_saturdays,
    get_employee_productivity_analytics,
    get_employee_activity_timeline,     
    get_employee_performance_stats,
    get_employee_calendar_events,
    generate_salary_slip_pdf,
    generate_html_salary_slip_pdf,
    preview_html_salary_slip,
    get_active_sessions,
    leave_list_create,
    leave_update_status,
    leave_update,
    get_attendance_with_leaves,
    update_attendance,
    wfh_request_list_create,
    wfh_request_update,
    export_wfh_csv,
    export_wfh_pdf,
    comp_off_request_list_create,
    comp_off_request_update,
    export_comp_off_csv,
    export_comp_off_pdf,
    use_comp_off,
    export_leaves_csv,
    export_leaves_pdf,
    get_monthly_salary_history,
    get_comp_off_balance,
    use_comp_off_balance,
    dashboard_summary_stats,
    monthly_salary_trend,
    department_wise_salary,
    attendance_analytics,
    employee_salary_distribution,
    recent_salary_activities,
    start_work_session,
    end_work_session,
    get_work_session_history,
    get_all_active_sessions,
    get_employee_work_analytics,
    get_department_work_analytics,
    employee_home_data,
    admin_home_data,
    start_work_session_with_notes,
    end_work_session_with_report,
    add_session_note,
    get_session_details,
    get_employee_work_reports,
    admin_get_employee_work_details,
    admin_get_detailed_session,
    get_comp_off_summary,
    get_one_time_ist_time,
    get_pending_requests_count,
    get_employee_notifications,
    # MODERN: New task-based endpoints
    add_task_to_session,
    complete_task_in_session,
    add_break_to_session,
    # Offer Letter
    generate_and_send_offer_letter,
    get_employee_offer_letter,
    send_offer_letter_email,
    # Relieving Letter
    generate_and_send_relieving_letter,
    get_employee_relieving_letter,
    send_relieving_letter_email,
    # Leave Management
    company_leaves,
    delete_company_leave,
    saturday_overrides,
    # Comp Off Usage Notifications
    send_comp_off_usage_notifications,
    get_comp_off_usage_notifications,
    respond_comp_off_notification,
    discard_expired_comp_off_notifications,
)
from .salary_excel_export import download_monthly_salary_excel

# Salary ViewSet mappings
salary_list = SalaryViewSet.as_view({"get": "list", "post": "create"})
salary_detail = SalaryViewSet.as_view(
    {"get": "retrieve", "put": "update", "delete": "destroy"}
)
salary_slip = SalaryViewSet.as_view({"get": "generate_slip"})

urlpatterns = [
    # Auth with OTP
    path("register/", register, name="register"),  # Step 1: Send OTP
    path("verify-otp/", verify_otp_and_register, name="verify-otp"),  # Step 2: Verify OTP & Register
    path("resend-otp/", resend_otp, name="resend-otp"),  # Resend OTP
    path("login/", login, name="login"),
    
    # Employee CRUD
    path("PostEmployee/", EmployeeAPIView.as_view(), name="AddEmployee"),
    path("GetEmployee/", EmployeeAPIView.as_view(), name="GetEmployee"),
    path("GetEmployee/<int:pk>/", EmployeeAPIView.as_view(), name="UpdateDeleteEmployee"),
    
    # Profile
    path("profile/", profile_view, name="profile"),
    
    # Leaves
    path("leaves/", leave_list_create, name="leave-list-create"),
    path("leaves/<int:pk>/update-status/", leave_update_status, name="leave-update-status"),
    path("leaves/<int:pk>/update/", leave_update, name="leave_update"),
    
    # Attendance with Leaves
    path("attendance/<int:employee_id>/<int:month>/<int:year>/", get_attendance_with_leaves, name="attendance-with-leaves"),
    path("attendance/update/", update_attendance, name="update-attendance"),
    
    # WFH Requests
    path("wfh-requests/", wfh_request_list_create, name="wfh-request-list-create"),
    path("wfh-requests/<int:pk>/", wfh_request_update, name="wfh-request-update"),
    path("wfh/export_csv/", export_wfh_csv, name="export_wfh_csv"),
    path("wfh/export_pdf/", export_wfh_pdf, name="export_wfh_pdf"),
    
    # Comp Off URLs
    path("comp-off-requests/", comp_off_request_list_create, name="comp-off-request-list-create"),
    path("comp-off-requests/<int:pk>/", comp_off_request_update, name="comp-off-request-update"),
    path("comp-off/export_csv/", export_comp_off_csv, name="export_comp_off_csv"),
    path("comp-off/export_pdf/", export_comp_off_pdf, name="export_comp_off_pdf"),
    path("use-comp-off/", use_comp_off, name="use_comp_off"),
    path("comp-off/summary/<int:employee_id>/", get_comp_off_summary, name="comp-off-summary"),
    
    
    # Leaves Export URLs
    path("leaves/export_csv/", export_leaves_csv, name="export_leaves_csv"),
    path("leaves/export_pdf/", export_leaves_pdf, name="export_leaves_pdf"),
    
    # Salaries
    path("salaries/", salary_list, name="salary-list"),
    path("salaries/<int:pk>/", salary_detail, name="salary-detail"),
    path("salaries/<int:pk>/generate-slip/", salary_slip, name="salary-generate-slip"),
    
    # Monthly Salary
    path("monthly-salary/", save_monthly_salary, name="save_monthly_salary"),
    path("monthly-salary/calculate/", calculate_monthly_salary, name="calculate_monthly_salary"),
    path("monthly-salary/history/<int:employee_id>/", get_monthly_salary_history, name="monthly_salary_history"),
    path("monthly-salary/download-excel/", download_monthly_salary_excel, name="download_monthly_salary_excel"),
    path("attendance/auto-mark-paid-saturdays/", auto_mark_paid_saturdays, name="auto_mark_paid_saturdays"),
    
    # Comp Off Balance URLs
    path("comp-off/balance/<int:employee_id>/", get_comp_off_balance, name="get_comp_off_balance"),
    path("comp-off/use-balance/", use_comp_off_balance, name="use_comp_off_balance"),
    
    # Salary Slip PDF
    path("salary-slip/<int:employee_id>/<int:month>/<int:year>/", generate_salary_slip_pdf, name="generate-salary-slip-pdf"),
    
    # HTML Salary Slip (New Beautiful Design)
    path("salary-slip-html/<int:employee_id>/<int:month>/<int:year>/", generate_html_salary_slip_pdf, name="generate-html-salary-slip-pdf"),
    path("salary-slip-preview/<int:employee_id>/<int:month>/<int:year>/", preview_html_salary_slip, name="preview-html-salary-slip"),
    
    # Dashboard URLs
    path("dashboard/summary-stats/", dashboard_summary_stats, name="dashboard-summary-stats"),
    path("dashboard/monthly-trend/<int:year>/", monthly_salary_trend, name="monthly-salary-trend"),
    path("dashboard/monthly-trend/", monthly_salary_trend, name="monthly-salary-trend-current"),
    path("dashboard/department-salary/", department_wise_salary, name="department-wise-salary"),
    path("dashboard/department-salary/<int:year>/<int:month>/", department_wise_salary, name="department-wise-salary-specific"),
    path("dashboard/attendance-analytics/", attendance_analytics, name="attendance-analytics"),
    path("dashboard/attendance-analytics/<int:year>/<int:month>/", attendance_analytics, name="attendance-analytics-specific"),
    path("dashboard/salary-distribution/", employee_salary_distribution, name="salary-distribution"),
    path("dashboard/recent-activities/", recent_salary_activities, name="recent-activities"),
    
    # Work Session URLs
    path('work-session/start/', start_work_session, name='start-work-session'),
    path('work-session/end/<uuid:session_id>/', end_work_session, name='end-work-session'),
    # MODERN: Task-based tracking endpoints
    path('work-session/add-task/<uuid:session_id>/', add_task_to_session, name='add-task-to-session'),
    path('work-session/complete-task/<uuid:session_id>/', complete_task_in_session, name='complete-task-in-session'),
    path('work-session/add-break/<uuid:session_id>/', add_break_to_session, name='add-break-to-session'),
    path('work-session/active/', get_active_sessions, name='get-active-sessions'),
    path('work-session/history/', get_work_session_history, name='work-session-history'),
    
    # Professional Work Session URLs
    path('work-session/start-with-notes/', start_work_session_with_notes, name='start-work-session-with-notes'),
    path('work-session/end-with-report/<uuid:session_id>/', end_work_session_with_report, name='end-work-session-with-report'),
    path('work-session/add-note/<uuid:session_id>/', add_session_note, name='add-session-note'),
    path('work-session/details/<uuid:session_id>/', get_session_details, name='get-session-details'),
    path('work-reports/<int:days>/', get_employee_work_reports, name='get-work-reports'),
    
    # Admin Monitoring URLs
    path('admin/active-sessions/', get_all_active_sessions, name='all-active-sessions'),
    path('admin/employee-analytics/<int:employee_id>/', get_employee_work_analytics, name='employee-analytics'),
    path('admin/department-analytics/<str:department>/', get_department_work_analytics, name='department-analytics'),
    path('admin/employee-work-details/<int:employee_id>/', admin_get_employee_work_details, name='admin-employee-work-details'),
    path('admin/session-details/<uuid:session_id>/', admin_get_detailed_session, name='admin-session-details'),
    
    # Dashboard URLs
    path('employee/home/', employee_home_data, name='employee-home'),
    path('admin/home/', admin_home_data, name='admin-home'),
    
    # Employee Analytics URLs
    path('employee/analytics/productivity/', get_employee_productivity_analytics, name='employee-productivity-analytics'),
    path('employee/analytics/timeline/', get_employee_activity_timeline, name='employee-activity-timeline'),
    path('employee/analytics/performance-stats/', get_employee_performance_stats, name='employee-performance-stats'),
    path('employee/calendar/events/', get_employee_calendar_events, name='employee-calendar-events'),
    path('employee/calendar/events/<int:year>/<int:month>/', get_employee_calendar_events, name='employee-calendar-events-specific'),
    path('get-one-time-ist-time/', get_one_time_ist_time, name='get_one_time_ist_time'),

    path('notifications/pending-count/', get_pending_requests_count),
    path('notifications/employee/', get_employee_notifications),
    
    # Offer Letter URLs
    path('offer-letter/generate/', generate_and_send_offer_letter, name='generate-offer-letter'),
    path('offer-letter/<int:employee_id>/', get_employee_offer_letter, name='get-offer-letter'),
    path('offer-letter/send/<int:employee_id>/', send_offer_letter_email, name='send-offer-letter'),
    
    # Relieving Letter URLs
    path('relieving-letter/generate/', generate_and_send_relieving_letter, name='generate-relieving-letter'),
    path('relieving-letter/<int:employee_id>/', get_employee_relieving_letter, name='get-relieving-letter'),
    path('relieving-letter/send/<int:employee_id>/', send_relieving_letter_email, name='send-relieving-letter'),
    
    # Employee Form URLs
    path('employee-form/', include('accounts.employee_form_urls')),
    
    # Profile Picture
    path('profile/upload-picture/', upload_profile_picture, name='upload-profile-picture'),
    
    # Leave Management
    path('company-leaves/', company_leaves, name='company-leaves'),
    path('company-leaves/<str:date>/', delete_company_leave, name='delete-company-leave'),
    path('saturday-overrides/', saturday_overrides, name='saturday-overrides'),
    
    # Admin Notes
    path('', include('accounts.admin_notes_urls')),
    
    # Assets Management
    path('', include('accounts.asset_urls')),

    # Comp Off Usage Notification APIs
    path('comp-off/send-usage-notifications/', send_comp_off_usage_notifications, name='send-comp-off-usage-notifications'),
    path('comp-off/usage-notifications/', get_comp_off_usage_notifications, name='get-comp-off-usage-notifications'),
    path('comp-off/usage-notifications/<int:notification_id>/respond/', respond_comp_off_notification, name='respond-comp-off-notification'),
    path('comp-off/discard-expired-notifications/', discard_expired_comp_off_notifications, name='discard-expired-comp-off-notifications'),
]