from datetime import datetime, timedelta

from django.db.models import Q, F, Avg
from django.utils.decorators import method_decorator
from django.views.decorators.cache import cache_page
from django.views.decorators.vary import vary_on_cookie

import email, re, json, requests, random, operator, base64, urllib.parse, pickle
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart

from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework import generics, viewsets, status

from rest_framework_jwt.authentication import JSONWebTokenAuthentication
from rest_framework.authentication import BasicAuthentication, SessionAuthentication

from twilio.rest import Client
from geopy import distance

from app.models import User
from app.serializers import *
from app.permissions import *
from app.pagination import *
from app.helpers.menu_filter import filtered_menu
from app.helpers.data_filters import *
from app.helpers.get_user_owner import get_user_owner
from app.helpers.send_email_by_smtp import SMTP
from app.helpers.push import send_push

from api import settings


SHIPPERS_PAGES = ('/', '/chat/', '/group-chat/', '/email-chat/', '/add-load/', '/my-loads/', '/notifications/', '/settings/users/', '/settings/', '/settings/system/', '/settings/user-requests/', '/profile/')
SHIPPERS_DISPATCHER_PAGES = ('/', '/chat/', '/group-chat/', '/email-chat/', '/add-load/', '/my-loads/', '/notifications/', '/profile/')
SHIPPERS_HR_PAGES = ('/', '/chat/', '/group-chat/', '/email-chat/', '/notifications/',)

CARRIERS_PAGES = ('/', '/chat/', '/group-chat/', '/email-chat/', '/dispatch/', '/my-loads/', '/notifications/', '/bids/', '/delivery-control/', '/vehicles/', '/vehicles/vehicles/', '/vehicles/drivers/', '/vehicles/owners/', '/settings/users/', '/settings/groups/', '/settings/system/', '/settings/user-requests/', '/profile/', '/sms/')
CARRIERS_DISPATCHER_PAGES = ('/', '/chat/', '/group-chat/', '/email-chat/', '/dispatch/', '/my-loads/', '/bids/', '/delivery-control/', '/notifications/', '/profile/', '/sms/')
CARRIERS_HR_PAGES = ('/', '/chat/', '/group-chat/', '/email-chat/', '/sms/', '/dispatch/', '/vehicles/', '/vehicles/vehicles/', '/vehicles/drivers/', '/vehicles/owners/', '/profile/')

ADMIN_PAGES = '__all__'


async def send_update_sms_notice(company_hash=0, data={}):
    import websockets

    uri = "wss://altekloads.com/ws/company/" + str(company_hash) + "/"
    async with websockets.connect(uri) as ws:
        await ws.send(json.dumps({
            'action': 'update_sms',
            'data': data
        }))


async def send_new_load_auction(company_hash=0, data={}):
    import websockets

    uri = "wss://altekloads.com/ws/company/" + str(company_hash) + "/"
    async with websockets.connect(uri) as ws:
        await ws.send(json.dumps({
            'action': 'new_load_auction',
            'data': data
        }))


async def send_update_loads(data={}):
    import websockets

    uri = "wss://altekloads.com/ws/company/0/" 
    async with websockets.connect(uri) as ws:
        await ws.send(json.dumps({
            'action': 'update_loads',
            'data': data
        }))


def get_user_gmail(user_id):
    creds = None
    id = user_id
    if user_id == 108 or user_id == 199:
        id = 7
        
    if os.path.exists('tokens/token_' + str(id) + '.pickle'):
        with open('tokens/token_' + str(id) + '.pickle', 'rb') as token:
            creds = pickle.load(token)

    if creds:
        from googleapiclient.discovery import build
        from google.auth.transport.requests import Request
        if creds.expired and creds.refresh_token:
            creds.refresh(Request())
            with open('tokens/token_' + str(id) + '.pickle', 'wb') as token:
                pickle.dump(creds, token)

        gmail = build('gmail', 'v1', credentials=creds)
        return gmail
    else:
        return None


def parse_msg(msg):
    if msg.get("payload").get("body").get("data"):
        return base64.urlsafe_b64decode(msg.get("payload").get("body").get("data").encode("ASCII")).decode("utf-8")
    return msg.get("snippet") 


class AppAuthClass():
    authentication_classes = [JSONWebTokenAuthentication, SessionAuthentication, BasicAuthentication]


class UserCreate(AppAuthClass, generics.CreateAPIView):
    authentication_classes = []
    permission_classes = []
    serializer_class = UserCreateSerializer

    def perform_create(self, serializer):        
        serializer.save()
        message = self.request.data['email'] + " had registered"
        UserAction.objects.create(user=User.objects.get(email=self.request.data['email']), content=message)


class DispatcherAdd(AppAuthClass, generics.CreateAPIView):
    permission_classes = [IsAuthenticated]
    serializer_class = DispatcherSerializer

    def perform_create(self, serializer):
        user = self.request.user
        # message = user.email + " had added dispatcher"
        # UserAction.objects.create(user=user, content=message)

        group_unassigned = WorkingGroup.objects.filter(company_instance=user.company_instance, group_name="Unassigned")
        if group_unassigned.count() > 0:
            group_unassigned = group_unassigned.first()
        else:
            group_unassigned = None

        serializer.save(added_by=user, working_group=group_unassigned, role=5, company_instance=user.company_instance)

    
class DriversView(AppAuthClass, generics.ListCreateAPIView):
    permission_classes = [IsAuthenticated]
    # pagination_class = StandartResultsSetPagination

    def get_serializer_class(self):
        if self.request.method == 'GET':
            return DriverSerializer
        else:
            return DriverCreateSerializer

    def get_queryset(self):
        user = self.request.user
        company_instance = user.company_instance
        get = self.request.query_params

        queryset = User.objects.exclude(driver_info=None)

        if user.company_instance != None:
            queryset = queryset.filter(company_instance=company_instance.pk)

        if 'search' in get:
            queryset = queryset.filter(Q(first_name__icontains=get['search']) | Q(last_name__icontains=get['search']) | Q(email__icontains=get['search']) | Q(driver_info__working_car__number__icontains=get['search']))

        if 'only_free' in get:
            queryset = queryset.filter(driver_info__working_car=None)

        if 'with_car' in get:
            queryset = queryset.filter(driver_info__status=1).exclude(driver_info__working_car=None).filter(driver_info__working_car__status=1)
            # .exclude(driver_info__is_enable=False)

        if 'for_working_group' in get:
            queryset = queryset.filter(my_working_group=None).filter(Q(working_group=None) | Q(working_group__group_name="Unassigned"))

        if 'wg' in get:
            queryset = queryset.filter(Q(working_group=get['wg']) | Q(working_group__group_name__icontains=get['wg']))

        if 'owner' in get:
            queryset = queryset.filter(driver_info__owner=int(get['owner']))


        for driver in queryset:
            unreads = TwilioMessage.objects.filter(fromNumber=driver.phone_number, status="Send", company_instance=user.company_instance)
            unread_count = unreads.count()
            driver.unread_count = unread_count
            if unread_count > 0:
                driver.last_message_id = unreads.last().pk
            else:
                driver.last_message_id = 0

        queryset = sorted(queryset, key=lambda driver: (driver.unread_count, driver.last_message_id), reverse=True)

        return queryset

    def perform_create(self, serializer):
        user = self.request.user
        company_instance = user.company_instance
        phone = None
        normalized_phone = None
        emergency_phone = "None"
        license_expiration_date = None
        new_driver = None
        owner_info = None

        email = self.request.data['email']

        if User.objects.filter(driver_info=None, email=email).exclude(owner_info=None).exists():
            new_driver = User.objects.filter(driver_info=None, email=email).exclude(owner_info=None).first()
            normalized_phone = new_driver.phone_number
            owner_info = new_driver.owner_info
        else:
            if 'license_expiration_date' in self.request.data:
                license_expiration_date = self.request.data['license_expiration_date']
            else:
                license_expiration_date = round(datetime.now().timestamp())

            if 'phone_number' in self.request.data:
                phone = self.request.data['phone_number']
                normalized_phone = phone_filter(phone, '1')

            if 'emergency_phone' in self.request.data:
                emergency_phone = phone_filter(self.request.data['emergency_phone'], '1')

            if user.role.pk == 8:
                new_driver = serializer.save(
                    company_instance=user.company_instance,
                    phone_number=normalized_phone, 
                    emergency_phone=emergency_phone,
                    license_expiration_date=license_expiration_date)
            else:
                new_driver = serializer.save(
                    company_instance=user.company_instance,
                    phone_number=normalized_phone, 
                    emergency_phone=emergency_phone,
                    license_expiration_date=license_expiration_date)

            if 'owner_id' in self.request.data:
                try:
                    user_owner_id = self.request.data['owner_id']
                    owner_info = CarOwner.objects.get(pk=user_owner_id)
                except:
                    pass

        driver_info = DriverInfo.objects.create(user=new_driver, unique_sms_key=random.randint(1000, 9999), owner=owner_info)

        if user.company_instance != None:
            account_sid = user.company_instance.twilio_account_sid
            auth_token = user.company_instance.twilio_auth_token
            messaging_service_sid = user.company_instance.twilio_messaging_service_sid
            content = "Congrats! You've been approved as a driver partner for " + user.company_instance.name + "! \nTo start getting loads, download our app 'ALTEK Drivers' for Android: https://play.google.com/store/apps/details?id=au.com.altekdrivers \nFor iOS: https://apps.apple.com/app/id1549665236"
            to_number = normalized_phone
            client = Client(account_sid, auth_token)
            client.messages.create(body=content, messaging_service_sid=messaging_service_sid, to=to_number)
            TwilioMessage.objects.create(content=content, user_from=user, user_to=new_driver)

        chat = Chat.objects.create(driver=driver_info, company_instance=company_instance)
        chat.users.set(set([new_driver.pk, owner_info.pk if owner_info != None else new_driver.pk]))
        dispatchers = list(User.objects.filter(role=5, company_instance=user.company_instance))
        chat.users.add(*dispatchers)

    # @method_decorator(cache_page(60*60*2))
    # @method_decorator(vary_on_cookie)
    def get(self, request, *args, **kwargs):
        return super().get(request, *args, **kwargs)


class UserList(AppAuthClass, generics.ListAPIView):
    serializer_class = UserListSerializer
    permission_classes = [IsAuthenticated]
 
    def get_queryset(self):
        queryset = User.objects.filter()
        get = self.request.query_params
        if 'phone_number' in get:
            queryset = queryset.filter(phone_number=get['phone_number'])

        return queryset

    @method_decorator(cache_page(60*60*2))
    @method_decorator(vary_on_cookie)
    def get(self, request, *args, **kwargs):
        return super().get(request, *args, **kwargs)


class MyUserList(AppAuthClass, generics.ListAPIView):
    serializer_class = UserListSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        user = self.request.user
        company_instance = user.company_instance
        get = self.request.query_params
        users = User.objects.filter()
        
        if company_instance != None:
            users = users.filter(company_instance=company_instance.pk)

        if 'for_working_group' in get:
            return users.filter(Q(working_group=None) | Q(working_group__group_name="Unassigned"), role=5)
        if 'all' in get:
            return users
        return users.filter(role=5)

    @method_decorator(cache_page(60*60*2))
    @method_decorator(vary_on_cookie)
    def get(self, request, *args, **kwargs):
        return super().get(request, *args, **kwargs)


class FirmsView(AppAuthClass, generics.ListAPIView):
    serializer_class = UserSettingsSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        user = self.request.user
        return CompanySettings.objects.all()


class CompaniesList(AppAuthClass, generics.ListCreateAPIView):
    permission_classes = [IsAuthenticated]
    serializer_class = CompanySerializer
    queryset = Company.objects.all()

    def perform_create(self, serializer):
        hash_ = random.randint(1000, 99999999)
        serializer.save(company_hash=hash_)

    @method_decorator(cache_page(60*60*20))
    @method_decorator(vary_on_cookie)
    def list(self, request, *args, **kwargs):
        return super().list(request, *args, **kwargs)


class CompanyDetail(AppAuthClass, generics.RetrieveUpdateDestroyAPIView):
    permission_classes = [IsAuthenticated]
    serializer_class = CompanySerializer
    queryset = Company.objects.filter()

    def get_object(self):
        user = self.request.user

        if hasattr(user, 'company_instance') and user.company_instance != None:
            return user.company_instance
        else:
            return super().get_object()

    @method_decorator(cache_page(60*60*2))
    @method_decorator(vary_on_cookie)
    def get(self, request, *args, **kwargs):
        return super().get(request, *args, **kwargs)


class CurrentUserDetail(AppAuthClass, generics.RetrieveUpdateDestroyAPIView):
    queryset = User.objects.all()
    permission_classes = [IsAuthenticated]
    serializer_class = UserSerializer

    def get_object(self):
        return self.request.user
    
    # @method_decorator(cache_page(60*60*10))
    # @method_decorator(vary_on_cookie)
    def get(self, request):
        user = request.user

        if user.role == None:
            return Response(dict(
                    id=0,
                    email=user.email,
                    first_name=user.first_name,
                    last_name=user.last_name,
                    req_status="Send"
                ))

        if user.role.pk == 11:
            try:
                req = RegistrationRequest.objects.get(new_user=user.id, status="Send")
                return Response(dict(
                    id=0,
                    email=user.email,
                    first_name=user.first_name,
                    last_name=user.last_name,
                    req_status="Send"
                ))
            except:
                return Response(dict(
                    id=0,
                    email=user.email,
                    first_name=user.first_name,
                    last_name=user.last_name,
                    req_status="None"
                ))
        else:
            serializer = UserDetailSerializer(request.user)

        return Response(serializer.data)

    def put(self, request, *args, **kwargs):
        return self.partial_update(request, *args, **kwargs)


class RegistrationRequestView(AppAuthClass, viewsets.ViewSet):
    permission_classes = [IsAuthenticated]

    def list(self, request):
        queryset = RegistrationRequest.objects.filter(status="Send")
        if request.user.company_instance != None:
            queryset = queryset.filter(resp_user=request.user)
        else:
            queryset = queryset.filter(company_instance=None)
        serializer = RegistrationRequestSerializer(queryset, many=True)
        return Response(serializer.data)

    def add(self, request, pk=None):
        user = request.user
        post = request.data
        resp_user = None
        company = None

        if post['role'] == 4:
            resp_user = User.objects.get(id=post['resp_user'])
            company = Company.objects.get(id=post['company'])
        else:
            resp_user = None
            company = None
            

        role = UserRole.objects.get(id=post['role'])

        RegistrationRequest.objects.create(new_user=user, resp_user=resp_user, company_instance=company, role=role)
        return Response(dict(
            status="ok"
        ))

    def result(self, request, pk=None):
        post = request.data
        queryset = RegistrationRequest.objects.get(pk=post['id'])

        del request.data['id']
        # del post['id']

        if post['status'] == 'Accept':
            queryset.status = 'Accept'
            new_user = queryset.new_user
            new_user.role = queryset.role
            company = queryset.company_instance

            

            if queryset.role.pk == 4:
                company_hash = hash(str(new_user.pk) + '__salt')
                if int(company_hash) < 0:
                    company_hash = company_hash * -1
                company = Company.objects.create(company_hash=company_hash)
                new_user.company_instance = company
                WorkingGroup.objects.create(group_name="Unassigned", color="#eeeeee", company_instance=company)

            new_user.save()
            queryset.save()
        elif post['status'] == 'Decline':
            queryset.delete()
        else:
            queryset.status = post['status']
            queryset.save()
        
        queryset = RegistrationRequest.objects.filter(resp_user=request.user)
        serializer = RegistrationRequestSerializer(queryset, many=True)
        return Response(serializer.data)


class UserDetails(AppAuthClass, generics.RetrieveUpdateDestroyAPIView):
    queryset = User.objects.filter()
    permission_classes = [IsAuthenticated]
    serializer_class = UserDetailSerializer

    def perform_update(self, serializer):
        retr_user = self.get_object()
        retr_user_driver_info = retr_user.driver_info if hasattr(retr_user, 'driver_info') else None
        str_coords = None
        post = self.request.data

        if 'zip_code' in post and retr_user_driver_info != None:
            bing_resp = requests.get("http://dev.virtualearth.net/REST/v1/Locations?query=" + post['zip_code'] + "&key=" + settings.BING_API_KEY)
            json_bing_resp = json.loads(bing_resp.text)
            
            if json_bing_resp['statusCode'] == 200:
                if len(json_bing_resp['resourceSets'][0]['resources']) > 0:
                    coords = json_bing_resp['resourceSets'][0]['resources'][0]['point']['coordinates']
                    location_name = json_bing_resp['resourceSets'][0]['resources'][0]['name']
                    str_coords = str(coords[0]) + ',' + str(coords[1])

                    retr_user.driver_info.location = str_coords
                    retr_user.driver_info.save(update_fields=['location'])
                    if location_name != None:
                        Car.objects.filter(active_driver=retr_user.driver_info).update(location=str_coords, availableCity=location_name)
                    else:
                        Car.objects.filter(active_driver=retr_user.driver_info).update(location=str_coords)
                               
        serializer.save()

    def put(self, request, *args, **kwargs):
        return self.partial_update(request, *args, **kwargs)


class UserOnlineHistory(AppAuthClass, generics.RetrieveAPIView):
    permission_classes = [IsAuthenticated]
    serializer_class = UserOnlineSerializer
    queryset = User.objects.filter()

    def retrieve(self, request, *args, **kwargs):
        req_object = self.get_object()
        # req_object = request.user
        online_log = None

        if req_object.user_online_log == "":
            online_log = list()
        else:
            online_log = json.loads(req_object.user_online_log)

        output_log = list()
        day_ago_stamp = round((datetime.now() - timedelta(hours=24)).timestamp())

        for timestamp in online_log:
            if timestamp > day_ago_stamp:
                output_log.append(timestamp) 
        
        return Response(output_log)


class LoadHistoryList(AppAuthClass, generics.ListAPIView):
    permission_classes = [IsAuthenticated]
    serializer_class = LoadInHistorySerializer

    def get_queryset(self):
        user = self.request.user
        company_instance = user.company_instance
        queryset = LoadInHistory.objects.filter(removedDateTime=None, action="Complete", driver__user__company_instance=company_instance.pk).order_by('-created_date')
        return queryset


class LoadCreate(AppAuthClass, generics.CreateAPIView): 
    permission_classes = []
    serializer_class = LoadSerializer

    def perform_create(self, serializer):
        import asyncio

        user = self.request.user

        new_load = serializer.save(shipper=user, reply_email=user.email)
        new_load.sys_ref = '#' + str(new_load.id)
        new_load.save(update_fields=['sys_ref'])
        
        LoadPoint.objects.create(
            load=new_load,
            type="Pick-up point",
            datetime=new_load.pick_up_date,
            full_name=new_load.pickUpAt, 
            city=new_load.pickUpAt_city, 
            zip_code=new_load.pickUpAt_zip, 
            location=new_load.start_location
        )

        LoadPoint.objects.create(
            load=new_load,
            type="Delivery point",
            datetime=new_load.delivery_date,
            full_name=new_load.deliverTo, 
            city=new_load.deliverTo_city, 
            zip_code=new_load.deliverTo_zip, 
            location=new_load.end_location
        )

        Cargo.objects.create(
            load=new_load,
            total_weight=new_load.weight,
            width=new_load.width,
            height=new_load.height,
            length=new_load.length,
        )

        cars = Car.objects.filter(Q(status=1) | Q(status=4), company_instance=user.company_instance, load=None).exclude(Q(location=None) | Q(location="")).exclude(active_driver=None).select_related('active_driver')

        drivers = []
        load_loc = new_load.start_location.split(',')
                    
        for car in cars:
            car_loc = car.location.split(',')
            miles_out = round(distance.distance(car_loc, load_loc).miles / 0.86)
            if miles_out < 200:
                drivers.append(car.active_driver.pk)

        data = {
            'load_id': new_load.id,
            'drivers': drivers
        }
        company_hash = user.company_instance.company_hash
        asyncio.get_event_loop().run_until_complete(send_new_load_auction(company_hash, data))
        # Documents.objects.create(load=new_load)


class PubSubLoadCreate(AppAuthClass, viewsets.ViewSet):
    permission_classes = []
    serializer_class = LoadSerializer

    def post(self, request):
        result = False
        loads = list()
        post = request.data
        shipper = User.objects.get(pk=7)
        sys_refs = list()

        for load_data in post['loads']:
            if Load.objects.filter(removedDateTime=None, pickUpAt=load_data['pickUpAt'], deliverTo=load_data['deliverTo'], broker_company=load_data['broker_company'], start_time=None, status=1).exists():
                continue

            serializer = SmallLoadSerializer(data=load_data)
            if serializer.is_valid(raise_exception=True):

                if load_data['sys_ref'] in sys_refs:
                    continue
                else:
                    sys_refs.append(load_data['sys_ref'])

                try:
                    new_load = serializer.save(shipper=shipper)
                    result = True
                except:
                    continue


                if new_load == None:
                    continue
                

                separated_pickup = separate_location(new_load.pickUpAt)
                separated_deliverto = separate_location(new_load.deliverTo)

                LoadPoint.objects.create(
                    load=new_load,
                    type="Pick-up point",
                    datetime=new_load.pick_up_date,
                    full_name=new_load.pickUpAt, 
                    city=separated_pickup['city'],
                    state=separated_pickup['state'],
                    zip_code=separated_pickup['zip'], 
                    location=new_load.start_location
                )

                LoadPoint.objects.create(
                    load=new_load,
                    type="Delivery point",
                    datetime=new_load.delivery_date,
                    full_name=new_load.deliverTo, 
                    city=separated_deliverto['city'],
                    state=separated_deliverto['state'],
                    zip_code=separated_deliverto['zip'], 
                    location=new_load.end_location
                )

                Cargo.objects.create(
                    load=new_load,
                    total_weight=new_load.weight,
                    width=new_load.width,
                    height=new_load.height,
                    length=new_load.length,
                )


                broker_company, _ = BrokerCompany.objects.get_or_create(name=new_load.company)
                broker, _ = Broker.objects.get_or_create(phone_number=phone_filter(new_load.broker_phone, '1'))
                broker.name = new_load.broker_name
                broker.company = broker_company
                broker.save()
                
                loads.append({
                    'id': new_load.id,
                    'pickUpAt': new_load.pickUpAt,
                    'deliverTo': new_load.deliverTo,
                    'pick_up_date': new_load.pick_up_date,
                    'delivery_date': new_load.delivery_date,
                    'price': new_load.price,
                    'miles': new_load.miles,
                    'weight': new_load.weight,
                    'pieces': new_load.pieces,
                    'start_location': new_load.start_location,
                    'end_location': new_load.end_location,
                    'created_date' : new_load.created_date,
                    'pickUpAt_zip' : new_load.pickUpAt_zip,
                    'deliverTo_zip' : new_load.deliverTo_zip,
                    'note' : new_load.note,
                    'isUrgent' : new_load.isUrgent,
                    'dims' : new_load.dims,
                    'car' : new_load.car,
                    'isDanger' : new_load.isDanger,
                    'isCanPutOnTop' : new_load.isCanPutOnTop,
                    'dock_level' : new_load.dock_level
                })
            

        return Response({
            'result': result,
            'data': loads
        })


class LoadList(AppAuthClass, generics.ListAPIView):
    permission_classes = [IsAuthenticated]
    serializer_class = LoadListSerializer
    pagination_class = StandartResultsSetPagination

    def get_queryset(self):
        user = self.request.user

        get = self.request.query_params
        
        queryset = Load.objects.filter(removedDateTime=None, start_time=None, status=1).exclude(start_location=None).order_by('-created_date')

        if hasattr(user, 'driver_info') and user.driver_info != None:
            working_car = user.driver_info.working_car
            if working_car != None:
                queryset = queryset.filter(width__lte=working_car.width, height__lte=working_car.height, length__lte=working_car.length)

        if hasattr(user, 'company_instance') and user.company_instance != None:
            company_info = user.company_instance
            brokers_blacklist = company_info.brokers_blacklist
            brokers_blacklist_array = brokers_blacklist.split('|')
            companies_blacklist = company_info.companies_blacklist
            companies_blacklist_array = companies_blacklist.split('%%')
            queryset = queryset.exclude(company__in=[company for company in companies_blacklist_array]).exclude(reply_email__in=[broker for broker in brokers_blacklist_array])
        
        if 'filter_type' in get:
            if get['filter_type'] == 'single':
                if 'filter_field' in get:
                    field = get['filter_field']
                    condition = get['condition']
                    value = get['value']

                    if value == 'false':
                        value = False
                    if value == 'true':
                        value = True

                    if condition == 'equal' or condition == 'more' or condition == 'less' or condition == 'contains':
                        if condition == 'more':
                            field = field + '__gte'
                        elif condition == 'less':
                            field = field + '__lte'
                        elif condition == 'contains':
                            field = field + '__icontains'

                        kwargs = {field: value}
                        queryset = queryset.filter(**kwargs)

                    elif condition == 'not_equal':
                        kwargs = {field: value}
                        queryset = queryset.filter(~Q(**kwargs))
            elif get['filter_type'] == 'multipart':
                filter_kwargs = {}
                filter_args = []
                exclude_kwargs = {}
                exclude_args = []
                for param in get:
                    splitted_param = param.split('__')
                    field = splitted_param[0]
                    # Так как с not выдает ошибку фильтрации
                    value_param = param
                    prefix = splitted_param[-1] if len(splitted_param) > 1 else None
                    modifier = 'filter'
                    if prefix == 'not':
                        modifier = 'exclude'
                        value_param = '__'.join(splitted_param[:-1])
                        prefix = splitted_param[-2]
                    value = get[param]

                    if value == 'false':
                        value = False
                    if value == 'true':
                        value = True
                    # Пока отменим фильтрацию по доскам. Никто не знает, как это должно работать)
                    if field == 'brokerage':
                        continue

                    if hasattr(Load, field):
                        if prefix == 'or':
                            # Фильтр типа ИЛИ
                            or_values = get[param].split(',')
                            field__prefix = field + '__icontains'
                            q_objects = Q()
                            for or_value in or_values:
                                filter_value = {
                                    field__prefix: or_value
                                }
                                q_objects |= Q(**filter_value)
                            if modifier == 'filter':
                                filter_args.append(q_objects)
                            elif modifier == 'exclude':
                                exclude_args.append(q_objects)
                            
                        else:
                            if modifier == 'filter':
                                filter_kwargs[value_param] = value
                            elif modifier == 'exclude':
                                exclude_kwargs[value_param] = value
                            
                queryset = queryset.filter(*filter_args, **filter_kwargs).exclude(*exclude_args, **exclude_kwargs)
        
        return queryset

    # @method_decorator(cache_page(10))
    # @method_decorator(vary_on_cookie)
    def list(self, request, *args, **kwargs):
        queryset = self.filter_queryset(self.get_queryset())
        get = request.query_params
        user = request.user
        company_instance = user.company_instance
        
        working_group_ids = None
        standart_radius = 200

        if 'radius' in get:
            standart_radius = get['radius']

        if hasattr(user, 'driver_info') and user.driver_info == None:
            before_15_min = datetime.now() - timedelta(minutes=15)
            queryset = queryset.filter(created_date__gte=before_15_min)

        page = self.paginate_queryset(queryset)
        new_queryset = list()

        if page is not None:
            queryset = page

        filter_by_distance = False
        if 'geo' in get and 'miles_range' in get:
            filter_by_distance = True
            geo = user.driver_info.location 
            
        cars_array = []

        if 'wg' in get:
            working_group_set = WorkingGroup.objects.filter(company_instance=user.company_instance)
            q_objects = Q()
            groups_name = get['wg'].split(',')
            for group_name in groups_name:
                filter_value = {
                    'group_name__icontains': group_name
                }
                q_objects |= Q(**filter_value)
            working_group_set = working_group_set.filter(q_objects)
            if working_group_set.exists():
                working_group_ids = working_group_set.values_list('pk', flat=True)

        # Если пользователь - водитель, то не тратим время на обработку машин для груза
        if not hasattr(user, 'driver_info') or hasattr(user, 'driver_info') and user.driver_info == None:
            cars_array = Car.objects.filter(~Q(location=None) & ~Q(location=""), company_instance=user.company_instance, load=None)
            cars_array = cars_array.exclude(status=2).exclude(active_driver=None)
            # .exclude(active_driver__is_enable=False)
            if working_group_ids != None:
                cars_array = cars_array.filter(active_driver__user__working_group__in=working_group_ids)

            cars_array = cars_array.values('id', 'location', 'status', 'active_driver')
            bided_loads = Load.objects.filter(removedDateTime=None, status=1, saved_in_history__isnull=False, bided=True).distinct()
            for load in bided_loads:
                bids_count = LoadInHistory.objects.filter(removedDateTime=None, load=load.id, driver__user__company_instance=company_instance, action="Bid").count()
                if bids_count > 0:
                    if Proposition.objects.filter(removedDateTime=None, load=load.id, status="Send").exists():
                        continue
                    load.bids_count = bids_count
                    actual_cars_count = 0
                    holded_cars_count = 0
                    min_miles_out = None
                    load_loc = load.start_location.split(',')

                    for car in cars_array:
                        miles_out = round(distance.distance(car['location'].split(','), load_loc).miles / 0.86)
                        if miles_out < 200:
                            if car['status'] != 1:
                                holded_cars_count += 1
                            else:
                                actual_cars_count += 1
                                if min_miles_out == None or miles_out < min_miles_out:
                                    min_miles_out = miles_out

                    load.actual_cars_count = actual_cars_count
                    load.holded_cars_count = holded_cars_count
                    load.miles_out = min_miles_out

                    new_queryset.append(load)


        for load in queryset:
            actual_cars_count = 0
            holded_cars_count = 0
            min_miles_out = None
            load_loc = load.start_location.split(',')

            if filter_by_distance:
                filter_miles = int(get['miles_range'])
                current_geo = geo.split(',')
                load_geo = load_loc
                min_miles_out = round(distance.distance(current_geo, load_geo).miles)

                if min_miles_out > filter_miles or min_miles_out == 0:
                    continue
            
            for car in cars_array:
                miles_out = round(distance.distance(car['location'].split(','), load_loc).miles / 0.86)
                if miles_out < 200:
                    if car['status'] != 1:
                        holded_cars_count += 1
                    else:
                        actual_cars_count += 1
                        if min_miles_out == None or miles_out < min_miles_out:
                            min_miles_out = miles_out
                            
            if working_group_ids != None:
                continue

            load.bids_count = 0
            load.actual_cars_count = actual_cars_count
            load.holded_cars_count = holded_cars_count
            load.miles_out = min_miles_out

            already_saw = load.users_saw
            if already_saw == '':
                already_saw = list()
            else:
                already_saw = json.loads(already_saw)

            load.already_saw = user.id in already_saw
            new_queryset.append(load)
        
        queryset = set(new_queryset)
        if 'order_by' in get:
            order_by = get['order_by']
            reverse = True
            if order_by != '':
                if get['order'] == 'DESC':
                    reverse = False
                queryset = sorted(queryset, key=lambda load: (load.bids_count, getattr(load, order_by), load.id), reverse=reverse)
        else:
            queryset = sorted(queryset, key=lambda load: (load.bids_count, load.id), reverse=True)
            
        serializer = self.get_serializer(queryset, many=True)
        if page is not None:
            return self.get_paginated_response(serializer.data)
        return Response(serializer.data)


class OurLoadList(AppAuthClass, generics.ListAPIView):
    permission_classes = [IsAuthenticated]
    serializer_class = LoadListSerializer
    # pagination_class = StandartResultsSetPagination

    def get_queryset(self):
        user = self.request.user
        
        get = self.request.query_params     
        company_instance = user.company_instance
        # loads = Load.objects.all()[0:5]
        user_workers = User.objects.filter(company_instance=company_instance.pk)
        loads = Load.objects.filter(company_instance=company_instance.pk)

        if 'status' in get:
            loads = loads.filter(status=int(get['status']))
        if 'status_not' in get:
            loads = loads.exclude(status=int(get['status_not']))
        
        return loads


class LoadDetail(AppAuthClass, generics.RetrieveUpdateDestroyAPIView):
    queryset = Load.objects.filter(removedDateTime=None, )
    permission_classes = [IsAuthenticated]
    serializer_class = LoadSerializer

    def put(self, request, *args, **kwargs):
        load = self.get_object()
        post = request.data
        user = request.user

        if 'status' in post:
            status_info = load.status_info
            if status_info == "":
                json_log = dict()
            else:
                json_log = json.loads(status_info)
            
            timestamp = round(datetime.now().timestamp())
            status = post['status']

            json_log[status] = timestamp
            
            new_log = json.dumps(json_log)

            load.status_info = new_log
            load.save(update_fields=['status_info'])

            if status == 6:
                resp_car = load.resp_car
                self.partial_update(request, *args, **kwargs)

                resp_car.status = 1
                resp_car.last_status_change = datetime.now()
                resp_car.save(update_fields=['status', 'last_status_change'])

                LoadInHistory.objects.create(load=load, action="Complete", driver_price=load.driver_price, driver=load.resp_driver)
                output = self.queryset.update(resp_car=None, last_car=resp_car.number, resp_driver=None)

                resp_car.status = CarStatus.objects.get(pk=1)
                resp_car.save(update_fields=['status'])
                
                return output
                
            else:
                try:
                    load.resp_driver.status = DriverStatus.objects.get(id=1)
                    load.resp_driver.save(update_fields=['status'])
                except:
                    pass
        elif 'substatus' in post:
            pass
        
        if 'resp_driver' in post:
            old_car = load.resp_car
            old_driver = load.resp_driver.user
            new_driver = User.objects.get(id=post['resp_driver'])
            new_car = Car.objects.get(active_driver=new_driver.driver_info)
            load_chat = None

            if Chat.objects.filter(load=load.id, company_instance=user.company_instance, users=old_driver.pk).exists():
                load_chat = Chat.objects.filter(load=load.id, company_instance=user.company_instance.pk, users=old_driver.pk).first()
                load_chat.users.remove(old_driver)
                load_chat.users.add(new_driver)

            old_car.status = CarStatus.objects.get(id=1)
            old_car.save(update_fields=['status'])

            new_car.status = CarStatus.objects.get(id=3)
            new_car.save(update_fields=['status'])

        output = self.partial_update(request, *args, **kwargs)
        return output

    def retrieve(self, request, *args, **kwargs):
        load = self.get_object()
        serializer = self.get_serializer(load)

        user = request.user
        
        user_id = user.id

        if not hasattr(user, 'driver_info') or user.driver_info == None:
            already_saw = load.users_saw
            if already_saw == '':
                already_saw = list()
            else:
                already_saw = json.loads(already_saw)
            if user_id not in already_saw:
                already_saw.append(user_id)
                load.users_saw = json.dumps(already_saw)
                load.save(update_fields=['users_saw'])

        car_coords = None
        resp_car = load.resp_car
        approximate_time = 0

        if resp_car != None:
            car_coords = resp_car.location

            bing_resp = requests.get("http://dev.virtualearth.net/REST/v1/Routes?wp.1=" + car_coords + "&wp.2=" + load.end_location + "&key=" + settings.BING_API_KEY + "&distanceUnit=mi")
            json_bing_resp = json.loads(bing_resp.text)
            approximate_time = None
            
            if json_bing_resp['statusCode'] == 200:
                if len(json_bing_resp['resourceSets'][0]['resources']) > 0:
                    approximate_time = json_bing_resp['resourceSets'][0]['resources'][0]['travelDuration']

        saved_loads = SavedLoad.objects.filter(state_from__icontains=load.pickUpAt_state, state_to__icontains=load.deliverTo_state)
        count = saved_loads.count()
        recomended_data = {
                'count': count,
                'driver_cost_per_mile': 0.0,
                'broker_cors_per_mile': 0.0,
                'percent': 0
            }
        if count > 0:
            percent = saved_loads.aggregate(percent=Avg('percents'))
            try:
                driver_cost_per_mile = saved_loads.aggregate(driver_cost_per_mile=Avg(F('driver_cost') / F('miles')))
            except:
                driver_cost_per_mile = {'driver_cost_per_mile': 0.0}
            broker_cors_per_mile = driver_cost_per_mile['driver_cost_per_mile'] + driver_cost_per_mile['driver_cost_per_mile'] * percent['percent']
            recomended_data = {
                'count': count,
                'driver_cost_per_mile': round(driver_cost_per_mile['driver_cost_per_mile'], 2),
                'broker_cors_per_mile': round(broker_cors_per_mile, 2),
                'percent': round(percent['percent'], 2)
            }

        last_email = ''
        gmail = get_user_gmail(user.id)
        if gmail != None:
            results = gmail.users().messages().list(
                userId='me',
                maxResults=1,
                q=load.mail_subject[:50] + " from:" + load.reply_email
                ).execute()
            messages = results.get('messages', [])
            for message in messages:
                mail = gmail.users().messages().get(userId='me', id=message['id']).execute()
                last_email = parse_msg(mail)


        output = {
            'load_data': serializer.data,
            'last_email': last_email,
            'bid_data': SmallPropositionSerializer(Proposition.objects.filter(removedDateTime=None, load=load.pk, status="Accept").last()).data,
            'recomended_data': recomended_data,
            'location_data': {
                'load_start_coords': load.start_location,
                'load_end_coords': load.end_location,
                'car_coords': car_coords,
                'approximate_time': approximate_time
            }
        }

        return Response(output) 


class LoadUpdateView(AppAuthClass, viewsets.ViewSet):
    permission_classes = [IsAuthenticated]

    def update_load(self, request, pk):
        load = Load.objects.select_related('points', 'cargos').get(pk=pk)
        post = dict(request.data)

        points_data = post.pop('points')
        load_points = list(load.points)
       

        points_len_diff = len(points_data) - len(load_points)
        if points_len_diff > 0:
            new_points = points_data[points_len_diff:]
            for new_point in new_points:
                LoadPoint.objects.create(load=load, **new_point)
        elif points_len_diff < 0:
            excess_points = load_points[points_len_diff:]
            for excess_point in excess_points:
                excess_point.delete()
        
        for index, load_point in enumerate(load_points):
            curr_point_data = points_data[index]
            for point_field in curr_point_data:
                setattr(load_point, point_field, curr_point_data[point_field])
            load_point.save()

        try:
            cargo_data = post.pop('cargo')[0]
            load_cargo = list(load.cargos)[0]
            
            updated_fields = list()
            for cargo_field in cargo_data:
                setattr(load_cargo, cargo_field, cargo_data[cargo_field])
                updated_fields.append(cargo_field)
            load_cargo.save(update_fields=updated_fields)
        except:
            pass

        updated_fields = list()
        for load_field in post:
            setattr(load, load_field, post[load_field])
            updated_fields.append(load_field)

        load = load.save(update_fields=updated_fields)
        resp = LoadSerializer(load).data
        return Response(resp)


class PropositionList(AppAuthClass, generics.ListCreateAPIView):
    permission_classes = [IsAuthenticated]
    serializer_class = PropositionSerializer

    def get_queryset(self):
        user = self.request.user
        
        queryset = Proposition.objects.filter(removedDateTime=None, status="Send")
        
        if user.role.pk == 4:
            queryset = queryset.filter(user__company_instance=user.company_instance)
        elif user.role.pk == 5:
            if hasattr(user, 'my_working_group') and user.my_working_group != None:
                queryset = queryset.filter(Q(user=user) | Q(user__in=[user for user in user.my_working_group.users.all()]))
            else:
                queryset = queryset.filter(user=user)

        return queryset

    def perform_create(self, serializer):
        user = self.request.user
        company = user.company_instance
        post = self.request.data
        load = Load.objects.get(id=post['load'])
        driver = DriverInfo.objects.get(pk=post['driver'])

        # message = user.email + " had added proposition to load"
        # UserAction.objects.create(user=user, content=message)
        gmail = get_user_gmail(user.id)
        # gmail = get_user_gmail(245)

        if user.working_gmail == 'development@etlgroupllc.com' or user.working_gmail == 'Lider@alliancelogistics.org' or user.working_gmail == 'Lider@alliancelogisticsllc.com':
            gmail = None
        

        if gmail != None:
            message = MIMEMultipart("alternative")
            message["Subject"] = 'Re: ' + load.mail_subject
            message["From"] = "'Altek' <" + company.company_mail_adress + ">"
            message["Reply-To"] = user.working_gmail
            message["In-Reply-To"] = load.mail_id
            message["References"] = load.mail_id
            message["To"] = load.reply_email
            # message["To"] = 'lukashov9182@gmail.com'
            message.attach(MIMEText(post['mail'], "html"))

            body = {
                # 'threadId': load.mail_thread,
                'raw': (base64.urlsafe_b64encode(message.as_bytes())).decode("utf-8")
            }
            gmail.users().messages().send(userId='me', body=body).execute()
        

        Car.objects.filter(id=post['car']).update(status=4, bid_time=datetime.now())

        # if gmail == None or user.department != 'Dispatcher':
        #     if company.company_mail_adress != '' and company.company_mail_password != '' and company.company_mail_host != '':
        #         smtp = SMTP(login=company.company_mail_adress,
        #                     password=company.company_mail_password,
        #                     domain=company.company_mail_host,
        #                     port=company.company_mail_port)
        #         smtp.send_mail(company.company_mail_adress, load.reply_email, message.as_string())
        # else:
        #     body = { 'raw': (base64.urlsafe_b64encode(message.as_bytes())).decode("utf-8")  }
        #     gmail.users().messages().send(userId='me', body=body).execute()

        load.bided = True
        load.save(update_fields=['bided'])
        # LoadInHistory.objects.create(load=load, action="Bid", driver_price=post['driver_price'], driver=driver)

        serializer.save(user=user, load=load, driver=driver, miles_out=post['miles_out'])

    
class PropositionDetail(AppAuthClass, generics.RetrieveUpdateDestroyAPIView):
    permission_classes = [IsAuthenticated]
    queryset = Proposition.objects.filter(removedDateTime=None)
    serializer_class = PropositionSerializer

    def perform_update(self, serializer):
        post = self.request.data
        retr_prop = self.get_object()
        user = self.request.user
        

        if 'status' in post:
            if post['status'] == "Accept":
                load_id = retr_prop.load.id
                price = retr_prop.price
                driver_price = retr_prop.driver_price
                broker_price = retr_prop.broker_price
                miles_out = retr_prop.miles_out
                carrier = retr_prop.user
                driver = None
                car = None

                if 'driver' in post:
                    driver = DriverInfo.objects.get(pk=post['driver'])
                else:
                    driver = retr_prop.driver
                
                if 'car' in post:
                    car = Car.objects.get(pk=post['car'])
                else:
                    car = retr_prop.car

                message = user.email + " had accepted proposition"
                # UserAction.objects.create(user=user, content=message)

                # load_in_history = LoadInHistory.objects.get(load=retr_prop.load.id, driver=driver)


                # if car.active_driver != None:
                #     load_in_history = LoadInHistory.objects.get_or_create(load=retr_prop.load, driver=car.active_driver.driver_info, driver_price=driver_price)
                    # load_in_history = car.active_driver.driver_info.saved_loads_set.get_or_create(load=load, driver_price=driver_price)
                # else:
                #     load_in_history = LoadInHistory.objects.get_or_create(load=retr_prop.load, driver=car.drivers.all()[0].driver_info, driver_price=driver_price)
                    # load_in_history = car.drivers.all()[0].driver_info.saved_loads_set.get_or_create(load=load, driver_price=driver_price)
                
                # load_in_history.action = "In work"
                # load_in_history.save(update_fields=['action'])


                car.status = CarStatus.objects.get(id=3)
                # car.car_propositions.set([retr_prop])
                Proposition.objects.filter(car=car).exclude(id=retr_prop.id).update(removedDateTime=datetime.now())

                car.save(update_fields=['status'])

                LoadInHistory.objects.filter(load=load_id, driver=driver.pk, action="Bid").update(success=True)
                
                Proposition.objects.filter(Q(load=load_id) | Q(car=car), removedDateTime=None).update(status="Decline")
                load = Load.objects.filter(removedDateTime=None, id=load_id)
                load.update(
                    bided=False,
                    start_time=datetime.now(),
                    price=price,
                    miles_out=miles_out,
                    broker_price=broker_price,
                    driver_price=driver_price,
                    resp_car=car,
                    resp_driver=driver,
                    resp_carrier_dispatcher=retr_prop.user,
                    company_instance=user.company_instance
                )
                load = load[0]

                serializer.save(agree=True)

                users = list()
                # users.append(load.resp_shipper_dispatcher)
                # try:
                users.append(load.resp_carrier_dispatcher.pk)
                if load.resp_driver.user != None:
                    users.append(load.resp_driver.user.pk)
                users.append(load.resp_driver.user)
                if load.resp_driver.owner != None:
                    users.append(load.resp_driver.owner.pk)
                resp_dispatcher_group = load.resp_carrier_dispatcher.working_group

                if resp_dispatcher_group != None:
                    if hasattr(resp_dispatcher_group, 'group_lead') and resp_dispatcher_group.group_lead != None:
                        users.append(resp_dispatcher_group.group_lead.pk)
                
                chat = Chat.objects.create(load=load, company_instance=user.company_instance)
                chat.users.set(users)
                # except:
                #     pass
            elif post['status'] == "Decline":
                car = retr_prop.car
                load = retr_prop.load

                car.status = CarStatus.objects.get(id=1)
                car.save(update_fields=['status'])

                load.bided = True
                load.save(update_fields=['bided'])

                serializer.save(agree=False, status="Decline")
            else:
                serializer.save()
        else:
            serializer.save()

    def put(self, request, *args, **kwargs):
        return self.partial_update(request, *args, **kwargs)


class NoticeList(AppAuthClass, generics.ListCreateAPIView):
    permission_classes = [IsAuthenticated]
    queryset = Notice.objects.all()
    serializer_class = NoticeSerializer

    def get_queryset(self):
        user = self.request.user
        return Notice.objects.filter(user_to=user).order_by('-status', '-created_date')[:25]

    def perform_create(self, serializer):
        post = self.request
        user_to = User.objects.filter(phone_number=post['phone_number'])[0]
        content = post['content']
        serializer.save(user_to=user_to, content=content)


class NoticeUpdate(AppAuthClass, viewsets.ViewSet):
    permission_classes = [IsAuthenticated]

    def mark_as_read(self, request):
        user = request.user
        Notice.objects.filter(user_to=user).update(status="Read")
        notices = Notice.objects.filter(user_to=user).order_by('-created_date')[:25]
        serializer = NoticeSerializer(notices)
        return Response(serializer.data)

    def mark_as_read_entity(self, request):
        user = request.user
        post = request.data
        Notice.objects.filter(user_to=user, entity_id=post['id'], entity_type=post['type']).update(status='Read')
        return Response({})


class NoticeDetail(AppAuthClass, generics.RetrieveUpdateDestroyAPIView):
    queryset = Notice.objects.filter()
    permission_classes = [IsAuthenticated]
    serializer_class = NoticeSerializer

    def put(self, request, *args, **kwargs):
        return self.partial_update(request, *args, **kwargs)


class UserActionDetail(AppAuthClass, generics.RetrieveUpdateDestroyAPIView):
    queryset = UserAction.objects.filter()
    permission_classes = [IsAuthenticated]
    serializer_class = UserActionSerializer


class ActionsList(AppAuthClass, generics.ListAPIView):
    permission_classes = [IsAuthenticated]
    queryset = UserAction.objects.all()
    serializer_class = UserActionSerializer


class CarsList(AppAuthClass, generics.ListAPIView):
    permission_classes = [IsAuthenticated]
    # queryset = Car.objects.all()
    serializer_class = CarSerializer
    pagination_class = StandartResultsSetPagination
    

    def get_queryset(self):
        user = self.request.user
        company_instance = user.company_instance
        get = self.request.query_params
        queryset = Car.objects.filter(company_instance=company_instance)
        standart_radius = 200
        working_group = None
        # return queryset.filter(drivers__first_name='i')
        # queryset = Car.objects.all()

        # if user.is_superuser or user.is_staff:
        #     return Car.objects.all()

        if 'wg' in get:
            working_group_set = WorkingGroup.objects.filter(company_instance=user.company_instance, group_name__icontains=get['wg'])
            if working_group_set.exists():
                working_group = working_group_set.first()

        if working_group != None:
            queryset = queryset.filter(active_driver__user__working_group=working_group.pk)
            

        if 'filter_type' in get:
            if get['filter_type'] == 'single':
                if 'filter_field' in get:
                    field = get['filter_field']
                    condition = get['condition']
                    value = get['value']

                    if value == 'false':
                        value = False
                    if value == 'true':
                        value = True

                    if condition == 'equal' or condition == 'more' or condition == 'less' or condition == 'contains':
                        if condition == 'more':
                            field = field + '__gte'
                        elif condition == 'less':
                            field = field + '__lte'
                        elif condition == 'contains':
                            field = field + '__icontains'

                        kwargs = {field: value}
                        queryset = queryset.filter(**kwargs)

                    elif condition == 'not_equal':
                        kwargs = {field: value}
                        queryset = queryset.exclude(**kwargs)
            elif get['filter_type'] == 'multipart':
                kwargs = {}
                args = []
                for param in get:
                    splitted_param = param.split('__')
                    field = splitted_param[0]
                    # full_field = splitted_param[:-1]
                    prefix = splitted_param[-1] if len(splitted_param) > 1 else None
                    value = get[param]

                    if value == 'false':
                        value = False
                    if value == 'true':
                        value = True

                    if hasattr(Car, field):
                        if field == 'drivers':
                            q_objects = Q(drivers__user__first_name__icontains=get[param]) | Q(drivers__user__last_name__icontains=get[param])
                            args.append(q_objects)
                        elif prefix == 'or':
                            or_values = get[param].split(',')
                            field__prefix = field + '__icontains'
                            q_objects = Q()
                            for or_value in or_values:
                                filter_value = {
                                    field__prefix: or_value
                                }
                                q_objects |= Q(**filter_value)
                            args.append(q_objects)
                        else:
                            kwargs[param] = value

                queryset = queryset.filter(*args, **kwargs)

        if 'order_by' in get:
            order_by = get['order_by']
            if order_by != '':
                if get['order'] == 'DESC':
                    order_by = '-' + order_by
                queryset = queryset.order_by(order_by)

        if 'free_only' in get:
            if 'ignore_bid' in get:
                queryset = queryset.filter(Q(status=1) | Q(status=4))
            else:
                queryset = queryset.filter(status=1)
            queryset = queryset.filter(~Q(location=None) & ~Q(location=""), load=None).exclude(active_driver=None).select_related('active_driver', 'status')

            if 'load_id' in get:
                new_queryset = list()
                load = Load.objects.get(id=get['load_id'])

                for car in queryset:
                    # if car.active_driver.is_enable == False:
                    #     continue

                    driver = car.active_driver
                    if LoadInHistory.objects.filter(removedDateTime=None, load=get['load_id'], driver=driver, action="Bid").exists():
                        bid = LoadInHistory.objects.filter(removedDateTime=None, load=get['load_id'], driver=driver, action="Bid").first().driver_price
                        car.bid = bid
                    else:
                        car.bid = 0
                    load_loc = load.start_location.split(',')
                    car_loc = car.location.split(',')
                    miles_out = round(distance.distance(car_loc, load_loc).miles / 0.86)
                    if miles_out < standart_radius or car.active_driver.pk == 179 or car.active_driver.pk == 186:
                        car.miles_out = miles_out
                        new_queryset.append(car)
                queryset = new_queryset
                queryset = sorted(queryset, key=lambda car: (car.bid, car.miles_out), reverse=False)
     
        if 'geo' in get and 'miles_range' in get:
            standart_radius = int(get['miles_range'])
            coords = ''
            new_queryset = list()
            queryset = queryset.exclude(location=None).exclude(location="")

            bing_resp = requests.get("http://dev.virtualearth.net/REST/v1/Locations?query=" + get['geo'].replace(' ', '%20') + "&key=" + settings.BING_API_KEY)
            json_bing_resp = json.loads(bing_resp.text)
            
            if json_bing_resp['statusCode'] == 200:
                if len(json_bing_resp['resourceSets'][0]['resources']) > 0:
                    coords = json_bing_resp['resourceSets'][0]['resources'][0]['point']['coordinates']
                else:
                    return []

            for car in queryset:
                miles_out = round(distance.distance(car.location.split(','), coords).miles / 0.86)
                if miles_out <= standart_radius:
                    car.miles_out = miles_out
                    car.eta = time_transform(round(miles_out / 20 * 60))
                    new_queryset.append(car)
            queryset = new_queryset


        return list(set(queryset))

    # @method_decorator(cache_page(60*10))
    # @method_decorator(vary_on_cookie)
    def list(self, request, *args, **kwargs):
        queryset = self.get_queryset()
        page = self.paginate_queryset(queryset)

        # Car.objects.get(id=2).drivers.add(DriverInfo.objects.get(pk=178))

        if page is not None:
            queryset = page
            serializer = self.get_serializer(queryset, many=True)
            return self.get_paginated_response(serializer.data)

        serializer = self.get_serializer(queryset, many=True)
        return Response(serializer.data)


class CarCreate(AppAuthClass, generics.CreateAPIView):
    permission_classes = []
    serializer_class = CarCreateSerializer

    def perform_create(self, serializer):
        post = self.request.data
        user = self.request.user
        
        active_driver = None

        if 'active_driver_id' in post:
            active_driver = DriverInfo.objects.get(pk=self.request.data['active_driver_id'])
            try:
                driver_last_car = Car.objects.get(active_driver=active_driver)
                driver_last_car.active_driver = None
                driver_last_car.save(update_fields=['active_driver'])
            except:
                pass

        new_car = serializer.save(status=CarStatus.objects.get(id=1), active_driver=active_driver, company_instance=user.company_instance)
        # if 'drivers' in post and len(post['drivers']) > 0:
        #     new_car.drivers.set(post['drivers'])


class CarDetail(AppAuthClass, generics.RetrieveUpdateDestroyAPIView):
    queryset = Car.objects.filter()
    permission_classes = [IsAuthenticated]
    serializer_class = CarCreateSerializer

    def perform_update(self, serializer):
        user = self.request.user
        
        post = self.request.data
        car = self.get_object()
        location = car.location


        if 'availableCity' in post and post['availableCity'] != '' and car.active_driver != None:
            bing_resp = requests.get("http://dev.virtualearth.net/REST/v1/Locations/" + post['availableCity'] + "?key=" + settings.BING_API_KEY)
            json_bing_resp = json.loads(bing_resp.text)
            
            if json_bing_resp['statusCode'] == 200:
                res = json_bing_resp['resourceSets'][0]['resources']
                if len(res) > 0:
                    location = str(res[0]['point']['coordinates'][0]) + ',' + str(res[0]['point']['coordinates'][1])
                    car.active_driver.location = location
                    car.active_driver.save(update_fields=['location'])

        if 'active_driver_id' in post:
            try:
                active_driver = DriverInfo.objects.get(pk=post['active_driver_id'])
                try:
                    driver_last_car = Car.objects.get(active_driver=active_driver)
                    driver_last_car.active_driver = None
                    driver_last_car.save(update_fields=['active_driver'])
                except:
                    pass
                finally:
                    serializer.save(active_driver=active_driver, location=location)
            except:
                pass
        else:       
            serializer.save(location=location)

    def put(self, request, *args, **kwargs):
        return self.partial_update(request, *args, **kwargs)

    # @method_decorator(cache_page(60*60))
    # @method_decorator(vary_on_cookie)
    def get(self, request, *args, **kwargs):
        return super().get(request, *args, **kwargs)


class UserChatGroups(AppAuthClass, generics.ListCreateAPIView):
    permission_classes = [IsAuthenticated]
    serializer_class = ChatGroupsSerializer

    def get_queryset(self):
        user = self.request.user
        chat_groups = ChatGroup.objects.filter(Q(user_initiator=user) | Q(user_member=user))
        return chat_groups


class UserChats(AppAuthClass, generics.ListCreateAPIView):
    permission_classes = [IsAuthenticated]
    serializer_class = UserChatsSerializer

    # def get_serializer(self, *args, **kwargs):
    #     serializer_class = self.get_serializer_class()
    #     kwargs['context'] = {
    #         'request': self.request
    #     }
    #     return serializer_class(*args, **kwargs)

    def get_queryset(self):
        user = self.request.user
        get = self.request.query_params
        
        if user.role.pk == 3:
            chat_groups = Chat.objects.filter(removedDateTime=None)
        else:
            chat_groups = Chat.objects.filter(company_instance=user.company_instance, removedDateTime=None)
            if user.role.pk != 4:
                chat_groups = chat_groups.filter(users=user)

        if 'search' in get:
            chat_groups = chat_groups.filter(Q(users__first_name__icontains=get['search']) | Q(users__last_name__icontains=get['search']) | Q(users__email__icontains=get['search']))
        
        return chat_groups

    def list(self, request):
        user = request.user
        chat_groups = self.get_queryset()
        serializer = UserChatsSerializer(chat_groups,context={'request': request}, many=True)
        serializer_data = sorted(
            serializer.data, key=lambda k: k['last_message']['id'] if k['last_message']['chat_group'] != None else 0, reverse=True)
        # chat_groups = Chat.objects.all()
        return Response(serializer_data)

    def create(self, request, *args, **kwargs):
        user = request.user
        post = request.data
        users = list()
        users.append(user)

        try:
            driver_user = User.objects.get(~Q(driver_info=None), id=post['driver_id'])
        except:
            return Response({
                'message': 'Driver doesn`t exist'
            })

        driver_info = driver_user.driver_info
        current_owner = driver_info.owner

        if current_owner != None:
            users.append(current_owner.user)
            owner_drivers = list(DriverInfo.objects.filter(owner=current_owner))
            for driver in owner_drivers:
                if driver.pk != current_owner.pk:
                    users.append(driver.user)
        else:
            users.append(driver_user)

        chat_queryset = Chat.objects.filter(users=user, removedDateTime=None).prefetch_related('users')
        for user_entity in users:
            chat_queryset = chat_queryset.filter(users=user_entity)

        new_chat = None
        chat_queryset = list(chat_queryset)
        if len(chat_queryset) > 0:
            for chat in chat_queryset:
                if chat.users.count() == len(users):
                    new_chat = chat_queryset[0]
                    new_chat.removedDateTime = None
                    new_chat.save(update_fields=['removedDateTime'])

        if new_chat == None:
            new_chat = Chat.objects.create(company_instance=user.company_instance)
            new_chat.users.set(users)

        return Response(ChatWithMessagesSerializer(new_chat, context={'request': request}).data)


class RetrieveChat(AppAuthClass, generics.RetrieveUpdateDestroyAPIView):
    permission_classes = [InChat]
    serializer_class = ChatWithMessagesSerializer
    queryset = Chat.objects.filter()

    def retrieve(self, request, *args, **kwargs):
        instance = self.get_object()
        serializer = self.get_serializer(instance)
        user = request.user

        unread_messages = ChatMessage.objects.filter(chat_group=instance.id).exclude(users_read=user.id)
        for unread_message in unread_messages:
            unread_message.users_read.add(user)

        return Response(serializer.data)

    def perform_update(self, serializer):
        user = self.request.user
        post = self.request.data
        curr_chat = self.get_object()

        users_in_action = list(User.objects.filter(id__in=post['users']))
        if 'action' in post:
            action_type = post['action']
            if action_type == 'add':
                curr_chat.users.add(*users_in_action)
            elif action_type == 'remove':
                curr_chat.users.remove(*users_in_action)
        else:
            if curr_chat.driver != None:
                users_in_action.append(curr_chat.driver.user)
            curr_chat.users.set(users_in_action)


class WorkingGroups(AppAuthClass, generics.ListCreateAPIView):
    permission_classes = [IsAuthenticated]
    serializer_class = WorkingGroupSerializer

    def get_queryset(self):
        user = self.request.user
        company = user.company_instance
        working_groups = WorkingGroup.objects.filter(company_instance=company)

        return working_groups

    @method_decorator(cache_page(60*60*2))
    @method_decorator(vary_on_cookie)
    def get(self, request, *args, **kwargs):
        return super().get(request, *args, **kwargs)

    def perform_create(self, serializer):
        user = self.request.user
        
        post = self.request.data
        group_name = post['group_name']
        users_ids = post['users']
        users_in_chat = list(users_ids)
        users = User.objects.filter(id__in=users_ids)

        users = list(users)
        if users.exclude(owner_info=None).exists():
            for owner in users.exclude(owner_info=None):
                for driver in owner.owner_info.drivers.all():
                    users.append(driver.user)

        dispatchers = users.filter(role=5)
        owners = users.exclude(owner_info=None)
        Chat.objects.filter(load=None, working_group=None, users__in=owners).delete() # удаляем все чаты с овнерами, которые добавлены в группу

        chats_with_dispatchers = Chat.objects.filter(load=None, working_group=None, users__in=dispatchers).prefetch_related('users')
        # удаляем диспетчеров из всех чатов с овнерами
        for chats_with_dispatcher in chats_with_dispatchers:
            for dispatcher in dispatchers:
                if dispatcher in chats_with_dispatcher.users.all():
                    chats_with_dispatcher.users.remove(dispatcher)

        # проверка на существование группы с таким названием и добавление префикса к имени
        existings_groups_count = WorkingGroup.objects.filter(company_instance=user.company_instance, group_name=group_name).count()
        prefix = 0

        if existings_groups_count > 0:
            while existings_groups_count > 0:
                prefix = prefix + 1
                group_name_with_prefix = group_name + '_' + str(prefix)
                existings_groups_count = WorkingGroup.objects.filter(company_instance=user.company_instance, group_name=group_name_with_prefix).count()
                
        if prefix > 0:
            group_name = group_name + '_' + str(prefix)

        new_group = serializer.save(group_name=group_name, users=users, company_instance=user.company_instance)
        # переопределяем группу для пользователя, который указан в качествее лидера
        if 'group_lead' in post:
            if post['group_lead'] != None:
                users_in_chat.append(post['group_lead'])
                group_lead = User.objects.get(id=post['group_lead'])
                group_lead.my_working_group = new_group
                group_lead.save(update_fields=['my_working_group'])

        # создаем чат для группы
        chat = Chat.objects.create(working_group=new_group, company_instance=user.company_instance)
        chat.users.set(users_in_chat)


class WorkingGroupsDetail(AppAuthClass, generics.RetrieveUpdateDestroyAPIView):
    queryset = WorkingGroup.objects.filter()
    permission_classes = [IsAuthenticated]
    serializer_class = WorkingGroupSerializer

    def perform_update(self, serializer):
        user = self.request.user
        company_instance = user.company_instance
        post = self.request.data
        users_ids = post['users']
        users = User.objects.filter(id__in=users_ids)
        users_in_chat = list(users_ids)
        group = self.get_object()

        existing_users = group.users.all()
        for group_user in existing_users:
            if hasattr(group_user, 'owner_info') and group_user.owner_info != None and group_user.id not in users_ids:
                chat = Chat.objects.create(company_instance=user.company_instance)
                chat.users.add(group_user)

        # переопределяем группу для пользователя, который указан в качествее лидера
        if 'group_lead' in post:
            if post['group_lead'] != None:
                users_in_chat.append(post['group_lead'])
                User.objects.filter(my_working_group=self.get_object().id).update(my_working_group=None)
                group_lead = User.objects.get(id=post['group_lead'])
                group_lead.my_working_group = self.get_object()
                group_lead.save(update_fields=['my_working_group'])

        if users.exclude(owner_info=None).exists():
            for owner in users.exclude(owner_info=None):
                for driver in owner.owner_info.drivers.all():
                    users_in_chat.append(driver.pk)

        wg = serializer.save()

        chat_users = User.objects.filter(id__in=users_in_chat)
        group.users.set(chat_users)
        group_unassigned = WorkingGroup.objects.filter(company_instance=company_instance, group_name="Unassigned")
        # определяем всех свободных диспетчеров в группу Unassigned
        if group_unassigned.count() > 0:
            group_unassigned = group_unassigned[0]
            User.objects.filter(company_instance=company_instance.pk, role=5).filter(Q(working_group=None) & Q(my_working_group=None)).update(working_group=group_unassigned)
        
        # возвращаем вободных диспетчеров в чаты с овнерами
        free_chats = Chat.objects.filter(working_group=None, load=None, company_instance=company_instance.pk)
        for free_chat in free_chats:
            free_dispatchers = User.objects.filter(company_instance=company_instance.pk, role=5, my_working_group=None).filter(Q(working_group=None) | Q(working_group__group_name="Unassigned"))
            free_chat.users.set(free_dispatchers)


class CarOwnersView(AppAuthClass, generics.ListCreateAPIView):
    permission_classes = [IsAuthenticated]
    serializer_class = CarOwnerSerializer
    # pagination_class = StandartResultsSetPagination

    def get_queryset(self):
        user = self.request.user
        company_instance = user.company_instance
        owners = User.objects.exclude(owner_info=None)

        if user.company_instance != None:
            owners = owners.filter(company_instance=company_instance.pk)

        if 'for_working_group' in self.request.query_params:
            owners = owners.filter(my_working_group=None).filter(Q(working_group=None) | Q(working_group__group_name="Unassigned"))

        return owners

    @method_decorator(cache_page(60*60*2))
    @method_decorator(vary_on_cookie)
    def get(self, request, *args, **kwargs):
        return super().get(request, *args, **kwargs)

    def post(self, request, *args, **kwargs):
        user = request.user
        company_instance = user.company_instance
        post = request.data
        user_data = dict(post['user'])
        owner_info = dict(post)

        user_data['password'] = 'password'
        user_data['role'] = 10

        owner_serializer = UserCreateSerializer(data=user_data)
        owner_serializer.is_valid(raise_exception=True)
        group_unassigned = None
        group_unassigned_set = WorkingGroup.objects.filter(company_instance=user.company_instance, group_name="Unassigned")
        free_dispatchers = None
        if group_unassigned_set.count() > 0:
            group_unassigned = group_unassigned_set.first()
            free_dispatchers = User.objects.filter(company_instance=company_instance.pk, role=5, working_group=group_unassigned)

        new_owner = owner_serializer.save(working_group=group_unassigned, company_instance=company_instance)

        owner_info['user'] = new_owner
        CarOwner.objects.create(**owner_info)

        chat = Chat.objects.create(company_instance=user.company_instance)
        users_in_chat = list()
        users_in_chat.append(new_owner)
        
        if free_dispatchers != None:
            for free_dispatcher in free_dispatchers:
                users_in_chat.append(free_dispatcher)

        chat.users.set(users_in_chat)

        return Response(owner_serializer.data)
        
        # try:
            # load = Load.objects.get(id=request.data.load_id)
            # document = serializer.save(load=load)
        # except:
            # document = serializer.save()


class CarOwnerDetail(AppAuthClass, generics.RetrieveUpdateDestroyAPIView):
    queryset = CarOwner.objects.filter()
    permission_classes = [IsAuthenticated]
    serializer_class = OwnerSerializer
    
    def put(self, request, *args, **kwargs):
        return self.partial_update(request, *args, **kwargs)

    @method_decorator(cache_page(60*60*2))
    @method_decorator(vary_on_cookie)
    def retrieve(self, request, *args, **kwargs):
        return super().retrieve(request, *args, **kwargs)


class CarsUpdateView(AppAuthClass, viewsets.ViewSet):
    permission_classes = []

    def update(self, request):
        post = request.data
        cars = post['cars']

        if 'status_id' in post:
            new_status = post['status_id']
            Car.objects.filter(pk__in=cars).update(status=new_status)

        return Response({
            'result': 'ok'
        })


class DriversUpdateView(AppAuthClass, viewsets.ViewSet):
    permission_classes = []

    def update(self, request):
        post = request.data
        drivers = post['drivers']

        if 'status_id' in post:
            new_status = post['status_id']
            DriverInfo.objects.filter(pk__in=drivers).update(status=new_status)

        if 'responsible_user' in post:
            responsible_user = post['responsible_user']
            DriverInfo.objects.filter(pk__in=drivers).update(responsible_user=responsible_user)

        return Response({
            'result': 'ok'
        })


class BidsView(AppAuthClass, viewsets.ViewSet):
    permission_classes = [IsAuthenticated]

    @method_decorator(cache_page(60*20))
    @method_decorator(vary_on_cookie)
    def get_bids(self, request):
        user = request.user

        get = request.query_params
        company_instance = user.company_instance

        queryset = LoadInHistory.objects.filter(removedDateTime=None, action="Bid")
        if company_instance != None:
            queryset = queryset.filter(driver__user__company_instance=company_instance.pk)
        if 'load_id' in get:
            queryset = queryset.filter(load=int(get['load_id']))
        if 'driver_id' in get:
            queryset = queryset.filter(driver=int(get['driver_id']))

        serializer = LoadInHistorySerializer(queryset, many=True)

        return Response(serializer.data)


    def update_bids(self, request):
        user = request.user
        company_instance = user.company_instance
        post = request.data

        queryset = LoadInHistory.objects.filter(removedDateTime=None, action="Bid", driver__user__company_instance=company_instance.pk)
        if 'load_id' in post:
            queryset = queryset.filter(load=int(post['load_id']))
        if 'driver_id' in post:
            queryset = queryset.filter(driver=int(post['driver_id']))
        if 'ids' in post:
            queryset = queryset.filter(id__in=post['ids'])

        if 'action' in post:
            if post['action'] == 'delete':
                queryset.update(removedDateTime=datetime.now())

        return Response({
            'result': 'ok'
        })


class UserChat(AppAuthClass, generics.RetrieveUpdateDestroyAPIView):
    permission_classes = [InChatGroup]
    serializer_class = ChatSerializer
    queryset = ChatGroup.objects.filter()

    def perform_update(self, serializer):
        chat = self.get_object()
        post = self.request.data
        if 'users' in post:
            users = list(post['users'])
            if chat.driver != None:
                users.append(chat.driver.pk)
            chat.users.set(users)
        serializer.save()


class ChatMessageView(AppAuthClass, generics.CreateAPIView):
    permission_classes = [IsAuthenticated]
    serializer_class = MessageSerializer

    def perform_create(self, serializer):
        user_from = self.request.user
        user_to = User.objects.get(pk=self.request.data['user_to'])
        chat_group = None

        try:
            chat_group = ChatGroup.objects.get(Q(user_initiator=user_to, user_member=user_from) | Q(user_initiator=user_from, user_member=user_to))
        except:
            chat_group = ChatGroup.objects.create(user_initiator=user_from, user_member=user_to)
        
        serializer.save(user_from=user_from, user_to=user_to, chat_group=chat_group)


class SettingsView(AppAuthClass, generics.RetrieveUpdateAPIView):
    serializer_class = UserSettingsSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        user = self.request.user
        return user

    def get_object(self):
        queryset = self.get_queryset()
        self.check_object_permissions(self.request, queryset)
        return queryset.company_instance

    @method_decorator(cache_page(60*60*20))
    @method_decorator(vary_on_cookie)
    def get(self, request):
        user = request.user

        serializer = CompanySerializer(user.company_instance)
        return Response(serializer.data)

    def put(self, request, *args, **kwargs):

        self.lookup_field = ''
        kwargs['pk'] = request.user.company_instance.pk

        return self.partial_update(request, *args, **kwargs)


class BrokersList(AppAuthClass, generics.ListCreateAPIView):
    permission_classes = [IsAuthenticated]
    serializer_class = BrokersSerializer

    def get_queryset(self):
        get = self.request.query_params
        queryset = Broker.objects.filter()

        if 'phone_number' in get:
            queryset = queryset.filter(phone_number__icontains=get['phone_number'])

        return queryset


class TwilioMessagesView(AppAuthClass, viewsets.ViewSet):
    permission_classes = []
    
    def post(self, request):
        get = request.query_params
        post = request.data
        new_message = None
        
        if 'user_id' in get:
            import asyncio

            user_to = User.objects.get(id=get['user_id'])
            company_instance = user_to.company_instance
            
            data = {}
            media = list()

            if 'NumMedia' in post:
                if int(post['NumMedia']) > 0:
                    for i in range(0, int(post['NumMedia'])):
                        media.append({
                            'type': post['MediaContentType' + str(i)],
                            'url': post['MediaUrl' + str(i)]
                        })

            media = json.dumps(media)
            
            if User.objects.filter(phone_number=post['From'], company_instance=company_instance).exists():
                user_from = User.objects.get(phone_number=post['From'])
                new_message = TwilioMessage.objects.create(user_from=user_from, user_to=user_to, fromNumber=post['From'], content=post['Body'], media=media, company_instance=company_instance)

                data = {
                    'driver': UserSerializer(user_from).data,
                    'message': post['Body']
                }

            elif Broker.objects.filter(phone_number=post['From']).exists():
                broker = Broker.objects.filter(phone_number=post['From']).first()
                new_message = TwilioMessage.objects.create(broker_from=broker, user_to=user_to, fromNumber=post['From'], content=post['Body'], media=media, company_instance=company_instance)
                data = {
                    'broker': {
                        'name': broker.name,
                        'phone_number': broker.phone_number
                    },
                    'message': post['Body']
                }
            else:
                broker = Broker.objects.create(name="New " + post['From'], phone_number=post['From'])
                new_message = TwilioMessage.objects.create(broker_from=broker, user_to=user_to, fromNumber=post['From'], content=post['Body'], media=media, company_instance=company_instance)
                data = {
                    'broker': {
                        'name': broker.name,
                        'phone_number': broker.phone_number
                    },
                    'message': post['Body']
                }

            data['media'] = media
            
            company_hash = user_to.company_instance.company_hash
            asyncio.get_event_loop().run_until_complete(send_update_sms_notice(company_hash, data))
        elif 'to_broker' in get:
            user = self.request.user
            account_sid = user.company_instance.twilio_account_sid
            auth_token = user.company_instance.twilio_auth_token
            messaging_service_sid = user.company_instance.twilio_messaging_service_sid
            client = Client(account_sid, auth_token)
            content = post['content']

            media = list()
            if 'media' in post:
                media.append({
                        'type': post['mediatype'],
                        'url': post['media']
                    })
            
            
            media = json.dumps(media)

            if 'broker_ids' in post:
                brokers = Broker.objects.filter(id__in=post['broker_ids'])
                for broker in brokers:
                    to_number = broker.phone_number

                    sms = dict(body=content, messaging_service_sid=messaging_service_sid, to=to_number)
                    if 'media' in post:
                        sms['media_url'] = post['media']
                    
                    message = client.messages.create(**sms)
                    new_message = TwilioMessage.objects.create(user_from=user, broker_to=broker, toNumber=to_number, content=content, media=media, company_instance=user.company_instance)

            else:
                number = phone_filter(post['number'], '1')
                broker = None
                brokers = Broker.objects.filter(phone_number=number, company_instance=user.company_instance)
                if brokers.exists():
                    broker = brokers.first()
                else:
                    broker = Broker.objects.create(phone_number=number, name=post['name'], company_instance=user.company_instance)

                to_number = number

                sms = dict(body=content, messaging_service_sid=messaging_service_sid, to=to_number)
                media = list()
                if 'media' in post:
                    sms['media_url'] = post['media']
                    media.append({
                            'type': post['mediatype'],
                            'url': post['media']
                        })
                
                
                media = json.dumps(media)
                  
                message = client.messages.create(**sms)
                new_message = TwilioMessage.objects.create(user_from=user, broker_to=broker, toNumber=to_number, content=content, media=media, company_instance=user.company_instance)

        elif 'numbers' in post:
            user = self.request.user
            post['users_from'] = user
            content = post['content']

            account_sid = user.company_instance.twilio_account_sid
            auth_token = user.company_instance.twilio_auth_token
            messaging_service_sid = user.company_instance.twilio_messaging_service_sid
            client = Client(account_sid, auth_token)

            media = list()
            if 'media' in post:
                media.append({
                        'type': post['mediatype'],
                        'url': post['media']
                    })
            
            media = json.dumps(media)
            
            for number in post['numbers']:
                user_to = User.objects.get(phone_number=number)
                to_number = number

                sms = dict(body=content, messaging_service_sid=messaging_service_sid, to=to_number)
                if 'media' in post:
                    sms['media_url'] = post['media']

                message = client.messages.create(**sms)

                new_message = TwilioMessage.objects.create(user_from=user, user_to=user_to, toNumber=to_number, content=content, media=media, company_instance=user.company_instance)              
        else:
            content = post['content']
            to_number = post['number']
            user = self.request.user
            user_to = User.objects.filter(phone_number=to_number)[0]

            account_sid = user.company_instance.twilio_account_sid
            auth_token = user.company_instance.twilio_auth_token
            messaging_service_sid = user.company_instance.twilio_messaging_service_sid
            client = Client(account_sid, auth_token)

            sms = dict(body=content, messaging_service_sid=messaging_service_sid, to=to_number)
            media = list()
            if 'media' in post:
                sms['media_url'] = post['media']
                media.append({
                        'type': post['mediatype'],
                        'url': post['media']
                    })
            
            media = json.dumps(media)

            message = client.messages.create(**sms)

            new_message = TwilioMessage.objects.create(user_from=user, user_to=user_to, toNumber=to_number, content=content, media=media)


        return Response(TwilioMessageSerializer(new_message).data)


class DriverChatView(AppAuthClass, generics.RetrieveDestroyAPIView):
    serializer_class = DriverChatSerializer
    queryset = User.objects.filter()
    permission_classes = [IsAuthenticated]

    
    def retrieve(self, request, *args, **kwargs):
        instance = self.get_object()
        serializer = self.get_serializer(instance)

        TwilioMessage.objects.filter(Q(toNumber=instance.phone_number) | Q(fromNumber=instance.phone_number), status="Send").update(status="Read")

        return Response(serializer.data)


class BrokerChatView(AppAuthClass, generics.RetrieveAPIView):
    serializer_class = BrokerChatSerializer
    queryset = Broker.objects.filter()
    permission_classes = [IsAuthenticated]

    def retrieve(self, request, *args, **kwargs):
        instance = self.get_object()
        serializer = self.get_serializer(instance)

        TwilioMessage.objects.filter(broker_to=instance.id, status="Send").update(status="Read")

        return Response(serializer.data)


class LoadsMap(AppAuthClass, viewsets.ViewSet):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        user = request.user

        cars = Car.objects.filter(company_instance=user.company_instance).select_related('dispatcher')
        items = list()

        for car in cars:
            items.append(dict(
                status=car.status,
                number=car.number,
                dispatcher=car.dispatcher.email,
                location=car.location,
            ))
        
        return Response({
            "count": cars.count(),
            "items": items
        })

    
class CallsList(AppAuthClass, generics.ListCreateAPIView):
    permission_classes = [IsAuthenticated]
    serializer_class = CallSerializer

    def get_queryset(self):
        user = self.request.user
    
        get = self.request.query_params
        queryset = Call.objects.filter(company_instance=user.company_instance)

        if 'user' in get:
            queryset = queryset.filter(author=get['user'])

        filter_kwargs = {}
        filter_args = []
        exclude_kwargs = {}
        exclude_args = []
        for param in get:
            splitted_param = param.split('__')
            field = splitted_param[0]
            value_param = param
            prefix = splitted_param[-1] if len(splitted_param) > 1 else None
            modifier = 'filter'
            if prefix == 'not':
                modifier = 'exclude'
                value_param = '__'.join(splitted_param[:-1])
                prefix = splitted_param[-2]
            value = get[param]

            if value == 'false':
                value = False
            if value == 'true':
                value = True

            if hasattr(Call, field):
                if modifier == 'filter':
                    filter_kwargs[value_param] = value
                elif modifier == 'exclude':
                    exclude_kwargs[value_param] = value
        queryset = queryset.filter(*filter_args, **filter_kwargs).exclude(*exclude_args, **exclude_kwargs)
        
        return queryset.order_by('-created_date')

    def perform_create(self, serializer):
        post = self.request.data
        user = self.request.user
        
        company = user.company_instance
        name_to = ''
        name_from = ''
        avatar_to = ''
        avatar_from = ''
        if User.objects.filter(phone_number=post['number_from']).exists():
            user_from = User.objects.filter(phone_number=post['number_from']).first()
            name_from = user_from.first_name + ' ' + user_from.last_name
            avatar_from = str(user_from.avatar)
        if User.objects.filter(phone_number=post['number_to']).exists():
            user_to = User.objects.filter(phone_number=post['number_to']).first()
            name_to = user_to.first_name + ' ' + user_to.last_name
            avatar_to = str(user_to.avatar)
        serializer.save(company_instance=company, author=user, name_from=name_from, name_to=name_to, avatar_to=avatar_to, avatar_from=avatar_from)
       

class CallDetail(AppAuthClass, generics.RetrieveUpdateDestroyAPIView):
    permission_classes = [IsAuthenticated]
    serializer_class = CallSerializer
    queryset = Call.objects.filter()


class ChangePasswordView(AppAuthClass, generics.UpdateAPIView):
    serializer_class = ChangePasswordSerializer
    model = User
    queryset = User.objects.filter()
    permission_classes = [IsAuthenticated]

    def update(self, request, *args, **kwargs):
        self.object = self.get_object()
        serializer = self.get_serializer(data=request.data)

        if serializer.is_valid():
            # Check old password
            if not self.object.check_password(serializer.data.get("old_password")):
                return Response({"old_password": ["Wrong password."]}, status=status.HTTP_400_BAD_REQUEST)
            if serializer.data.get("new_password_1") != serializer.data.get("new_password_2"):
                return Response({"new_password": ["Passwords are not equal."]}, status=status.HTTP_400_BAD_REQUEST)
            # set_password also hashes the password that the user will get
            self.object.set_password(serializer.data.get("new_password_1"))
            self.object.save()
            response = {
                'status': 'success',
                'code': status.HTTP_200_OK,
                'message': 'Password updated successfully',
                'data': []
            }

            return Response(response)

        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


class BookkeepingView(AppAuthClass, viewsets.ViewSet):
    permission_classes = [IsAuthenticated]

    def change_statuses(self, request):
        post = request.data

        Payment.objects.filter(id__in=post['ids']).update(status=post['status'])
        return Response({
            'success': True
        })


    def data(self, request):
        import xlwt

        user = request.user
        get = request.query_params

        if not hasattr(user, 'company_instance') and user.company_instance != None:
            return Response('Not authorized')

        company_instance = user.company_instance
        name = datetime.today().strftime("%Y-%m-%d")

        today = datetime.today()
        next_day = today + timedelta(days=-today.weekday(), weeks=1)
        last_day = today - timedelta(days=today.weekday())

        next_day_formatted = ''
        last_day_formatted = ''
        if 'next_day' in get:
            next_day_formatted = get['next_day'] + ' 00:00'
        else:
            next_day_formatted = next_day.strftime('%Y-%m-%d %H:%M')

        if 'last_day' in get:
            last_day_formatted = get['last_day'] + ' 00:00'
        else:
            last_day_formatted = last_day.strftime('%Y-%m-%d %H:%M')

        date_filter = {
            'created_date__lte': next_day_formatted,
            'created_date__gte': last_day_formatted
        }

        queryset = Payment.objects.filter(load__company_instance=company_instance, load__removedDateTime=None).filter(**date_filter)

        filter_kwargs = {}
        filter_args = []
        exclude_kwargs = {}
        exclude_args = []
        for param in get:
            splitted_param = param.split('__')
            field = splitted_param[0]
            value_param = param
            prefix = splitted_param[-1] if len(splitted_param) > 1 else None
            modifier = 'filter'
            if prefix == 'not':
                modifier = 'exclude'
                value_param = '__'.join(splitted_param[:-1])
                prefix = splitted_param[-2]
            value = get[param]

            if value == 'false':
                value = False
            if value == 'true':
                value = True
            # Пока отменим фильтрацию по доскам. Никто не знает, как это должно работать)
            if field == 'brokerage':
                continue

            if hasattr(Load, field):
                if prefix == 'or':
                    # Фильтр типа ИЛИ
                    or_values = get[param].split(',')
                    field__prefix = field + '__icontains'
                    q_objects = Q()
                    for or_value in or_values:
                        filter_value = {
                            field__prefix: or_value
                        }
                        q_objects |= Q(**filter_value)
                    if modifier == 'filter':
                        filter_args.append(q_objects)
                    elif modifier == 'exclude':
                        exclude_args.append(q_objects)
                    
                else:
                    if modifier == 'filter':
                        filter_kwargs[value_param] = value
                    elif modifier == 'exclude':
                        exclude_kwargs[value_param] = value
                    
        queryset = queryset.filter(*filter_args, **filter_kwargs).exclude(*exclude_args, **exclude_kwargs).select_related('load', 'user', 'status')
        output = []

        drivers_output = {}
        count = 1

        for index, payment in enumerate(queryset):
            payment_user = payment.user

            wg = payment_user.working_group

            if payment_user.driver_info != None and payment_user.owner == None:
                continue
            
            owner = payment_user.owner

            if owner.company_name in drivers_output:
                drivers_output[owner.company_name]['driver_price'] += load.driver_price
            else:
                number = ''
                for word in company_instance.name.split(' '):
                    number += word[0].upper()

                if wg != None:
                    for word in wg.group_name.split(' '):
                        number += word[0].upper()

                date = datetime.today().strftime('%y')
                number += date
                number += '-'
                if 'counter' in get:
                    number += get['counter'] # Неделя, за которую платим (по счетчику)
                else:
                    number += '0'
                number += '-'
                number += str(count)

                count += 1

                drivers_output[wner.company_name] = {
                    'number': number,
                    'driver_price': payment.amount
                }


        list_keys = list(drivers_output.keys())
        list_keys.sort()

        if 'create_doc' in get:

            drivers_book = xlwt.Workbook()
            drivers_page = drivers_book.add_sheet('A')

            dispatchers_book = xlwt.Workbook()
            dispatchers_page = dispatchers_book.add_sheet('A')

            for index, owner_company in enumerate(list_keys):
                drivers_page.write(index, 0, next_day.strftime('%d/%m/%Y'))
                drivers_page.write(index, 1, drivers_output[owner_company]['number'])
                drivers_page.write(index, 2, owner_company)
                drivers_page.write(index, 3, 'Nonemployee Compensation')
                drivers_page.write(index, 4, drivers_output[owner_company]['driver_price'])

            
            # dispatchers_page.write(index, 0, next_day.strftime('%d/%m/%Y'))
            # dispatchers_page.write(index, 1, number)
            # dispatchers_page.write(index, 2, 'customer job')
            # dispatchers_page.write(index, 3, 'amount')
            # dispatchers_page.write(index, 4, 'trucking')
            # dispatchers_page.write(index, 5, company_instance.name + ' ' + wg1.group_name)



            drivers_name = 'media/qb_xls/drivers_' + name + '.xls'
            dispatchers_name = 'media/qb_xls/dispatchers_' + name + '.xls'

            drivers_book.save(drivers_name)
            # dispatchers_book.save(dispatchers_name)


            return Response([
                'https://altekloads.com/backend/api/' + drivers_name,
                # 'https://altekloads.com/backend/api/' + dispatchers_name
            ]) 
        # else:
        #     pass

        return Response(drivers_output)

    











