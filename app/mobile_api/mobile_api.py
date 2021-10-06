from django.dispatch import dispatcher
from django.utils.decorators import method_decorator
from django.views.decorators.cache import cache_page
from django.views.decorators.vary import vary_on_cookie

from datetime import datetime, timedelta

from django.db.models import Q, F, Max, Count, Sum, Avg
from app.views import AppAuthClass

import random, requests, json

from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework import viewsets

from twilio.rest import Client
from geopy import distance

from api import settings
from app.models import User
from app.serializers import *
from app.permissions import *
from app.pagination import *
from app.helpers.data_filters import *
from app.helpers.get_user_owner import get_user_owner



def create_pages(menu_pages, parent=None):
    for page in menu_pages:
        page_dict = {
            'name': page['text'],
            'url': page['link'],
            'icon': page['icon'],
            'has_childrens': False,
            'parent_page': parent
        }
        if 'icon_alt' in page:
            page_dict['icon_alt'] = page['icon_alt']

        if 'children' in page:
            page_dict['has_childrens'] = True

        new_page = Page.objects.create(
            **page_dict
        )

        if 'children' in page:
            create_pages(page['children'], new_page)



class MobileAuth(viewsets.ViewSet):
    authentication_classes = []
    permission_classes = []

    def test(self, request):
        # Chat.objects.exclude(driver=None).delete()
        # dispatchers_14 = User.objects.filter(company_instance=14, role=5).values_list('id', flat=True)
        # company_14 = Company.objects.get(pk=14)
        # dispatchers_15 = User.objects.filter(company_instance=15, role=5).values_list('id', flat=True)
        # company_15 = Company.objects.get(pk=15)
        
        # for driver in DriverInfo.objects.filter(user__company_instance=14):
        #     chat = Chat.objects.create(
        #         driver=driver,
        #         company_instance=company_14
        #     )
        #     chat.users.set(dispatchers_14)
        
        # for driver in DriverInfo.objects.filter(user__company_instance=15):
        #     chat = Chat.objects.create(
        #         driver=driver,
        #         company_instance=company_15
        #     )
        #     chat.users.set(dispatchers_15)
        
        return Response([Chat.objects.filter(company_instance=14).exclude(driver=None).count(), Chat.objects.filter(company_instance=15).exclude(driver=None).count()]) 

    def get_code_by_sms(self, request):
        post = request.data
        phone_number = phone_filter(post['phone_number'])
        users = User.objects.filter(phone_number=phone_number)

        if len(users) > 0:
            user = users[0]
            
            # account_sid = user.company_instance.twilio_account_sid
            # auth_token = user.company_instance.twilio_auth_token
            account_sid = 'ACc49bbf7ecc1ef3504da55a47f705e301'
            auth_token = '363307736f68598eeddb7fb5629a4838'
            client = Client(account_sid, auth_token)

            client.messages.create(
                body="<#>Your auth code: " + user.driver_info.unique_sms_key + "\r\n /viQ1xVf96ei",
                # messaging_service_sid=user.company_instance.twilio_messaging_service_sid,
                messaging_service_sid='MGdf77e1c2a1ddff60182bf4ae9115fa7c',
                to=phone_number
            )

            return Response({
                'success': True,
                'message': 'SMS was send'
            })

        else:
            return Response({
                'success': False,
                'message': 'User not found'
            })
        
    def auth(self, request):
        post = request.data
        phone_number = phone_filter(post['phone_number'])
        auth_code = post['auth_code']
        users = User.objects.filter(~Q(driver_info=None), phone_number=phone_number)

        if len(users) > 0:
            user = users[0]
            driver_info = user.driver_info

            if user.driver_info.unique_sms_key == auth_code:
                return Response({
                    'success': True,
                    'email': user.email,
                    'password': 'password',
                    'group_id': user.company_instance.id,
                    'user_id': user.id,
                    'company_hash': user.company_instance.company_hash
                })
            else:
                return Response({
                    'success': False,
                    'message': 'Code is wrong'
                })

            driver_info.unique_sms_key = random.randint(1000, 9999)
            driver_info.save(update_fields=['unique_sms_key'])
        else:
            return Response({
                'success': False,
                'message': 'User not found'
            })


class MobileAPI(AppAuthClass, viewsets.ViewSet):
    permission_classes = [IsAuthenticated]
    pagination_class = SmallResultsSetPagination

    @property
    def paginator(self):
        if not hasattr(self, '_paginator'):
            if self.pagination_class is None:
                self._paginator = None
            else:
                self._paginator = self.pagination_class()
        return self._paginator

    def paginate_queryset(self, queryset):
        if self.paginator is None:
            return None
        return self.paginator.paginate_queryset(queryset, self.request, view=self)

    def get_paginated_response(self, data):
        assert self.paginator is not None
        return self.paginator.get_paginated_response(data)

    def update_location(self, request):
        user = request.user
        post = self.request.data

        if post['location'] == '37.4219977,-122.0839723':
            return Response()

        if hasattr(user, 'driver_info'):
            driver_info = user.driver_info

            bing_resp = requests.get("http://dev.virtualearth.net/REST/v1/Locations/" + post['location'] + "?key=" + settings.BING_API_KEY)
            json_bing_resp = json.loads(bing_resp.text)
            location_name = ''
            location = post['location']
            
            if json_bing_resp['statusCode'] == 200:
                if len(json_bing_resp['resourceSets'][0]['resources']) > 0:
                    location_name = json_bing_resp['resourceSets'][0]['resources'][0]['name']
            
            if location_name != None:
                Car.objects.filter(active_driver=user.driver_info).update(location=location, availableCity=location_name)
            else:
                Car.objects.filter(active_driver=user.driver_info).update(location=location)

            user.zip_code = ''
            driver_info.location = location
            user.save(update_fields=['zip_code'])
            driver_info.save(update_fields=['location'])

            for load in Load.objects.filter(removedDateTime=None, resp_driver=driver_info):
                Location.objects.create(driver=driver_info, point=location, location_name=location_name, timestamp=round(datetime.now().timestamp()), load=load)


            return Response({
                    'success': True,
                    'message': 'Location updated successfully'
                })

        else:
            return Response({
                    'success': False,
                    'message': 'Something wrong'
                })

    def send_bid(self, request):
        post = request.data
        load = Load.objects.get(id=post['load'])
        price = post['price']
        user = request.user
        
        # try:
        load_in_history = LoadInHistory.objects.create(load=load, action="Bid", driver_price=post['price'], driver=user.driver_info)

        return Response({
            'bid': load_in_history.id,
            'success': True
        })
        # except:
        #     return Response({
        #         'success': False
        #     })

    def remove_bid(self, request):
        post = request.data
        try:
            LoadInHistory.objects.get(id=post['bid_id']).delete()
            return Response({
                'success': True
            })
            
        except:
            return Response({
                'success': False,
                'message': 'No bid with this id: ' + post['bid_id']
            })

    @method_decorator(cache_page(60*10))
    @method_decorator(vary_on_cookie)    
    def get_loads_in_work(self, request):
        user = request.user
        queryset = Load.objects.filter(removedDateTime=None)

    def edit_driver(self, request):
        user = request.user
        driver_info = user.driver_info
        post = request.data

        if 'is_enable' in post:
            driver_info.is_enable = post['is_enable']
            driver_info.available_time = datetime.now()
            driver_info.save(update_fields=['is_enable', 'available_time'])
            if post['is_enable'] == False:
                Car.objects.filter(active_driver=driver_info).update(status=2)
            if post['is_enable'] == True:
                Car.objects.filter(active_driver=driver_info).update(status=1)
            

        if 'status' in post:
            status = DriverStatus.objects.get(id=post['status'])
            driver_info.status = status
            driver_info.save(update_fields=['status'])
            
        return Response(DriverInfoSerializer(driver_info).data)

    @method_decorator(cache_page(60*60*10))
    @method_decorator(vary_on_cookie)
    def profile(self, request):
        user = request.user

        if not Car.objects.filter(active_driver=user.id).exists():
            car = Car.objects.filter(drivers=user.id).first()
            car.active_driver = user.driver_info
            car.save(update_fields=['active_driver'])

        return Response(UserDetailSerializer(user).data)

    def get_loads(self, request):
        # self.pagination_class = LargeResultsSetPagination
        user = request.user
        get = request.query_params
        standart_radius = 300
        filter_by_distance = False
        geo_search = 'start'
        queryset = Load.objects.filter(Q(status=1) & ~Q(start_location=None), removedDateTime=None,)

        # Load.objects.filter(removedDateTime=None~Q(pick_up_date=None)).update(pick_up_date=None)

        # less_15_minutes = datetime.now() - timedelta(minutes=15)
        # queryset = queryset.filter(modifiedDateTime__gte=less_15_minutes)

        if 'filter_type' in get:
            if get['filter_type'] == 'single':
                if 'filter_field' in get:
                    field = get['filter_field']
                    condition = get['condition']
                    value = get['value']

                    if condition == 'equal' or condition == 'more' or condition == 'less' or condition == 'contains':
                        if condition == 'more':
                            field = field + '__gte'
                        elif condition == 'less':
                            field = field + '__lte'
                        elif condition == 'contains':
                            field = field + '__icontains'

                        filtering_dict = {field: value}
                        queryset = queryset.filter(**filtering_dict)

                    elif condition == 'not_equal' :
                        filtering_dict = {field: value}
                        queryset = queryset.filter(~Q(**filtering_dict))
            elif get['filter_type'] == 'multipart':
                for param in get:
                    if hasattr(Load, param):
                        field = param + '__icontains'
                        filtering_dict = {field: get[param]}
                        queryset = queryset.filter(**filtering_dict)

        if hasattr(user, 'company_instance'):
            brokers_blacklist = user.company_instance.brokers_blacklist
            brokers_blacklist_array = brokers_blacklist.split('|')
            queryset = queryset.filter(~Q(reply_email__in=[broker for broker in brokers_blacklist_array]))
        
        if 'order_by' in get:
            order_by = get['order_by']
            if order_by != '':
                if get['order'] == 'DESC':
                    order_by = '-' + order_by
                queryset = queryset.order_by(order_by)

        if 'miles_range' in get:
            standart_radius = int(get['miles_range'])

        if 'geo_search' in get and get['geo_search'] == 'end':
            geo_search = 'end'

        if 'geo' in get:
            filter_by_distance = True

        new_queryset = list()
        if filter_by_distance == True:
            for load in queryset:
                filter_miles = standart_radius
                current_geo = get['geo'].split(',')
                load_geo = None

                if geo_search == 'start':
                    load_geo = load.start_location.split(',')
                elif geo_search == 'end':
                    load_geo = load.end_location.split(',')
                else:
                    continue
                
                distance_between_cur_and_load = round(distance.distance(current_geo, load_geo).miles)

                if distance_between_cur_and_load > filter_miles:
                    continue
                else:
                    if hasattr(user, 'driver_info'):
                        driver_geo = user.driver_info.location.split(',')
                        start_load_geo = load.start_location.split(',')
                        distance_before_load = round(distance.distance(driver_geo, start_load_geo).miles)
                        load.distance_before_load = distance_before_load
                    new_queryset.append(load)
            queryset = new_queryset
            
        page = self.paginate_queryset(queryset)

        if page is not None:
            queryset = page

        serializer = LoadListSerializer(queryset, many=True)
        if page is not None:
            return self.get_paginated_response(serializer.data)
        return Response(serializer.data)

    @method_decorator(cache_page(60*10))
    @method_decorator(vary_on_cookie)
    def get_loads_history(self, request):
        user = request.user
        # user = User.objects.get(id=179)
        if hasattr(user, 'driver_info'):
            driver = user.driver_info
            loads = LoadInHistory.objects.filter(removedDateTime=None, driver=driver, action="Complete")
            total_driver_price = loads.aggregate(sum=Sum('driver_price'))
            queryset = loads
            serializer = LoadInHistorySerializer(queryset, many=True)
            
            return Response({
                'count': loads.count(),
                **total_driver_price,
                'results': serializer.data
            })
        else:
            return Response('Driver not found')
