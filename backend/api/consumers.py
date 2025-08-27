import json
from channels.generic.websocket import AsyncWebsocketConsumer
from channels.db import database_sync_to_async
from django.conf import settings
from django.utils import timezone
from django.contrib.auth.models import User, AnonymousUser
from rest_framework_simplejwt.backends import TokenBackend
from .models import Stream


class StreamConsumer(AsyncWebsocketConsumer):
    async def connect(self):
        self.stream_id = self.scope['url_route']['kwargs'].get('stream_id')
        self.stream_group_name = f"stream_{self.stream_id}"

        # Try to resolve an authentication token either from querystring (?token=)
        # or from the "authorization" header included in the websocket handshake.
        token = None

        # querystring (scope['query_string'] is bytes)
        qs = (self.scope.get('query_string') or b'').decode()
        if qs:
            for pair in qs.split('&'):
                if pair.startswith('token='):
                    token = pair.split('=', 1)[1]
                    break

        # headers fallback
        if not token:
            headers = {h[0].decode(): h[1].decode() for h in (self.scope.get('headers') or [])}
            auth = headers.get('authorization') or headers.get('Authorization')
            if auth and auth.lower().startswith('bearer '):
                token = auth.split(' ', 1)[1].strip()

        if token:
            user = await self._get_user_from_token(token)
            if user:
                self.scope['user'] = user

        await self.channel_layer.group_add(self.stream_group_name, self.channel_name)
        await self.accept()

    async def disconnect(self, close_code):
        await self.channel_layer.group_discard(self.stream_group_name, self.channel_name)

    async def receive(self, text_data):
        try:
            payload = json.loads(text_data)
        except json.JSONDecodeError:
            return

        message_type = payload.get('type')

        if message_type == 'stream.chunk':
            await self.channel_layer.group_send(
                self.stream_group_name,
                {
                    'type': 'stream_chunk',
                    'chunk': payload.get('chunk')
                }
            )
        elif message_type == 'stream.end':
            # Only allow the requestor if authenticated and is the host of the stream
            requester = self.scope.get('user') or AnonymousUser()
            # mark stream ended in DB
            await self.end_stream(requester)

    async def stream_chunk(self, event):
        await self.send(text_data=json.dumps({
            'type': 'stream.chunk',
            'chunk': event['chunk']
        }))

    @database_sync_to_async
    def _get_user_from_token(self, token):
        """
        Decode and validate the JWT produced by SimpleJWT, then return the User.
        If the token is invalid or the user not found, returns AnonymousUser().
        """
        try:
            token_backend = TokenBackend(algorithm='HS256', signing_key=settings.SECRET_KEY)
            valid_data = token_backend.decode(token, verify=True)
            user_id = valid_data.get('user_id') or valid_data.get('user_id')
            return User.objects.get(pk=user_id)
        except Exception:
            return AnonymousUser()

    @database_sync_to_async
    def end_stream(self, requester):
        """
        Sets the `is_live` flag to False and saved ended_at. Only the host may end the stream.
        """
        try:
            stream = Stream.objects.get(id=self.stream_id)
        except Stream.DoesNotExist:
            return

        # only host may close the stream
        if requester.is_authenticated and stream.host and requester.id == stream.host.id:
            stream.is_live = False
            stream.ended_at = timezone.now()
            stream.save()
