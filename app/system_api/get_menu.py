from django.utils.decorators import method_decorator
from django.views.decorators.cache import cache_page
from django.views.decorators.vary import vary_on_cookie

from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework import viewsets
from app.views import AppAuthClass

from app.serializers import PageSerializer


SHIPPERS_PAGES = ('/', '/chat/', '/tutorial/', '/group-chat/', '/email-chat/', '/add-load/', '/my-loads/', '/my-loads/active/', '/my-loads/completed/', '/notifications/', '/settings/users/', '/settings/', '/settings/system/', '/settings/user-requests/', '/profile/')
SHIPPERS_DISPATCHER_PAGES = ('/', '/chat/', '/tutorial/', '/group-chat/', '/email-chat/', '/add-load/', '/my-loads/', '/my-loads/active/', '/my-loads/completed/', '/notifications/', '/profile/')
SHIPPERS_HR_PAGES = ('/', '/chat/', '/tutorial/', '/group-chat/', '/email-chat/', '/notifications/',)

CARRIERS_PAGES = ('/', '/chat/', '/tutorial/', '/group-chat/', '/email-chat/', '/dispatch/', '/my-loads/', '/my-loads/active/', '/my-loads/completed/', '/notifications/', '/bids/', '/delivery-control/', '/vehicles/', '/vehicles/vehicles/', '/vehicles/drivers/', '/vehicles/owners/', '/settings/users/', '/settings/groups/', '/settings/system/', '/settings/user-requests/', '/profile/', '/sms/')
CARRIERS_DISPATCHER_PAGES = ('/', '/chat/', '/tutorial/', '/group-chat/', '/email-chat/', '/dispatch/', '/my-loads/', '/my-loads/active/', '/my-loads/completed/', '/bids/', '/delivery-control/', '/notifications/', '/profile/', '/sms/', '/vehicles/vehicles/')
CARRIERS_HR_PAGES = ('/', '/chat/', '/tutorial/', '/group-chat/', '/email-chat/', '/sms/', '/dispatch/', '/vehicles/', '/vehicles/vehicles/', '/vehicles/drivers/', '/vehicles/owners/', '/profile/')

ADMIN_PAGES = '__all__'


class GenerateMenuList(AppAuthClass, viewsets.ViewSet):
    permission_classes = [IsAuthenticated]

    @method_decorator(cache_page(60*60*10))
    @method_decorator(vary_on_cookie)
    def get(self, request):
        user = request.user
        
        response = dict(
            items=PageSerializer(user.role.page_set.filter(parent_page=None), context={'request': request}, many=True).data,
        )

        return Response(response)

