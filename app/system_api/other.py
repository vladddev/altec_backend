from django.utils.decorators import method_decorator
from django.views.decorators.cache import cache_page
from django.views.decorators.vary import vary_on_cookie

from datetime import datetime, timedelta, date
from geopy import distance
from django.http import HttpResponseRedirect
from django.db.models import Q, Sum, F
from rest_framework.parsers import MultiPartParser
from app.views import AppAuthClass
from app.helpers import data_filters

import re, time, json, requests, random, base64

from twilio.rest import Client
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework import generics, viewsets
from rest_framework.views import APIView

from app.models import User
from app.serializers import *
from app.permissions import *
from app.pagination import *
from app.helpers.data_filters import *
from app.helpers.get_user_owner import get_user_owner
from app.system_api.email_classes import LoadParser

from api import settings



SHIPPERS_PAGES = ('/', '/chat/', '/group-chat/', '/email-chat/', '/add-load/', '/my-loads/', '/my-loads/active/', '/my-loads/completed/', '/notifications/', '/settings/users/', '/settings/', '/settings/system/', '/settings/user-requests/', '/profile/')
SHIPPERS_DISPATCHER_PAGES = ('/', '/chat/', '/group-chat/', '/email-chat/', '/add-load/', '/my-loads/', '/my-loads/active/', '/my-loads/completed/', '/notifications/', '/profile/')
SHIPPERS_HR_PAGES = ('/', '/chat/', '/group-chat/', '/email-chat/', '/notifications/',)

CARRIERS_PAGES = ('/', '/chat/', '/group-chat/', '/email-chat/', '/dispatch/', '/my-loads/', '/my-loads/active/', '/my-loads/completed/', '/notifications/', '/bids/', '/delivery-control/', '/vehicles/', '/vehicles/vehicles/', '/vehicles/drivers/', '/vehicles/owners/', '/settings/users/', '/settings/groups/', '/settings/system/', '/settings/user-requests/', '/profile/', '/sms/')
CARRIERS_DISPATCHER_PAGES = ('/', '/chat/', '/group-chat/', '/email-chat/', '/dispatch/', '/my-loads/', '/my-loads/active/', '/my-loads/completed/', '/bids/', '/delivery-control/', '/notifications/', '/profile/', '/sms/', '/vehicles/vehicles/')
CARRIERS_HR_PAGES = ('/', '/chat/', '/group-chat/', '/email-chat/', '/sms/', '/dispatch/', '/vehicles/', '/vehicles/vehicles/', '/vehicles/drivers/', '/vehicles/owners/', '/profile/')

ADMIN_PAGES = '__all__'

async def send_update_loads_notice():
    import websockets

    uri = "wss://altekloads.com/ws/company/0/"
    async with websockets.connect(uri) as ws:
         ws.send(json.dumps({
            'action': 'update_loads',
            'data': {}
        }))

def decode_base64(data, altchars=b'+/'):
    output = list()
    splitted_body = data.split('-')
    
    for body_part in splitted_body:
        splitted_body_part = body_part.split('_')
        for small_part in splitted_body_part:
            padding = len(small_part) % 4
            if padding > 0:
                small_part += '=' * padding
            output.append(base64.b64decode(small_part).decode('utf-8'))                    
                    
    return ''.join(output) 



class LoadFileUploadView(AppAuthClass, APIView):
    parser_classes = [MultiPartParser]
    permission_classes = [IsAuthenticated]

    def put(self, request, format=None):
        # post = request.data
        # return Response({
        #         'result': post
        #     })
        post = request.data
        load = None
        if 'load' not in post:
            return Response({
                'result': 'load id is empty'
            })

        # try:
        #     load = Load.objects.get(id=int(post['load_id']))
        # except:
        #     return Response({
        #         'result': 'Load #' + post['load_id'] + ' not found'
        #     })

        if 'file' not in post:
            return Response({
                'result': 'File not found'
            })

        serializer = DocumentSerializer(data=post, context={'request': request})
        serializer.is_valid(raise_exception=True)
        document = serializer.save()

        return Response({
            'result': 'Ok'
        })
            
    def get(self, request):
        serializer = DocumentSerializer(Documents.objects.all(), many=True)
        return Response(serializer.data)


class FileUploadView(AppAuthClass, APIView):
    parser_classes = [MultiPartParser]
    permission_classes = [IsAuthenticated]

    def put(self, request, format=None):            
        serializer = FileSerializer(data=request.data, context={'request': request})
        serializer.is_valid(raise_exception=True)
        serializer.save()

        return Response(serializer.data)

    def get(self, request):
        serializer = FileSerializer(File.objects.all(), many=True)
        return Response(serializer.data)


class FileDetail(AppAuthClass, generics.RetrieveUpdateDestroyAPIView):
    serializer_class = FileSerializer
    permission_classes = [IsAuthenticated]
    queryset = File.objects.filter()


class TutorialUploadView(AppAuthClass, generics.ListAPIView):
    permission_classes = [IsAuthenticated]
    serializer_class = TutorialSerializer

    def get_queryset(self):
        user = self.request.user
        return Tutorial.objects.filter(company_instance=user.company_instance)

    @method_decorator(cache_page(60*60*2))
    @method_decorator(vary_on_cookie)
    def get(self, request, *args, **kwargs):
        return super().get(request, *args, **kwargs)


class TutorialCreateView(AppAuthClass, generics.CreateAPIView):
    permission_classes = [IsAuthenticated]
    serializer_class = TutorialCreateSerializer
    queryset = Tutorial.objects.filter()

    def perform_create(self, serializer):
        user = self.request.user
        serializer.save(company_instance=user.company_instance)


class TutorialDetail(AppAuthClass, generics.RetrieveUpdateDestroyAPIView):
    serializer_class = TutorialSerializer
    permission_classes = [IsAuthenticated]
    queryset = Tutorial.objects.filter()

    def put(self, request, *args, **kwargs):
        return self.partial_update(request, *args, **kwargs)


class HRAPIView(AppAuthClass, viewsets.ViewSet):
    permission_classes = [IsAuthenticated]

    def check_drivers(self, request):
        get = request.query_params
        output = {
            'user_exists': False
        }

        if User.objects.filter(email=get['email']).exists():
            output = {
                'user_exists': True
            }

        return Response(output)

    def add_drivers(self, request):
        post = request.data
        user = request.user

        # return Response({
        #     'result': request.data
        # }) 

        new_driver = None
        new_driver_info = None
        new_owner = None
        new_car = None
        new_drivers = list()
        new_owner_info = None
        working_group = None
        working_group = WorkingGroup.objects.filter(company_instance=user.company_instance, group_name="Unassigned").first()

        driver_phone = data_filters.phone_filter(post['drivers']['phones'][0], '1')
        owner_phone = data_filters.phone_filter(post['owner']['phones'][0], '1')
        
        if User.objects.filter(email=post['owner']['email']).exists():

            new_owner = User.objects.get(email=post['owner']['email'])

            if not hasattr(new_owner, 'owner_info') or new_owner.owner_info == None:
                new_owner_info = CarOwner.objects.create(
                    city=post['owner']['city'],
                    state=post['owner']['state'],
                    user=new_owner,
                    company_name=post['owner']['companyName']
                )
            else:
                new_owner_info = new_owner.owner_info
                new_owner_info.city = post['owner']['city']
                new_owner_info.state = post['owner']['state']
                new_owner_info.company_name = post['owner']['companyName']
                new_owner_info.save(update_fields=['city', 'state', 'company_name'])

            new_owner.first_name = post['owner']['firstName']
            new_owner.last_name = post['owner']['lastName']
            new_owner.phone_number = owner_phone
            new_owner.address = post['owner']['address']
            new_owner.zip_code = post['owner']['zip']
            new_owner.save(update_fields=['first_name', 'last_name', 'phone_number', 'address', 'zip_code'])
        else:
            owner_data = {
                'email': post['owner']['email'],
                'password': 'password',
                'first_name': post['owner']['firstName'],
                'last_name': post['owner']['lastName'],
                'phone_number': owner_phone,
                'address': post['owner']['address'],
                'zip_code': post['owner']['zip'],
                'working_group': working_group
            }

            owner_serializer = CarOwnerSerializer(data=owner_data, context={'request': request})
            owner_serializer.is_valid(raise_exception=True)
            new_owner = owner_serializer.save(company_instance=user.company_instance)

            new_owner_info = CarOwner.objects.create(
                city=post['owner']['city'],
                state=post['owner']['state'],
                user=new_owner,
                company_name=post['owner']['companyName']
            )


        bing_resp = requests.get("http://dev.virtualearth.net/REST/v1/Locations?query=" + str(post['owner']['zip']) + "&key=" + settings.BING_API_KEY)
        json_bing_resp = json.loads(bing_resp.text)
        str_coords = ''
        
        if json_bing_resp['statusCode'] == 200:
            if len(json_bing_resp['resourceSets'][0]['resources']) > 0:
                coords = json_bing_resp['resourceSets'][0]['resources'][0]['point']['coordinates']
                str_coords = str(coords[0]) + ',' + str(coords[1])

        driver = post['drivers']

        if driver['email'] != post['owner']['email'] and driver_phone != owner_phone:

            if User.objects.filter(email=driver['email']).exists():
                new_driver = User.objects.get(email=driver['email'])

                new_driver.first_name = driver['firstName']
                new_driver.phone_number = driver_phone
                new_driver.address = driver['address']
                new_driver.zip_code = driver['zip']
                new_driver.emergency_phone = driver['emergencyContactPhone']
                new_driver.emergency_name = driver['emergencyContactName']
                new_driver.license_expiration_date = round(datetime.strptime(driver['licenseExpires'], "%m/%d/%Y").timestamp())
                new_driver.address = driver['address']
                new_driver.save(update_fields=['first_name', 'phone_number', 'address', 'zip_code', 'emergency_phone', 'emergency_name', 'license_expiration_date', 'address'])
            else:
                driver_data = {
                    'email': driver['email'],
                    'password': 'password',
                    'first_name': driver['firstName'],
                    'phone_number': driver_phone,
                    'emergency_phone': driver['emergencyContactPhone'],
                    'emergency_name': driver['emergencyContactName'],
                    'license_expiration_date': round(datetime.strptime(driver['licenseExpires'], "%m/%d/%Y").timestamp()),
                    'address': driver['address'],
                    'password': 'password',
                    'zip_code': driver['zip'],
                    'working_group': working_group,
                }

                driver_serializer = DriverCreateSerializer(data=driver_data, context={'request': request})
                driver_serializer.is_valid(raise_exception=True)
                new_driver = driver_serializer.save(company_instance=user.company_instance)
                driver_info = DriverInfo.objects.create(owner=new_owner.owner_info, user=new_driver, location=str_coords, unique_sms_key=random.randint(1000, 9999))

                chat = Chat.objects.create(driver=driver_info, company_instance=user.company_instance)
                chat.users.set(set([new_driver.pk, new_owner.pk]))
                dispatchers = list(User.objects.filter(role=5, company_instance=user.company_instance))
                chat.users.add(*dispatchers)

                account_sid = user.company_instance.twilio_account_sid
                auth_token = user.company_instance.twilio_auth_token
                messaging_service_sid = user.company_instance.twilio_messaging_service_sid
                content = "Congrats! You've been approved as a driver partner for " + user.company_instance.name + "! \nTo start getting loads, download our app 'ALTEK Drivers' for Android: https://play.google.com/store/apps/details?id=au.com.altekdrivers \nFor iOS: https://apps.apple.com/app/id1549665236"
                to_number = driver_phone
                client = Client(account_sid, auth_token)
                try:
                    message = client.messages.create(body=content, messaging_service_sid=messaging_service_sid, to=to_number)
                    TwilioMessage.objects.create(content=content, company_instance=user.company_instance, user_to=new_driver, toNumber=to_number)
                except:
                    pass
        else:
            new_driver = new_owner
            new_driver.phone_number = owner_phone
            new_driver.emergency_phone = driver['emergencyContactPhone']
            new_driver.emergency_name = driver['emergencyContactName']
            new_driver.save(update_fields=['phone_number', 'emergency_phone', 'emergency_name', 'emergency_phone'])

            if not hasattr(new_owner, 'driver_info') or new_owner.driver_info == None:
                driver_info = DriverInfo.objects.create(owner=new_owner.owner_info, user=new_driver, location=str_coords, unique_sms_key=random.randint(1000, 9999))
                account_sid = user.company_instance.twilio_account_sid
                auth_token = user.company_instance.twilio_auth_token
                messaging_service_sid = user.company_instance.twilio_messaging_service_sid
                content = "Congrats! You've been approved as a driver partner for " + user.company_instance.name + "! \nTo start getting loads, download our app 'ALTEK Drivers' for Android: https://play.google.com/store/apps/details?id=au.com.altekdrivers \nFor iOS: https://apps.apple.com/app/id1549665236"
                to_number = driver_phone
                client = Client(account_sid, auth_token)
                try:
                    message = client.messages.create(body=content, messaging_service_sid=messaging_service_sid, to=to_number)
                    TwilioMessage.objects.create(content=content, company_instance=user.company_instance, user_to=new_driver, toNumber=to_number)
                except:
                    pass

        new_drivers.append(new_driver.id)

        car_sizes = post['size'].split('x')

        if Car.objects.filter(vin=post['vin'], active_driver=new_driver.id).exists():
            new_car = Car.objects.get(vin=post['vin'], active_driver=new_driver.id)
            new_car.drivers.add(new_driver.driver_info)

            new_car.payload = int(post['payload'] if post['payload'] != '' else 0)
            new_car.width = float(car_sizes[1] or 0)
            new_car.height = float(car_sizes[2] or 0)
            new_car.length = float(car_sizes[0] or 0)
            new_car.licensePlate = post['licensePlate']
            new_car.licenseState = post['licenseState']
            new_car.licenseExpiryDate = reformatting_date_for_hr(post['licenseExpiryDate'])
            new_car.insuranceExpiry = reformatting_date_for_hr(post['insuranceExpires'])
            new_car.weight = int(post['payload'] if post['payload'] != '' else 0)
            new_car.carModel = post['make']
            new_car.type = post['model']
            new_car.carYear = int(post['year'])
            # new_car.location = str_coords
            new_car.two_drivers = post['two_drivers']
            
            new_car.save(update_fields=['payload', 'width', 'height', 'length', 'licensePlate', 'licenseState', 'licenseExpiryDate', 'insuranceExpiry', 'weight', 'carModel', 'type', 'carYear', 'location', 'two_drivers'])
        else:
            active_driver = DriverInfo.objects.get(pk=int(new_drivers[0]))

            car_data = {
                'payload': int(post['payload'] if post['payload'] != '' else 0),
                'width': float(car_sizes[1] or 0),
                'height': float(car_sizes[2] or 0),
                'length': float(car_sizes[0] or 0),
                'vin': post['vin'], 
                'licensePlate': post['licensePlate'],
                'licenseState': post['licenseState'],
                'licenseExpiryDate': reformatting_date_for_hr(post['licenseExpiryDate']),
                'insuranceExpiry': reformatting_date_for_hr(post['insuranceExpires']),
                'weight': int(post['payload'] if post['payload'] != '' else 0),
                'carModel': post['make'],
                'type': post['model'],
                'carYear': int(post['year']),
                'two_drivers': post['two_drivers'],
                'location': str_coords,
                'car_owner': new_owner.id,
                'drivers': new_drivers,
                'active_driver': active_driver 
            }
        
            car_serializer = CarCreateSerializer(data=car_data, context={'request': request})
            car_serializer.is_valid(raise_exception=True)
            new_car = car_serializer.save(company_instance=user.company_instance)


        return Response({
            'owner': new_owner.id,
            'car': new_car.id,
            'driver': new_driver.id
        })

    def reject_drivers(self, request):
        post = request.data
        car = None
        users = None

        if 'driver' in post and 'owner' in post and post['driver'] != post['owner']:
            users = User.objects.filter(Q(email=post['driver']) | Q(email=post['owner']))
            car = Car.objects.filter(Q(drivers__user__email=post['driver']) | Q(drivers__user__email=post['owner']), vin=post['car'])
        elif 'driver' in post and 'owner' in post and post['driver'] == post['owner']:
            users = User.objects.filter(email=post['owner'])
            car = Car.objects.filter(drivers__user__email=post['owner'], vin=post['car'])

        car.delete()
        users.delete()

        return Response({
            'result': 'ok'
        })

    def update_car(self, request):
        post = request.data
        car_sizes = post['size'].split('x')
        
        if Car.objects.filter(vin=post['vin']).exists():
            new_car = Car.objects.get(vin=post['vin'])

            new_car.width = float(car_sizes[1] or 0)
            new_car.height = float(car_sizes[2] or 0)
            new_car.length = float(car_sizes[0] or 0)
            
            new_car.save(update_fields=['width', 'height', 'length'])

            return Response({
                'car': new_car.id
            })

        return Response({
            'car': None
        })


class DashboardView(AppAuthClass, viewsets.ViewSet):
    permission_classes = [IsAuthenticated]
    
    @method_decorator(cache_page(60*10))
    @method_decorator(vary_on_cookie)
    def list(self, request):
        user = self.request.user
        get = request.query_params
        response = None

        if user.role.id == 3:
            response = self.get_superuser_dashboard()
        elif user.role.id == 4:
            # response = self.get_carriers_dashboard(user)
            response = self.get_superuser_dashboard()
        elif user.role.id == 5:
            response = self.get_dispatcher_dashboard(user)
        else:
            response = {}
                

        return Response(response) 

    def get_shippers_dashboard(self, queryset):
        all_queryset = queryset
        in_transit_queryset = queryset.exclude(status=1).exclude(status=6)
        delivered_queryset = queryset.filter(status=6)

        before_two_h = datetime.now() - timedelta(hours=2)
        before_eight_h = datetime.now() - timedelta(hours=8)
        before_one_day = datetime.now() - timedelta(hours=24)
        
        all_queryset_uotput = [
            {
                'title': '<2 hrs',
                'count': all_queryset.filter(created_date__gte=before_two_h).count()
            },
            {
                'title': '2-8 hrs',
                'count': all_queryset.filter(created_date__range=(before_eight_h, before_two_h)).count()
            },
            {
                'title': '8-24 hrs',
                'count': all_queryset.filter(created_date__range=(before_one_day, before_eight_h)).count()
            },
            {
                'title': '24+ hrs',
                'count': all_queryset.filter(created_date__lte=before_one_day).count()
            },
        ]

        in_transit_queryset_output = [
            {
                'title': '<2 hrs',
                'count': in_transit_queryset.filter(created_date__gte=before_two_h).count()
            },
            {
                'title': '2-8 hrs',
                'count': in_transit_queryset.filter(created_date__range=(before_eight_h, before_two_h)).count()
            },
            {
                'title': '8-24 hrs',
                'count': in_transit_queryset.filter(created_date__range=(before_one_day, before_eight_h)).count()
            },
            {
                'title': '24+ hrs',
                'count': in_transit_queryset.filter(created_date__lte=before_one_day).count()
            },
        ]

        delivered_queryset_uotput = [
            {
                'title': '<2 hrs',
                'count': delivered_queryset.filter(created_date__gte=before_two_h).count()
            },
            {
                'title': '2-8 hrs',
                'count': delivered_queryset.filter(created_date__range=(before_eight_h, before_two_h)).count()
            },
            {
                'title': '8-24 hrs',
                'count': delivered_queryset.filter(created_date__range=(before_one_day, before_eight_h)).count()
            },
            {
                'title': '24+ hrs',
                'count': delivered_queryset.filter(created_date__lte=before_one_day).count()
            },
        ]

        return [
            {
                'title': 'Posted',
                'values': all_queryset_uotput
            },
            {
                'title': 'In transit',
                'values': in_transit_queryset_output
            },
            {
                'title': 'Delivered',
                'values': delivered_queryset_uotput
            }
        ]

    def get_carriers_dashboard(self, user):
        minute_ago = datetime.now() - timedelta(minutes=1)

        all_dispatchers = User.objects.filter(company_instance=user.company_instance, role=5)
        active_dispatchers = all_dispatchers.filter(last_online__gte=minute_ago)
        my_loads = None

        user_workers = User.objects.filter(company_instance=user.company_instance)
        my_loads = Load.objects.filter(company_instance=user.company_instance, removedDateTime=None,)

        in_progress_loads = my_loads.filter(~Q(start_time=None))

        active_cars = Car.objects.exclude(status=1).filter(car_creator=user)
        passive_cars = Car.objects.filter(car_creator=user, status=1)

        before_one_day = datetime.now() - timedelta(days=1)
        before_two_day = datetime.now() - timedelta(days=2)
        before_three_day = datetime.now() - timedelta(days=3)
        before_seven_day = datetime.now() - timedelta(days=7)

        cars_in_progress = [
            {
                'title': '0-24 hrs',
                'count': active_cars.filter(last_status_change__gte=before_one_day).count()
            },
            {
                'title': '24-48 hrs',
                'count': active_cars.filter(last_status_change__range=(before_two_day, before_one_day)).count()
            },
            {
                'title': '48-72 hrs',
                'count': active_cars.filter(last_status_change__range=(before_three_day, before_two_day)).count()
            },
            {
                'title': '72+ hrs',
                'count': active_cars.filter(last_status_change__lte=before_three_day).count()
            },
        ]

        cars_out_of_service = [
            {
                'title': '0-24 hrs',
                'count': passive_cars.filter(last_status_change__gte=before_one_day).count()
            },
            {
                'title': '24-48 hrs',
                'count': passive_cars.filter(last_status_change__range=(before_two_day, before_one_day)).count()
            },
            {
                'title': '2-7 days',
                'count': passive_cars.filter(last_status_change__range=(before_seven_day, before_two_day)).count()
            },
            {
                'title': '7+ days',
                'count': passive_cars.filter(last_status_change__lte=before_seven_day).count()
            },
        ]

        ended_count = my_loads.filter(status=6).count()

        today = date.today()
        date_filter = dict(created_date__day=today.day, created_date__month=today.month, created_date__year=today.year)
        our_props = Proposition.objects.filter(removedDateTime=None, status="Send").filter(Q(user=user) | Q(user__in=[user for user in user.user_workers.all()]))
        props_today = our_props.filter(**date_filter).count()

        return {
            'my_loads_stats': {
                'bids': props_today,
                'posted_loads': Load.objects.filter(**date_filter).count(),
                'all': my_loads.count(),
                'success': ended_count,
                'damaged': ended_count,
                'late': ended_count,
                'cancelled': ended_count,
                'loads_in_progress': self.load_serialize(in_progress_loads),
            },
            'my_users_stats': {
                'users_online': self.user_serialize_with_props(active_dispatchers),
                'my_workers': self.user_serialize_with_props(all_dispatchers)
            },
            'my_vehicles_stats': {
                'available': Car.objects.filter(car_creator=user, status=1).count(),
                'total': Car.objects.filter(car_creator=user).count(),
                'in_progress': cars_in_progress,
                'out_of_service': cars_out_of_service
            }
        }

    def get_dispatcher_dashboard(self, user):
        minute_ago = datetime.now() - timedelta(minutes=1)
        my_loads = None
        my_loads = Load.objects.filter(Q(resp_shipper_dispatcher=user.id) | Q(resp_carrier_dispatcher=user.id), removedDateTime=None,)

        in_progress_loads = my_loads.filter(~Q(start_time=None))

        active_cars = Car.objects.exclude(status=1).filter(company_instance=user.company_instance)
        passive_cars = Car.objects.filter(company_instance=user.company_instance, status=1)

        before_one_day = datetime.now() - timedelta(days=1)
        before_two_day = datetime.now() - timedelta(days=2)
        before_three_day = datetime.now() - timedelta(days=3)
        before_seven_day = datetime.now() - timedelta(days=7)

        cars_in_progress = [
            {
                'title': '0-24 hrs',
                'count': active_cars.filter(last_status_change__gte=before_one_day).count()
            },
            {
                'title': '24-48 hrs',
                'count': active_cars.filter(last_status_change__range=(before_two_day, before_one_day)).count()
            },
            {
                'title': '48-72 hrs',
                'count': active_cars.filter(last_status_change__range=(before_three_day, before_two_day)).count()
            },
            {
                'title': '72+ hrs',
                'count': active_cars.filter(last_status_change__lte=before_three_day).count()
            },
        ]

        cars_out_of_service = [
            {
                'title': '0-24 hrs',
                'count': passive_cars.filter(last_status_change__gte=before_one_day).count()
            },
            {
                'title': '24-48 hrs',
                'count': passive_cars.filter(last_status_change__range=(before_two_day, before_one_day)).count()
            },
            {
                'title': '2-7 days',
                'count': passive_cars.filter(last_status_change__range=(before_seven_day, before_two_day)).count()
            },
            {
                'title': '7+ days',
                'count': passive_cars.filter(last_status_change__lte=before_seven_day).count()
            },
        ]

        ended_count = my_loads.filter(status=6).count()
        user_props = Proposition.objects.filter(removedDateTime=None, user=user.pk)

        return {
            'my_loads_stats': {
                'all': my_loads.count(),
                'success': ended_count,
                'damaged': ended_count,
                'late': ended_count,
                'cancelled': ended_count,
                'loads_in_progress': self.load_serialize(in_progress_loads),
            },
            'my_vehicles_stats': {
                'available': Car.objects.filter(car_creator=user, status=1).count(),
                'total': Car.objects.filter(car_creator=user).count(),
                'in_progress': cars_in_progress,
                'out_of_service': cars_out_of_service
            },
            'props_stats': {
                'bids': user_props.count(),
                **user_props.aggregate(gross=Sum('price')),
                'profit': 0
            }
        }
    
    def get_superuser_dashboard(self):
        # user = self.request.user
        user = User.objects.get(pk=199)
        get = self.request.query_params
        company_instance = user.company_instance if hasattr(user, 'company_instance') else None
        loads = Load.objects.filter()
        cars_queryset = Car.objects.exclude(active_driver=None)
        driver_bids = LoadInHistory.objects.filter(removedDateTime=None, action="Bid")
        drivers =  DriverInfo.objects.filter()
        users_queryset = User.objects.exclude(id=user.id)

        our_loads = loads.filter(~Q(start_time=None), removedDateTime=None)
        if company_instance != None:
            our_loads = our_loads.filter(company_instance=company_instance)
            cars_queryset = cars_queryset.filter(company_instance=company_instance.pk)
            driver_bids = driver_bids.filter(driver__user__company_instance=company_instance.pk)
            drivers = drivers.filter(user__company_instance=company_instance.pk)
            
            # users_queryset = users_queryset.filter(company_instance=company_instance.pk)

        dispatchers_queryset = users_queryset.filter(role=5)

        week_ago = datetime.now() - timedelta(days=7)
        today = date.today()
        date_filter = {}
        days_count = 1

        if 'from' in get:
            date_filter['created_date__gte'] = get['from']
        if 'to' in get:
            date_filter['created_date__lte'] = get['to']
        if 'from' in get and 'to' in get:
            days_count = datetime.strptime(get['to'], '%Y-%m-%d %H:%M').date() - datetime.strptime(get['from'], '%Y-%m-%d %H:%M').date()
            days_count = days_count.days
        else:
            date_filter = dict(created_date__day=today.day, created_date__month=today.month, created_date__year=today.year)

        gross = our_loads.filter(**date_filter).aggregate(gross=Sum('broker_price'))
        revenue = our_loads.filter(**date_filter).aggregate(revenue=Sum(F('broker_price') - F('driver_price')))

        posted_loads_today = loads.filter(**date_filter).count()
        our_loads_today = our_loads.filter(**date_filter).count()
        our_props = Proposition.objects.filter(status="Send").filter(Q(user=user) | Q(user__in=[user for user in user.user_workers.all()]))
        props_today = our_props.filter(**date_filter).count()

        serializer_context = {
            'posted_loads': loads,
            'actual_loads': our_loads,
            'bids': our_props,
            'date_filter': date_filter
        }

        margin = 0
        if gross['gross'] != None and revenue['revenue'] != None:
            margin = round(revenue['revenue'] / gross['gross'], 2)
            

        if 'brokers' in get:
            brokers_queryset = BrokerCompany.objects.all()
            count = brokers_queryset.count()
            page = 1
            if 'page' in get:
                page = get['page'] or 1
            limit = 50
            if 'limit' in get:
                limit = get['limit'] or 50
            offset = (int(page) - 1)*int(limit)
            to = offset + limit
            brokers_queryset = brokers_queryset[offset:to]
            return {
                'count': count,
                'brokers': BrokersStatsSerializer(brokers_queryset, context={**serializer_context}, many=True).data
            }
        elif 'dispatchers' in get:
            return {
                'count': dispatchers_queryset.count(),
                'dispatchers': DispatchersStatsSerializer(dispatchers_queryset, context={**serializer_context}, many=True).data,
                'users_online': UserSerializer(users_queryset.filter(is_online=True), many=True).data
            }
        elif 'vehicles' in get:
            return {
                'count': cars_queryset.count(),
                'in_service': cars_queryset.filter(status=1).count(),
                'vehicles': CarStatsSerializer(cars_queryset, context={**serializer_context}, many=True).data,
            }
        else:
            bids_by_hour = list()
            gross_by_hour = list()
            margin_by_hour = list()
            for i in range(1, 24):
                date_filter['created_date__hour'] = i
                bids_by_hour.append(our_props.filter(**date_filter).count() / days_count)
                hour_gross = our_loads.filter(**date_filter).aggregate(gross=Sum('broker_price'))['gross'] or 0 / days_count
                hour_revenue = our_loads.filter(**date_filter).aggregate(revenue=Sum(F('broker_price') - F('driver_price')))['revenue'] or 0 / days_count
                gross_by_hour.append(hour_gross)
                if hour_gross > 0 and hour_revenue > 0:
                    margin_by_hour.append(hour_revenue / hour_gross)
                else:
                    margin_by_hour.append(0)
            return {
                'gross': gross['gross'] or 0,
                'gross_by_hour': gross_by_hour,
                'revenue': revenue['revenue'] or 0,
                'margin': margin,
                'margin_by_hour': margin_by_hour,
                'posted_loads': posted_loads_today,
                'loads': our_loads_today,
                'bids': props_today,
                'bids_by_hour': bids_by_hour,  
                'driver_bids': driver_bids.filter(**date_filter).count(),
                'successed_bids': driver_bids.filter(**date_filter).filter(success=True).count(),
                'drivers_registered': drivers.exclude(app_activity_time=None).count(),
                'drivers_online': drivers.filter(in_app=True).count()
            }

    def load_serialize(self, obj):
        return LoadStatisticSerializer(obj, many=True).data

    def user_serialize(self, obj):
        return UserSerializer(obj, many=True).data

    def user_serialize_with_props(self, obj):
        return UserSerializerForCarriersDashboard(obj, many=True).data


class Heartbeat(AppAuthClass, viewsets.ViewSet):
    permission_classes = [IsAuthenticated]

    def beat(self, request):
        user_id = request.user.id
        user = User.objects.get(id=user_id)
        notices = Notice.objects.filter(user_to=user, status="Send")

        timestamp = round(datetime.now().timestamp())

        online_log = user.user_online_log
        if online_log == "":
            json_log = list()
        else:
            json_log = json.loads(online_log)

        json_log.append(timestamp)
        new_log = json.dumps(json_log)

        user.user_online_log = new_log
        user.last_online = datetime.now()
        user.save(update_fields=['user_online_log', 'last_online'])

        chats_msgs = ChatMessage.objects.filter(chat_group__company_instance=user.company_instance, chat_group__removedDateTime=None).exclude(users_read=user)
        if user.role.pk != 4:
            chats_msgs = chats_msgs.filter(chat_group__users=user)

        unread_messages = chats_msgs.count()

        output = {
            'last_online': round(user.last_online.timestamp()),
            'new_notices': NoticeSerializer(notices, many=True).data,
            'unread_sms': TwilioMessage.objects.filter(status="Send", company_instance=user.company_instance).exclude(fromNumber="").count(),
            'unread_messages': unread_messages,
        }
        
        return Response(output)


class GuestAPI(AppAuthClass, viewsets.ViewSet):
    permission_classes = []

    def get_load(self, request, code=None):
        try:
            load = Load.objects.get(pk=code)
            load_data = GuestLoadSerializer(load).data
            return Response({
                'success': True,
                'result': load_data
            })
        except:

            return Response({
                'success': False,
                'result': 'Not found'
            })

    def get_cars_map(self, request):
        get = request.query_params
        company_id = get['company']
        load_id = get['load']

        output = {
                'success': True,
                'result': list()
            }

        if not Сompany.objects.filter(pk=company_id).exists() or not Load.objects.filter(removedDateTime=None, pk=load_id).exists():
            output = {
                'success': False,
                'result': 'Wrong company or load'
            }

        queryset = Car.objects.filter(car_creator=company_id).filter(Q(status=1) | Q(status=4)).filter(~Q(location=None) & ~Q(location=""), load=None).exclude(active_driver=None)
        load = Load.objects.get(id=load_id)

        new_queryset = list()

        for car in queryset:
            if car.active_driver.is_enable == False:
                continue
            load_loc = load.start_location.split(',')
            car_loc = car.location.split(',')
            miles_out = round(distance.distance(car_loc, load_loc).miles / 0.86)
            if miles_out < 300:
                output['result'].append({
                    'id': car.id,
                    'number': car.number,
                    'location': car_loc
                })

        return Response(output)     
        

class GooglePubSub(AppAuthClass, viewsets.ViewSet):
    permission_classes = []

    def mail_callback(self, message):
        message.ack()

    def get(self, request):
        # from google.cloud import pubsub_v1
        import asyncio
        import pickle
        import os.path
        from googleapiclient.discovery import build
        from google_auth_oauthlib.flow import InstalledAppFlow
        from google.auth.transport.requests import Request
        
        asyncio.get_event_loop().run_until_complete(send_update_loads_notice())
        return Response('ok')
        
        PUBSUB_PROJECT_ID = 'altek-mail-1604991451587'
        PUBSUB_TOPIC_ID = 'loads_parsing'

        os.environ['GOOGLE_APPLICATION_CREDENTIALS'] = "app/system_api/access/access.json"
        SCOPES = ['https://mail.google.com/']

        asyncio.get_event_loop().run_until_complete(send_update_loads_notice())

        google_auth_code = None
        get = request.query_params
        
        if 'code' in get:
            google_auth_code = get['code']

        creds = None
        if os.path.exists('token.pickle'):
            with open('token.pickle', 'rb') as token:
                creds = pickle.load(token)
                

        if not creds or not creds.valid:
            if creds and creds.expired and creds.refresh_token:
                creds.refresh(Request())
            else:
                flow = InstalledAppFlow.from_client_secrets_file(
                    os.path.abspath('app/system_api/access/client_secret.json'), SCOPES)
                
                flow.redirect_uri = 'https://altekloads.com/backend/api/google/'
                auth_url, _ = flow.authorization_url(access_type='offline')
                if not google_auth_code:
                    return HttpResponseRedirect(auth_url)
                    
                flow.fetch_token(code=google_auth_code)

                creds = flow.credentials
            with open('token.pickle', 'wb') as token:
                pickle.dump(creds, token) 

        gmail = build('gmail', 'v1', credentials=creds)
 
        request = {
          'labelIds': ['INBOX'],
          'topicName': 'projects/altek-mail-1604991451587/topics/loads_parsing'
        }

        
        if 'renew_watch' in get:
            res = gmail.users().watch(userId='me', body=request).execute()
        

        results = gmail.users().messages().list(userId='me',
            maxResults=5,
            q="is:unread after:{0}".format(time.strftime("%d/%m/%Y"))
            ).execute()
        messages = results.get('messages', [])

        # if len(messages) > 

        output = list()
        load_parser = LoadParser()

        for message in messages:
            mail = gmail.users().messages().get(userId='me', id=message['id']).execute()
      
            payload = mail.get('payload')
            body = parse_msg(mail)

            headers = {}
            for header in payload['headers']:
                headers[header['name']] = header['value']

            load_parser.set_mail(headers=headers, body=body)
            # parse_result = load_parser.parse()
            output.append(message['id'])
            # gmail.users().messages().trash(userId='me', id=message['id']).execute()
            

        return Response({
            'result': output
        })          

    def post(self, request):
        import asyncio, pickle, os.path
        from googleapiclient.discovery import build
        from google_auth_oauthlib.flow import InstalledAppFlow
        from google.auth.transport.requests import Request

        # log = open('log.log', 'a+')
        # log.write('Request came' + '\r\n')

        google_auth_code = None
        get = request.query_params
        os.environ['GOOGLE_APPLICATION_CREDENTIALS'] = "app/system_api/access/access.json"
        SCOPES = ['https://www.googleapis.com/auth/gmail.readonly']

        output = []

        if 'code' in get:
            google_auth_code = get['code']

        creds = None
        if os.path.exists('token.pickle'):
            with open('token.pickle', 'rb') as token:
                creds = pickle.load(token)
                

        if not creds or not creds.valid:
            if creds and creds.expired and creds.refresh_token:
                creds.refresh(Request())
            else:
                flow = InstalledAppFlow.from_client_secrets_file(
                    os.path.abspath('app/system_api/access/client_secret.json'), SCOPES)
                
                flow.redirect_uri = 'https://altekloads.com/backend/api/google/'
                auth_url, _ = flow.authorization_url()
                if not google_auth_code:
                    return HttpResponseRedirect(auth_url)
                    
                flow.fetch_token(code=google_auth_code)

                creds = flow.credentials
            with open('token.pickle', 'wb') as token:
                pickle.dump(creds, token) 

        gmail = build('gmail', 'v1', credentials=creds)
        results = gmail.users().messages().list(
            userId='me',
            maxResults=5,
            q="is:unread after:{0}".format(time.strftime("%d/%m/%Y"))
            ).execute()
        messages = results.get('messages', [])

        load_parser = LoadParser()
        # log.write('Parser activated' + '\r\n')
        final_result = False

        for message in messages:
            mail = gmail.users().messages().get(userId='me', id=message['id']).execute()
            payload = mail.get('payload')
            body = payload['body']['data']
            decoded_body = parse_msg(mail)

            headers = {}
            for header in payload['headers']:
                headers[header['name']] = header['value']

            load_parser.set_mail(headers=headers, body=decoded_body)

            # log.write('Message parsed' + '\r\n')

            parse_result = load_parser.parse()
            output.append(parse_result)
            
            if parse_result:
                final_result = True
                # log.write(message['id'] + '\r\n')
                # gmail.users().messages().trash(userId='me', id=message['id'])
                

        # log.write('\r\n' * 2)
        # log.close()
        if final_result:
            # requests.get('https://green-node.ru/backend/api/loads/get-from-gmail?user_id=2&push=1')
            asyncio.get_event_loop().run_until_complete(send_update_loads_notice())
        # gmail = build('gmail', 'v1', credentials=creds)

        # mail = gmail.users().messages().get(userId='me', id=msg_id).execute()
        # messages = mail.get('payload')

        # body = messages['body']['data'] + '==='
        # try:
        #     decoded_body = decode_base64(body)
        # except:
        #     decoded_body = body

        
        return Response(output, 200)


class GmailAuth(AppAuthClass, viewsets.ViewSet):
    permission_classes = [IsAuthenticated]

    def auth(self, request):
        import pickle
        import os.path
        from googleapiclient.discovery import build
        from google_auth_oauthlib.flow import InstalledAppFlow
        from google.auth.transport.requests import Request

        user = request.user
        get = request.query_params

        os.environ['GOOGLE_APPLICATION_CREDENTIALS'] = "app/system_api/access/access.json"
        SCOPES = ['https://mail.google.com/']
        google_auth_code = None

        output = {
            'success': True,
            'user': user.id
        }
        
        if 'code' in get:
            google_auth_code = get['code']

        id = user.id
        if user.id == 108 or user.id == 199:
            id = 7

        creds = None
        if os.path.exists('tokens/token_' + str(id) + '.pickle'):
            with open('tokens/token_' + str(id) + '.pickle', 'rb') as token:
                creds = pickle.load(token)

        if not creds or not creds.valid:
            if creds and creds.expired and creds.refresh_token:
                creds.refresh(Request())
            else:
                flow = InstalledAppFlow.from_client_secrets_file(
                    os.path.abspath('app/system_api/access/client_secret.json'), SCOPES)
                
                flow.redirect_uri = 'https://altekloads.com/backend/api/gmail/'
                auth_url, _ = flow.authorization_url(access_type='offline', prompt='consent')
                if not google_auth_code:
                    return Response({
                        'redirect': auth_url
                    })
                    
                flow.fetch_token(code=google_auth_code)

                creds = flow.credentials
            with open('tokens/token_' + str(id) + '.pickle', 'wb') as token:
                pickle.dump(creds, token)

        gmail = build('gmail', 'v1', credentials=creds)
        profile = gmail.users().getProfile(userId='me').execute()
        output['profile'] = profile['emailAddress']

        user.working_gmail = profile['emailAddress']
        user.save(update_fields=['working_gmail'])

        return Response(output)

    def logout(self, request):
        user = request.user
        id = user.id
        if user.id == 108 or user.id == 199:
            id = 7
        if os.path.exists('tokens/token_' + str(id) + '.pickle'):
            os.remove('tokens/token_' + str(id) + '.pickle')

            user.working_gmail = None
            user.save(update_fields=['working_gmail'])
            return Response({
                'success': True,
                'user': user.id
            })
        else:
            return Response({
                'success': False,
                'user': user.id,
                'message': 'No such file: tokens/token_' + str(id) + '.pickle'
            })


class CompanyRolesView(AppAuthClass, viewsets.ViewSet):
    permission_classes = [IsAuthenticated]

    def get_roles(self, request):
        user = request.user
        user_company = user.company_instance
        # queryset = UserRole.objects.filter(company_instance=user_company.pk)
        queryset = UserRole.objects.all()
        serialised_queryset = UserRoleSerializer(queryset, many=True)
        return Response(serialised_queryset.data)

    def get_role(self, request, pk=None):
        user = request.user
        user_company = user.company_instance
        queryset = UserRole.objects.get(pk=pk)

        serialised_queryset = UserRoleSerializer(queryset)
        return Response(serialised_queryset.data)

        if queryset.company_instance.pk == user_company.pk:
            serialised_queryset = UserRoleSerializer(queryset)
            return Response(serialised_queryset.data)
        else:
            return Response({
                'status': 'denied'
            })

    def create_role(self, request):
        user = request.user
        user_company = user.company_instance
        post = request.data

        new_role = UserRole.objects.create(
            name=post['name'],
            # company_instance=user_company
        )
        if 'pages' in post:
            pages = list(Page.objects.filter(id__in=post['pages']).values_list('id', flat=True))
            new_role.page_set.add(*pages)
        return Response(UserRoleSerializer(new_role).data)

    def delete_role(self, request, pk=None):
        queryset = UserRole.objects.get(pk=pk)
        queryset.delete()
        return Response({
            'status': 'success'
        })

    def update_role(self, request, pk=None):
        user = request.user
        user_company = user.company_instance
        post = request.data
        queryset = UserRole.objects.get(pk=pk)

        # if queryset.company_instance.pk == user_company.pk:
        if 'name' in post:
            queryset.name = post['name']
            queryset.save()

        if 'pages' in post:
            queryset.page_set.clear()
            pages = list(Page.objects.filter(id__in=post['pages']).values_list('id', flat=True))
            queryset.page_set.add(*pages)

        return Response(UserRoleSerializer(queryset).data)

    def get_pages(self, request):
        return Response(PageSerializer(Page.objects.all(), many=True, context={'request': request}).data)
