import json
from channels.generic.websocket import AsyncWebsocketConsumer
from channels.db import database_sync_to_async
from urllib.parse import parse_qs


class NotificationConsumer(AsyncWebsocketConsumer):

    async def connect(self):
        # JWT token from query string: ws://...?token=xxx
        query_string = self.scope.get('query_string', b'').decode()
        params = parse_qs(query_string)
        token = params.get('token', [None])[0]

        user = await self.get_user_from_token(token)

        if user is None:
            await self.close()
            return

        self.user = user
        self.role = await self.get_role(user)

        # Admin joins admin group, employee joins their own group
        if self.role == 'admin':
            self.group_name = 'admin_requests'
        else:
            self.group_name = f'employee_{user.id}'

        await self.channel_layer.group_add(self.group_name, self.channel_name)
        await self.accept()

        # Send initial pending count on connect
        if self.role == 'admin':
            counts = await self.get_pending_counts()
            await self.send(text_data=json.dumps({
                'type': 'pending_counts',
                'data': counts
            }))

    async def disconnect(self, close_code):
        if hasattr(self, 'group_name'):
            await self.channel_layer.group_discard(self.group_name, self.channel_name)

    async def receive(self, text_data):
        pass

    # Called when group sends 'request_update' event
    async def request_update(self, event):
        await self.send(text_data=json.dumps({
            'type': 'request_update',
            'data': event.get('data', {})
        }))

    # Called when group sends 'pending_counts' event
    async def pending_counts(self, event):
        await self.send(text_data=json.dumps({
            'type': 'pending_counts',
            'data': event.get('data', {})
        }))

    # Called for employee notifications
    async def notification_message(self, event):
        await self.send(text_data=json.dumps({
            'type': 'notification',
            'message': event.get('message', {})
        }))

    @database_sync_to_async
    def get_user_from_token(self, token):
        if not token:
            return None
        try:
            from rest_framework_simplejwt.tokens import AccessToken
            from django.contrib.auth import get_user_model
            User = get_user_model()
            decoded = AccessToken(token)
            return User.objects.get(id=decoded['user_id'])
        except Exception:
            return None

    @database_sync_to_async
    def get_role(self, user):
        return getattr(user, 'role', 'employee')

    @database_sync_to_async
    def get_pending_counts(self):
        from .models import Leave, WFHRequest, CompOffRequest
        return {
            'leave': Leave.objects.filter(status='Pending').count(),
            'wfh': WFHRequest.objects.filter(status='Pending').count(),
            'comp_off': CompOffRequest.objects.filter(status='Pending').count(),
        }
