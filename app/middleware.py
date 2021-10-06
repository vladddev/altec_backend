from channels.auth import AuthMiddlewareStack
from asgiref.sync import sync_to_async
from rest_framework.authtoken.models import Token
from django.contrib.auth.models import AnonymousUser
from django.db import close_old_connections
from urllib import parse

from rest_framework_jwt.settings import api_settings


jwt_decode_handler = api_settings.JWT_DECODE_HANDLER

def get_token(token):
    try:
        Token.objects.get(key=token)
    except Token.DoesNotExist:
        return None

class TokenAuthMiddleware:
    def __init__(self, inner):
        self.inner = inner

    def __call__(self, scope):
        query_string = scope["query_string"].decode()
        query_dict = dict(parse.parse_qsl(query_string))
        token = query_dict.get("access_token")
        user = None

        if token:
            sync_to_async(close_old_connections)
            # try:
            # token = Token.objects.get(key=raw_token)
            user = jwt_decode_handler(token)['user_id']
            # except:
            #     user = None
        else:
            user = None
        scope["user"] = user
        return self.inner(scope)


# TokenAuthMiddlewareStack = lambda inner: TokenAuthMiddleware(AuthMiddlewareStack(inner))