from channels.routing import ProtocolTypeRouter, URLRouter
from django.urls import re_path
from api.consumers import StreamConsumer

application = ProtocolTypeRouter({
    'websocket': URLRouter([
        re_path(r'ws/stream/(?P<stream_id>\w+)/$', StreamConsumer.as_asgi()),
    ])
})
