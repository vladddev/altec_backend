from app.middleware import TokenAuthMiddleware
from channels.routing import ProtocolTypeRouter, URLRouter
import app.routing

application = ProtocolTypeRouter({
    'websocket': TokenAuthMiddleware(
        URLRouter(
            app.routing.websocket_urlpatterns
        )
    ),
})


# query_string = scope["query_string"].decode()
# query_dict = dict(parse.parse_qsl(query_string))
# raw_token = query_dict.get("access_token")