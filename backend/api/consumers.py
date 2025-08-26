import json
from channels.generic.websocket import AsyncWebsocketConsumer
from channels.db import database_sync_to_async
from .models import Stream
from django.contrib.auth.models import User

class StreamConsumer(AsyncWebsocketConsumer):
    async def connect(self):
        self.stream_id = self.scope['url_route']['kwargs']['stream_id']
        self.stream_group_name = f'stream_{self.stream_id}'

        # Join stream group
        await self.channel_layer.group_add(
            self.stream_group_name,
            self.channel_name
        )

        await self.accept()

    async def disconnect(self, close_code):
        # Leave stream group
        await self.channel_layer.group_discard(
            self.stream_group_name,
            self.channel_name
        )

    async def receive(self, text_data):
        try:
            text_data_json = json.loads(text_data)
            message_type = text_data_json.get('type')
            
            if message_type == 'stream.chunk':
                # Broadcast the stream chunk to all viewers
                await self.channel_layer.group_send(
                    self.stream_group_name,
                    {
                        'type': 'stream_chunk',
                        'chunk': text_data_json.get('chunk')
                    }
                )
            elif message_type == 'stream.end':
                # Handle stream end
                await self.end_stream()
        except json.JSONDecodeError:
            pass

    async def stream_chunk(self, event):
        # Send stream chunk to WebSocket
        await self.send(text_data=json.dumps({
            'type': 'stream.chunk',
            'chunk': event['chunk']
        }))

    @database_sync_to_async
    def end_stream(self):
        try:
            stream = Stream.objects.get(id=self.stream_id)
            stream.is_live = False
            stream.save()
        except Stream.DoesNotExist:
            pass
