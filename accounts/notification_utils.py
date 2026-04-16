from channels.layers import get_channel_layer
from asgiref.sync import async_to_sync
import json

def send_notification(user_id, notification_data):
    """Send real-time notification to user"""
    channel_layer = get_channel_layer()
    if channel_layer:
        async_to_sync(channel_layer.group_send)(
            f'employee_{user_id}',
            {
                'type': 'notification_message',
                'message': notification_data
            }
        )

def send_leave_notification(user_id, leave_request, status):
    """Send leave status notification"""
    message = {
        'id': leave_request.id,
        'type': 'leave_status',
        'message': f'Your leave request has been {status.lower()}',
        'status': status,
        'date': leave_request.applied_at.isoformat() if leave_request.applied_at else None,
        'leave_type': leave_request.leave_type,
        'start_date': leave_request.start_date.isoformat(),
        'end_date': leave_request.end_date.isoformat(),
    }
    send_notification(user_id, message)

def send_compoff_notification(user_id, compoff_request, status):
    """Send comp off status notification"""
    message = {
        'id': compoff_request.id,
        'type': 'compoff_status',
        'message': f'Your comp off request has been {status.lower()}',
        'status': status,
        'date': compoff_request.created_at.isoformat() if compoff_request.created_at else None,
        'hours': compoff_request.hours,
        'request_date': compoff_request.date.isoformat(),
    }
    send_notification(user_id, message)

def send_wfh_notification(user_id, wfh_request, status):
    """Send WFH status notification"""
    message = {
        'id': wfh_request.id,
        'type': 'wfh_status',
        'message': f'Your WFH request has been {status.lower()}',
        'status': status,
        'date': wfh_request.created_at.isoformat() if wfh_request.created_at else None,
        'type_detail': wfh_request.type,
        'start_date': wfh_request.start_date.isoformat(),
        'end_date': wfh_request.end_date.isoformat(),
    }
    send_notification(user_id, message)