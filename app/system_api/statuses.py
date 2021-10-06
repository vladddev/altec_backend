from django.utils.decorators import method_decorator
from django.views.decorators.cache import cache_page
from django.views.decorators.vary import vary_on_cookie

from app.views import AppAuthClass
from rest_framework.permissions import IsAuthenticated
from rest_framework import generics


from app.serializers import *
from app.permissions import *


class CarStatusesList(AppAuthClass, generics.ListCreateAPIView):
    permission_classes = [IsAuthenticated]
    serializer_class = CarStatusesSerializer
    queryset = CarStatus.objects.all().order_by('id')

    @method_decorator(cache_page(60*60*20))
    @method_decorator(vary_on_cookie)
    def list(self, request, *args, **kwargs):
        return super().list(request, *args, **kwargs)


class DriversStatusesList(AppAuthClass, generics.ListCreateAPIView):
    permission_classes = [IsAuthenticated]
    serializer_class = DriversStatusesSerializer
    queryset = DriverStatus.objects.all().order_by('id')

    @method_decorator(cache_page(60*60*20))
    @method_decorator(vary_on_cookie)
    def list(self, request, *args, **kwargs):
        return super().list(request, *args, **kwargs)


class LoadStatusesList(AppAuthClass, generics.ListCreateAPIView):
    permission_classes = [IsAuthenticated]
    serializer_class = LoadStatusesSerializer
    queryset = LoadStatus.objects.all().order_by('id')

    @method_decorator(cache_page(60*60*20))
    @method_decorator(vary_on_cookie)
    def list(self, request, *args, **kwargs):
        return super().list(request, *args, **kwargs)


class LoadSubStatusesList(AppAuthClass, generics.ListCreateAPIView):
    permission_classes = [IsAuthenticated]
    serializer_class = LoadSubStatusesSerializer
    queryset = LoadSubStatus.objects.all().order_by('id')

    @method_decorator(cache_page(60*60*20))
    @method_decorator(vary_on_cookie)
    def list(self, request, *args, **kwargs):
        return super().list(request, *args, **kwargs)


class BookkeepingStatusesList(AppAuthClass, generics.ListCreateAPIView):
    permission_classes = [IsAuthenticated]
    serializer_class = BookkeepingStatusesSerializer
    queryset = BookkeepingStatus.objects.all().order_by('id')


class DriversStatusDetails(AppAuthClass, generics.RetrieveUpdateDestroyAPIView):
    queryset = DriverStatus.objects.filter()
    permission_classes = [IsAuthenticated]
    serializer_class = DriversStatusesSerializer


class CarStatusDetails(AppAuthClass, generics.RetrieveUpdateDestroyAPIView):
    queryset = CarStatus.objects.filter()
    permission_classes = [IsAuthenticated]
    serializer_class = CarStatusesSerializer


class LoadStatusDetails(AppAuthClass, generics.RetrieveUpdateDestroyAPIView):
    queryset = LoadStatus.objects.filter()
    permission_classes = [IsAuthenticated]
    serializer_class = LoadStatusesSerializer


class LoadSubStatusDetails(AppAuthClass, generics.RetrieveUpdateDestroyAPIView):
    queryset = LoadSubStatus.objects.filter()
    permission_classes = [IsAuthenticated]
    serializer_class = LoadSubStatusesSerializer


class BookkeepingStatusDetails(AppAuthClass, generics.RetrieveUpdateDestroyAPIView):
    queryset = BookkeepingStatus.objects.filter()
    permission_classes = [IsAuthenticated]
    serializer_class = BookkeepingStatusesSerializer