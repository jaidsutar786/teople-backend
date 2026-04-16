from asgiref.sync import async_to_sync
from channels.layers import get_channel_layer


def broadcast_pending_counts():
    """Admin group ko updated pending counts bhejo"""
    try:
        from .models import Leave, WFHRequest, CompOffRequest
        channel_layer = get_channel_layer()
        if channel_layer is None:
            return
        counts = {
            'leave': Leave.objects.filter(status='Pending').count(),
            'wfh': WFHRequest.objects.filter(status='Pending').count(),
            'comp_off': CompOffRequest.objects.filter(status='Pending').count(),
        }
        counts['total'] = counts['leave'] + counts['wfh'] + counts['comp_off']
        async_to_sync(channel_layer.group_send)(
            'admin_requests',
            {'type': 'pending_counts', 'data': counts}
        )
    except Exception:
        pass


def broadcast_request_update(request_type):
    """Admin group ko notify karo ki new/updated request hai"""
    try:
        channel_layer = get_channel_layer()
        if channel_layer is None:
            return
        async_to_sync(channel_layer.group_send)(
            'admin_requests',
            {'type': 'request_update', 'data': {'request_type': request_type}}
        )
        broadcast_pending_counts()
    except Exception:
        pass


def notify_employee(user_id, message):
    """Employee ko notification bhejo"""
    try:
        channel_layer = get_channel_layer()
        if channel_layer is None:
            return
        async_to_sync(channel_layer.group_send)(
            f'employee_{user_id}',
            {'type': 'notification_message', 'message': message}
        )
    except Exception:
        pass
