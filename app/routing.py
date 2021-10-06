from django.urls import path
from django.conf.urls import url, include

from app import consumers

websocket_urlpatterns = [
    url(r"^ws/chat-groups/(?P<id>\w+)/$", consumers.ChatConsumer),
    url(r"^ws/chat/(?P<id>\w+)/$", consumers.GroupChatConsumer),
    url(r"^ws/all-loads/$", consumers.LoadsConsumer),
    url(r"^ws/driver-bids/(?P<group_id>\w+)/$", consumers.DriverBidsConsumer),

    url(r"^ws/company/(?P<company_hash>\w+)/$", consumers.GeneralConsumer),
]