# from app.models import UserModel
from app.models import *
from rest_framework import serializers
from django.contrib.auth.hashers import make_password
from django.db.models import Q, Sum, F
from datetime import datetime, timedelta
from .helpers.get_user_owner import get_user_owner
from rest_framework.validators import UniqueValidator, UniqueTogetherValidator
import arrow, json
from datetime import datetime




def str_to_date(string):
    return arrow.get(string).datetime
    return datetime.strptime(string, '%Y-%m-%dT%H:%M:%S.%f%z')

def to_first_level(dict):
    output = {}

    for key,value in dict.items():
        if str(type(value)) == "<class 'collections.OrderedDict'>":
            output.update(to_first_level(value))
        else:
            output[key] = value

    return output


class LocationSerializer(serializers.ModelSerializer):
    class Meta:
        model = Location
        fields = '__all__'


class LoadPointSerializer(serializers.ModelSerializer):
    class Meta:
        model = LoadPoint
        fields = '__all__'


class DriversStatusesSerializer(serializers.ModelSerializer):
    class Meta():
        model = DriverStatus
        fields = '__all__'


class CarStatusesSerializer(serializers.ModelSerializer):
    class Meta():
        model = CarStatus
        fields = '__all__'

    
class DriverBonusSerializer(serializers.ModelSerializer):
    class Meta():
        model = DriverBonus
        fields = '__all__'


class DriverFineSerializer(serializers.ModelSerializer):
    class Meta():
        model = DriverFine
        fields = '__all__'


class LoadStatusesSerializer(serializers.ModelSerializer):
    class Meta():
        model = LoadStatus
        fields = '__all__'


class LoadSubStatusesSerializer(serializers.ModelSerializer):
    class Meta():
        model = LoadSubStatus
        fields = '__all__'


class BookkeepingStatusesSerializer(serializers.ModelSerializer):
    class Meta():
        model = BookkeepingStatus
        fields = '__all__'


class DocumentSerializer(serializers.ModelSerializer):
    sender = serializers.HiddenField(default=serializers.CurrentUserDefault())

    class Meta():
        model = Documents
        fields = '__all__'


class FileSerializer(serializers.ModelSerializer):
    sender = serializers.HiddenField(default=serializers.CurrentUserDefault())

    class Meta():
        model = File
        fields = '__all__'


class TutorialCreateSerializer(serializers.ModelSerializer):
    class Meta():
        model = Tutorial
        fields = '__all__'


class TutorialSerializer(serializers.ModelSerializer):
    files = FileSerializer(read_only=True, many=True)

    class Meta():
        model = Tutorial
        fields = '__all__'


class UserSerializer(serializers.ModelSerializer):
    phone_number = serializers.CharField(max_length=20, validators=[ UniqueValidator(queryset=User.objects.all()) ])
    role = serializers.PrimaryKeyRelatedField(read_only=True)
    
    class Meta:
        model = User
        fields = ('id', 'email', 'address', 'first_name', 'last_name', 'phone_number', 'avatar', 'role', 'last_online', 'zip_code', 'fb_token', 'filters_data', 'is_superuser', 'is_online', 'user_device')


class UserSettingsSerializer(serializers.ModelSerializer):
    user = UserSerializer(read_only=True)

    def to_representation(self, instance):
        ret = super().to_representation(instance)

        ret['company_hash'] = str(ret['company_hash'])

        return ret
    
    class Meta:
        model = CompanySettings
        fields = '__all__'


class CompanySerializer(serializers.ModelSerializer):
    # users = serializers.PrimaryKeyRelatedField(read_only=True, many=True)
    # groups = serializers.PrimaryKeyRelatedField(read_only=True, many=True)
    # brokers = serializers.PrimaryKeyRelatedField(read_only=True, many=True)
    # cars = serializers.PrimaryKeyRelatedField(read_only=True, many=True)
    # loads = serializers.PrimaryKeyRelatedField(read_only=True, many=True)
    # tutorials = serializers.PrimaryKeyRelatedField(read_only=True, many=True)
    # chats = serializers.PrimaryKeyRelatedField(read_only=True, many=True)
    # requests = serializers.PrimaryKeyRelatedField(read_only=True, many=True)

    class Meta:
        model = Company
        fields = '__all__'


class UserOnlineSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = ('user_online_log', )


class CargoSerializer(serializers.ModelSerializer):
    class Meta:
        model = Cargo
        fields = '__all__'


class SmallLoadSerializer(serializers.ModelSerializer):
    documents = DocumentSerializer(read_only=True, many=True)
    sys_ref = serializers.CharField(default="", validators=[UniqueValidator(queryset=Load.objects.filter(removedDateTime=None, start_time=None))])
    shipper = serializers.HiddenField(default=User.objects.get(pk=7))
    points = LoadPointSerializer(read_only=True, many=True)

    class Meta:
        model = Load
        fields = '__all__'
        # validators = [
        #     UniqueTogetherValidator(
        #         queryset=Load.objects.filter(start_time=None),
        #         fields=['pickUpAt', 'deliverTo', 'company']
        #     )
        # ]


class GuestLoadSerializer(serializers.ModelSerializer):
    load_locations = LocationSerializer(read_only=True, many=True)
    status = LoadStatusesSerializer(read_only=True)
    substatus = LoadSubStatusesSerializer(read_only=True)
    
    class Meta:
        model = Load
        fields = '__all__'


class LoadSerializer(serializers.ModelSerializer):
    shipper = serializers.HiddenField(default=serializers.CurrentUserDefault())
    cargos = CargoSerializer(read_only=True, many=True)
    # status = LoadStatusesSerializer(read_only=True)
    # substatus = LoadSubStatusesSerializer(read_only=True)
    load_locations = LocationSerializer(read_only=True, many=True)
    points = LoadPointSerializer(read_only=True, many=True)
    documents = DocumentSerializer(read_only=True, many=True)
    load_chat = serializers.PrimaryKeyRelatedField(read_only=True, default=0)
    resp_car = serializers.StringRelatedField(read_only=True)
    load_propositions = serializers.PrimaryKeyRelatedField(read_only=True, many=True)

    def to_representation(self, instance):
        ret = super().to_representation(instance)

        ret['resp_driver_name'] = str(instance.resp_driver)

        return ret
    
    class Meta:
        model = Load
        fields = '__all__'
        

class DriverInfoSerializer(serializers.ModelSerializer):
    user = UserSerializer(read_only=True)
    working_car = serializers.StringRelatedField(read_only=True)
    responsible_user = UserSerializer(read_only=True)
    # saved_loads = LoadInHistorySerializer(read_only=True, many=True)
    driver_loads = SmallLoadSerializer(read_only=True, many=True)
    status = serializers.StringRelatedField()
    
    class Meta:
        model = DriverInfo
        fields = '__all__'


class SmallDriverInfoSerializer(serializers.ModelSerializer):
    user = UserSerializer(read_only=True)
    working_car = serializers.StringRelatedField(read_only=True)
    responsible_user = serializers.PrimaryKeyRelatedField(read_only=True)
    # saved_loads = serializers.PrimaryKeyRelatedField(read_only=True, many=True)
    driver_loads = serializers.PrimaryKeyRelatedField(read_only=True, many=True)
    status = serializers.StringRelatedField()
    
    class Meta:
        model = DriverInfo
        fields = '__all__'


class PropositionListSerializer(serializers.ListSerializer):
    def to_representation(self, data):
        data = data.filter(~Q(status="Decline"))
        return super(PropositionListSerializer, self).to_representation(data)


class PropositionSerializer(serializers.ModelSerializer):
    user = serializers.StringRelatedField(read_only=True)
    load = LoadSerializer(read_only=True)
    driver = SmallDriverInfoSerializer(read_only=True)
    # driver = serializers.PrimaryKeyRelatedField(read_only=True)
    
    class Meta:
        list_serializer_class = PropositionListSerializer
        model = Proposition
        fields = '__all__'


class SmallPropositionSerializer(serializers.ModelSerializer):
    user = serializers.StringRelatedField(read_only=True)
    driver = SmallDriverInfoSerializer(read_only=True)
    
    class Meta:
        model = Proposition
        fields = '__all__'


class LoadStatisticSerializer(serializers.ModelSerializer):
    driver = UserSerializer(read_only=True)

    def to_representation(self, instance):
        ret = super().to_representation(instance)

        if ret['start_time'] != None:
            if ret['finish_time'] == None:
                ret['process_duration'] = round((datetime.now(timezone.utc) - str_to_date(ret['start_time'])).total_seconds())
            else:
                ret['process_duration'] = round((str_to_date(ret['finish_time']) - str_to_date(ret['start_time'])).total_seconds())
        else:
            ret['process_duration'] = None

        return ret
    
    class Meta:
        model = Load
        fields = ('id', 'start_time', 'finish_time', 'driver')


class LoadInHistorySerializer(serializers.ModelSerializer):
    load = SmallLoadSerializer(read_only=True)
    driver = SmallDriverInfoSerializer(read_only=True)

    class Meta:
        model = LoadInHistory
        fields = '__all__'


class CarSerializer(serializers.ModelSerializer):
    dispatcher = UserSerializer(read_only=True)
    drivers = SmallDriverInfoSerializer(read_only=True, many=True)
    active_driver = SmallDriverInfoSerializer(read_only=True)
    car_propositions = serializers.SerializerMethodField() 
    car_owner = serializers.PrimaryKeyRelatedField(read_only=True)
    car_creator = serializers.PrimaryKeyRelatedField(read_only=True)
    miles_out = serializers.IntegerField(default=0)
    bid = serializers.FloatField(default=0)
    status = CarStatusesSerializer(read_only=True)
    load = serializers.PrimaryKeyRelatedField(read_only=True)
    eta = serializers.CharField(default='', read_only=True)

    def get_car_propositions(self, obj):
        props = Proposition.objects.filter(car=obj, removedDateTime=None)
        return SmallPropositionSerializer(props, read_only=True, many=True).data

    class Meta:
        model = Car
        fields = '__all__'


class OwnerSerializer(serializers.ModelSerializer):
    user = UserSerializer(read_only=True)
    drivers = SmallDriverInfoSerializer(read_only=True, many=True)
    owner_cars = CarSerializer(read_only=True, many=True)
    
    class Meta:
        model = CarOwner
        fields = '__all__'
        related_fields = ['user']

    def update(self, instance, validated_data):
        request = self.context.get('request').data
        for related_obj_name in self.Meta.related_fields:
            if not related_obj_name in request:
                continue
            related_instance = getattr(instance, related_obj_name)
            data = request[related_obj_name]
            update_fields = list()
            
            for attr_name, value in data.items():
                update_fields.append(str(attr_name))
                setattr(related_instance, attr_name, value)
            related_instance.save(update_fields=update_fields)
        return super().update(instance, validated_data)


class UserDetailSerializer(serializers.ModelSerializer):
    added_by = UserSerializer(read_only=True)
    company_info = serializers.SerializerMethodField() 
    driver_info = DriverInfoSerializer(read_only=True)
    owner_info = OwnerSerializer(read_only=True)
    phone_number = serializers.CharField(max_length=20, validators=[ UniqueValidator(queryset=User.objects.all()) ])

    def get_company_info(self, obj):
        if obj.company_instance != None:
            return CompanySerializer(obj.company_instance, read_only=True).data
        else:
            return None

    def to_representation(self, instance):
        ret = super().to_representation(instance)

        if ret['user_online_log']:
            online_log = json.loads(ret['user_online_log'])

            ret['last_online'] = datetime.utcfromtimestamp(online_log[-1]).strftime('%Y-%m-%d %H:%M:%S')
            
        del ret['user_online_log']

        ret['in_gmail'] = False

        id = instance.id
        if instance.id == 108 or instance.id == 199:
            id = 7

        if os.path.exists('tokens/token_' + str(id) + '.pickle'):
            ret['in_gmail'] = True

        if ret['company_info'] != None:
            ret['company_info']['company_hash'] = str(ret['company_info']['company_hash'])

        return ret

    class Meta:
        model = User
        exclude  = ('password', 'groups', 'user_permissions')


class PropositionSerializerForCarriersDashboard(serializers.ModelSerializer):
    class Meta:
        model = Proposition
        fields = ('status', 'price')


class UserSerializerForCarriersDashboard(serializers.ModelSerializer):
    user_propositions = PropositionSerializerForCarriersDashboard(read_only=True, many=True)
    
    def to_representation(self, instance):
        ret = super().to_representation(instance)
        ret['props_count'] = len(ret['user_propositions'])
        ret['full_name'] = ret['first_name'] + ' ' + ret['last_name']

        return ret
    
    class Meta:
        model = User
        fields = fields = ('id', 'email', 'address', 'first_name', 'last_name', 'user_propositions', 'last_online', 'avatar', 'is_online')


class MessageSerializer(serializers.ModelSerializer):
    chat_group = serializers.HiddenField(default=1)
    user_from = serializers.SerializerMethodField() 
    user_to = serializers.SerializerMethodField()
    
    def get_user_from(self, obj):
        if self.context.get('request').user == obj.user_from:
            return 'self'
        else:
            return obj.user_from.id

    def get_user_to(self, obj):
        if self.context.get('request').user == obj.user_to:
            return 'self'
        else:
            return obj.user_to.id

    class Meta:
        model = Message
        fields = '__all__'


class ChatGroupMessageSerializer(serializers.ModelSerializer):
    chat_group = serializers.HiddenField(default=1)
    user_from = UserSerializer(read_only=True) 
    user_to = UserSerializer(read_only=True)

    class Meta:
        model = Message
        fields = '__all__'


class NoticeSerializer(serializers.ModelSerializer):
    user_to = serializers.StringRelatedField(read_only=True)
    
    class Meta:
        model = Notice
        fields = '__all__'


class UserCreateSerializer(serializers.ModelSerializer):
    phone_number = serializers.CharField(max_length=20, validators=[UniqueValidator(queryset=User.objects.all())])
    
    def validate_password(self, value: str) -> str:
        return make_password(value)
        
    class Meta:
        model = User
        fields = '__all__'


class ChatGroupsSerializer(serializers.ModelSerializer):
    chat_group_messages = serializers.SerializerMethodField() 
    user_member = serializers.SerializerMethodField() 
    user_initiator = serializers.SerializerMethodField()

    def get_chat_group_messages(self, obj):
        return ChatGroupMessageSerializer(Message.objects.filter(chat_group=obj).first(), read_only=True).data

    def get_user_initiator(self, obj):
        if self.context.get('request').user == obj.user_initiator:
            return 'self'
        else:
            return UserSerializer(User.objects.get(pk=obj.user_initiator.id), read_only=True).data

    def get_user_member(self, obj):
        if self.context.get('request').user == obj.user_member:
            return 'self'
        else:
            return UserSerializer(User.objects.get(pk=obj.user_member.id), read_only=True).data

    
    
    class Meta:
        model = ChatGroup
        fields = '__all__'


class ChatSerializer(serializers.ModelSerializer):
    # chat_group_messages = ChatGroupMessageSerializer(read_only=True, many=True) 
    pages_count = serializers.SerializerMethodField() 
    chat_group_messages = serializers.SerializerMethodField() 
    user_member = serializers.SerializerMethodField() 
    user_initiator = serializers.SerializerMethodField()

    def get_user_initiator(self, obj):
        if self.context.get('request').user == obj.user_initiator:
            return 'self'
        else:
            return UserSerializer(User.objects.get(pk=obj.user_initiator.id), read_only=True).data

    def get_user_member(self, obj):
        if self.context.get('request').user == obj.user_member:
            return 'self'
        else:
            return UserSerializer(User.objects.get(pk=obj.user_member.id), read_only=True).data

    def get_chat_group_messages(self, obj):
        page = 1
        limit = 50
        get = self.context.get('request').query_params
        
        if 'page' in get and get['page'] != '':
            page = int(get['page'])

        if 'limit' in get and get['limit'] != '':
            limit = int(get['limit'])

        from_item = (page - 1) * limit
        to_item = page * limit
    
        return ChatGroupMessageSerializer(Message.objects.filter(chat_group=obj)[from_item:to_item], read_only=True, many=True).data

    def get_pages_count(self, obj):
        limit = 50
        get = self.context.get('request').query_params
        mess_count = Message.objects.filter(chat_group=obj).count()

        if 'limit' in get and get['limit'] != '':
            limit = int(get['limit'])

        return round(mess_count/limit)


    class Meta:
        model = ChatGroup
        fields = '__all__'


class ChatMessageSerializer(serializers.ModelSerializer):
    user_from = UserSerializer(read_only=True)
    files = FileSerializer(read_only=True, many=True)

    class Meta:
        model = ChatMessage
        fields = '__all__'


class UserChatsSerializer(serializers.ModelSerializer):
    last_message = serializers.SerializerMethodField()
    users = UserSerializer(many=True, read_only=True)
    load = serializers.PrimaryKeyRelatedField(read_only=True)
    unread_count = serializers.SerializerMethodField()
    
    def get_last_message(self, obj):
        return ChatMessageSerializer(ChatMessage.objects.filter(chat_group=obj).first(), read_only=True).data

    def get_unread_count(self, obj):
        if self.context.get('request') != None:
            user = self.context.get('request').user
            return ChatMessage.objects.filter(chat_group=obj).exclude(users_read=user).count()
        else:
            return 0

    class Meta:
        model = Chat
        fields = '__all__'


class ChatWithMessagesSerializer(serializers.ModelSerializer):
    chat_group_messages = serializers.SerializerMethodField()
    pages_count = serializers.SerializerMethodField() 
    users = UserSerializer(many=True, read_only=True)
    load = serializers.PrimaryKeyRelatedField(read_only=True)

    def get_chat_group_messages(self, obj):
        page = 1
        limit = 50
        request = self.context.get('request')
        
        if request != None and hasattr(request, 'query_params'):
            if 'page' in request.query_params:
                page = int(request.query_params['page'])

            if 'limit' in request.query_params:
                limit = int(request.query_params['limit'])

        from_item = (page - 1) * limit
        to_item = page * limit
        messages = ChatMessage.objects.filter(chat_group=obj)[from_item:to_item]
    
        return ChatMessageSerializer(messages, read_only=True, many=True).data


    def get_pages_count(self, obj):
        limit = 50
        get = self.context.get('request').query_params
        mess_count = ChatMessage.objects.filter(chat_group=obj).count()

        if 'limit' in get and get['limit'] != '':
            limit = int(get['limit'])

        return round(mess_count/limit)

    class Meta:
        model = Chat
        fields = '__all__'


class UserListSerializer(serializers.ModelSerializer):
    user_owner = serializers.PrimaryKeyRelatedField(read_only=True)
    my_working_group = serializers.PrimaryKeyRelatedField(read_only=True)
    # shipper_loads = serializers.PrimaryKeyRelatedField(many=True, read_only=True)
    # user_workers = UserSerializer(read_only=True, many=True)
    # user_notices = NoticeSerializer(read_only=True, many=True)

    # chat_groups_initiator = ChatGroupsSerializer(read_only=True, many=True)
    # chat_groups_member = ChatGroupsSerializer(read_only=True, many=True)

    class Meta:
        model = User
        exclude  = ('password', 'user_online_log', 'groups', 'user_permissions', 'private_email_password', 'private_email_domain', 'private_email_port', 'private_email_imap_domain', 'private_email_imap_port')


class DispatcherSerializer(serializers.ModelSerializer):
    role = serializers.HiddenField(default=UserRole.objects.get(id=5))
    phone_number = serializers.CharField(max_length=20, validators=[ UniqueValidator(queryset=User.objects.all()) ])

    def validate_password(self, value: str) -> str:
        return make_password(value)

    def to_representation(self, instance):
        ret = super().to_representation(instance)
        del ret['password']
        return ret

    class Meta:
        model = User
        fields = ('email', 'password', 'first_name', 'last_name', 'role', 'phone_number', 'is_online')


class DispatchersStatsSerializer(serializers.ModelSerializer):
    def to_representation(self, instance):
        ret = super().to_representation(instance)

        posted_loads = self.context.get('posted_loads').filter(resp_carrier_dispatcher=instance.pk)
        actual_loads = self.context.get('actual_loads').filter(resp_carrier_dispatcher=instance.pk)
        bids = self.context.get('bids').filter(user=instance.pk)

        date_filter = self.context.get('date_filter')
        revenue = posted_loads.filter(**date_filter).aggregate(revenue=Sum(F('broker_price') - F('driver_price')))
        gross = posted_loads.filter(**date_filter).aggregate(gross=Sum('broker_price'))

        percent = 0
        if gross['gross'] != None and revenue['revenue'] != None:
            percent = round(gross['gross'] / revenue['revenue'], 2)

        ret['stat'] = {
            'bids': bids.filter(**date_filter).count(),
            'current_loads': actual_loads.filter(**date_filter).count(),
            'revenue': revenue['revenue'] or 0,
            'percent': percent
        }

        return ret

    class Meta:
        fields = ('id', 'email', 'first_name', 'last_name', 'phone_number', 'is_online')
        model = User


class CarCreateSerializer(serializers.ModelSerializer):
    car_creator = serializers.HiddenField(default=serializers.CurrentUserDefault())
    # vin = serializers.CharField(max_length=200, validators=[ UniqueValidator(queryset=Car.objects.all()) ])
    # drivers = serializers.RelatedField(many=True, read_only=True, required=False)

    class Meta:
        model = Car
        fields = '__all__'


class CarStatsSerializer(serializers.ModelSerializer):
    def to_representation(self, instance):
        ret = super().to_representation(instance)

        actual_loads = self.context.get('actual_loads').filter(resp_car=instance.pk)
        bids = self.context.get('bids').filter(user=instance.pk)

        date_filter = self.context.get('date_filter')
        revenue = actual_loads.filter(**date_filter).aggregate(revenue=Sum(F('broker_price') - F('driver_price')))
        gross = actual_loads.filter(**date_filter).aggregate(gross=Sum('broker_price'))

        percent = 0
        if gross['gross'] != None and revenue['revenue'] != None and revenue['revenue'] != 0:
            percent = round(gross['gross'] / revenue['revenue'], 2)

        driver = instance.active_driver.user
        ret['driver'] = driver.first_name + ' ' + driver.last_name

        ret['stat'] = {
            'current_loads': actual_loads.filter(**date_filter).count(),
            'gross': gross['gross'] or 0,
            'revenue': revenue['revenue'] or 0,
            'percent': percent
        }

        return ret

    class Meta:
        fields = ('id', 'number',)
        model = Car


class LoadListSerializer(serializers.ModelSerializer):
    shipper = serializers.StringRelatedField(read_only=True)
    already_saw = serializers.BooleanField(default=False)
    bids_count = serializers.IntegerField(default=0)
    miles_out = serializers.IntegerField(default=0)
    actual_cars_count = serializers.IntegerField(default=0)
    holded_cars_count = serializers.IntegerField(default=0)
    distance_before_load = serializers.IntegerField(default=0)
    resp_driver = SmallDriverInfoSerializer(read_only=True)
    resp_car = CarCreateSerializer(read_only=True)
    saved_in_history = serializers.PrimaryKeyRelatedField(read_only=True, many=True)
    points = LoadPointSerializer(read_only=True, many=True)
    load_propositions = SmallPropositionSerializer(many=True, read_only=True)
    
    status = LoadStatusesSerializer(read_only=True)
    substatus = LoadSubStatusesSerializer(read_only=True)
    
    class Meta:
        model = Load
        exclude = ('users_saw', )


class UserActionSerializer(serializers.ModelSerializer):
    user = serializers.StringRelatedField(read_only=True)
    
    class Meta:
        model = UserAction
        fields = '__all__'


class CarDriverSerializer(serializers.ModelSerializer):
    driver_info = DriverInfoSerializer(read_only=True)
    role = serializers.PrimaryKeyRelatedField(read_only=True)

    class Meta:
        model = User
        fields = ('id', 'email', 'first_name', 'last_name', 'role', 'phone_number', 'zip_code', 'address', 'driver_info', 'is_online', )


class UserCarOwnerSerializer(serializers.ModelSerializer):
    phone_number = serializers.CharField(max_length=20, validators=[UniqueValidator(queryset=User.objects.all())])
    
    class Meta:
        model = User
        fields = ('id', 'email', 'first_name', 'last_name', 'address', 'zip_code', 'emergency_phone', 'phone_number', 'is_online')


class CarOwnerSerializer(serializers.ModelSerializer):
    role = serializers.HiddenField(default=UserRole.objects.get(id=10))
    added_by = serializers.HiddenField(default=serializers.CurrentUserDefault())
    password = serializers.HiddenField(default='password')
    owner_info = OwnerSerializer(read_only=True)
    working_group = serializers.PrimaryKeyRelatedField(read_only=True)
    phone_number = serializers.CharField(max_length=20, validators=[ UniqueValidator(queryset=User.objects.all()) ])

    def validate_password(self, value: str) -> str:
        return make_password(value)

    def to_representation(self, instance):
        ret = super().to_representation(instance)
        new_ret = to_first_level(ret)
        return new_ret
    
    class Meta:
        model = User
        fields = ('id', 'email', 'first_name', 'last_name', 'added_by', 'working_group', 'address', 'zip_code', 'emergency_phone', 'role', 'phone_number', 'password', 'owner_info', 'is_online')


class EmailSerializer(serializers.ModelSerializer):
    user_from = serializers.HiddenField(default=serializers.CurrentUserDefault())

    class Meta:
        model = Email
        fields = '__all__'


class TwilioMessageSerializer(serializers.ModelSerializer):
    user_from = serializers.PrimaryKeyRelatedField(read_only=True)
    user_to = serializers.PrimaryKeyRelatedField(read_only=True)
    broker_from = serializers.PrimaryKeyRelatedField(read_only=True)
    broker_to = serializers.PrimaryKeyRelatedField(read_only=True)

    class Meta:
        model = TwilioMessage
        fields = ('id', 'content', 'modifiedDateTime', 'toNumber', 'fromNumber', 'status', 'user_from', 'user_to', 'broker_from', 'broker_to', 'media')


class TwilioRecieveMessageSerializer(serializers.ModelSerializer):
    user_from = serializers.PrimaryKeyRelatedField(read_only=True)
    user_to = serializers.PrimaryKeyRelatedField(read_only=True)
    broker_from = serializers.PrimaryKeyRelatedField(read_only=True)
    broker_to = serializers.PrimaryKeyRelatedField(read_only=True)

    class Meta:
        model = TwilioMessage
        fields = ('id', 'content', 'modifiedDateTime', 'toNumber', 'fromNumber', 'status', 'user_from', 'user_to', 'broker_from', 'broker_to', 'media')


class BrokersSerializer(serializers.ModelSerializer):
    last_message = serializers.SerializerMethodField()
    unread_count = serializers.IntegerField(default=0)

    def get_last_message(self, obj):
        return TwilioMessageSerializer(TwilioMessage.objects.filter(Q(fromNumber=obj.phone_number) | Q(toNumber=obj.phone_number)).last(), read_only=True).data

    def get_unread(self, obj):
        if TwilioMessage.objects.filter(fromNumber=obj.phone_number, status="Send").exists():
            return True
        else:
            return False

    def get_unread_count(self, obj):
        return TwilioMessage.objects.filter(fromNumber=obj.phone_number, status="Send").count()

    class Meta:
        fields = '__all__'
        model = Broker


class BrokersStatsSerializer(serializers.ModelSerializer):
    def to_representation(self, instance):
        ret = super().to_representation(instance)

        posted_loads = self.context.get('posted_loads').filter(company=ret['name'])
        actual_loads = self.context.get('actual_loads').filter(company=ret['name'])
        date_filter = self.context.get('date_filter')
        revenue = posted_loads.filter(**date_filter).aggregate(revenue=Sum(F('broker_price') - F('driver_price')))
        gross = posted_loads.filter(**date_filter).aggregate(gross=Sum('broker_price'))

        percent = 0
        if gross['gross'] != None and revenue['revenue'] != None:
            if gross['gross'] > 0 and revenue['revenue'] > 0:
                percent = round(gross['gross'] / revenue['revenue'], 2)

        ret['stat'] = {
            'posted_loads': posted_loads.count(),
            'current_loads': actual_loads.count(),
            'revenue': revenue['revenue'] or 0,
            'percent': percent
        }

        return ret

    class Meta:
        fields = '__all__'
        model = BrokerCompany


class DriverSerializer(serializers.ModelSerializer):
    role = serializers.HiddenField(default=UserRole.objects.get(id=10))
    user_owner = serializers.HiddenField(default=serializers.CurrentUserDefault())
    added_by = serializers.HiddenField(default=serializers.CurrentUserDefault())
    driver_info = DriverInfoSerializer(read_only=True)
    last_message = serializers.SerializerMethodField()
    car = CarSerializer(read_only=True, many=True)
    working_group = serializers.PrimaryKeyRelatedField(read_only=True)
    password = serializers.HiddenField(default='password')
    phone_number = serializers.CharField(max_length=20, validators=[ UniqueValidator(queryset=User.objects.all()) ])
    unread_count = serializers.IntegerField(default=0)
    last_message_id = serializers.IntegerField(default=0)
    chat = serializers.PrimaryKeyRelatedField(read_only=True)

    def get_last_message(self, obj):
        return TwilioMessageSerializer(TwilioMessage.objects.filter(Q(fromNumber=obj.phone_number) | Q(toNumber=obj.phone_number)).last(), read_only=True).data

    def validate_password(self, value: str) -> str:
        return make_password(value)


    class Meta:
        model = User
        fields = ('id', 'car', 'chat', 'email', 'first_name', 'last_name', 'added_by', 'role', 'user_owner', 'working_group', 'phone_number', 'zip_code', 'last_message_id', 'last_message', 'unread_count', 'password', 'address', 'emergency_phone', 'license_expiration_date', 'drive_license', 'driver_info', 'is_online', 'company_instance')


class DriverCreateSerializer(serializers.ModelSerializer):
    role = serializers.HiddenField(default=UserRole.objects.get(id=10))
    user_owner = serializers.HiddenField(default=serializers.CurrentUserDefault())
    added_by = serializers.HiddenField(default=serializers.CurrentUserDefault())
    password = serializers.HiddenField(default='password')
    phone_number = serializers.CharField(max_length=20, validators=[ UniqueValidator(queryset=User.objects.all()) ])

    def validate_password(self, value: str) -> str:
        return make_password(value)

    class Meta:
        model = User
        fields = ('id', 'email', 'first_name', 'last_name', 'added_by', 'role', 'user_owner', 'working_group', 'phone_number', 'zip_code', 'password', 'address', 'emergency_phone', 'license_expiration_date', 'drive_license', 'company_instance')


class DriverChatSerializer(serializers.ModelSerializer):
    # twilio_to_messages = TwilioMessageSerializer(read_only=True, many=True)
    messages = serializers.SerializerMethodField()

    def get_messages(self, obj):
        return TwilioMessageSerializer(TwilioMessage.objects.filter(Q(toNumber=obj.phone_number) | Q(fromNumber=obj.phone_number)), read_only=True, many=True).data

    class Meta:
        model = User
        depth = 1
        fields = ('id', 'email', 'first_name', 'last_name', 'phone_number', 'messages', 'avatar', 'is_online')


class BrokerChatSerializer(serializers.ModelSerializer):
    messages = serializers.SerializerMethodField()

    def get_messages(self, obj):
        return TwilioMessageSerializer(TwilioMessage.objects.filter(Q(broker_to=obj.id) | Q(broker_from=obj.id)), read_only=True, many=True).data

    class Meta:
        fields = '__all__'
        model = Broker


class RegistrationRequestSerializer(serializers.ModelSerializer):
    new_user = UserSerializer(read_only=True)

    class Meta():
        model = RegistrationRequest
        fields = '__all__'


class WorkingGroupSerializer(serializers.ModelSerializer):
    users = UserSerializer(read_only=True, many=True)
    group_lead = UserSerializer(read_only=True)

    class Meta():
        model = WorkingGroup
        fields = '__all__'


class CallSerializer(serializers.ModelSerializer):
    author = UserSerializer(read_only=True)

    class Meta:
        model = Call
        fields = '__all__'


class ChangePasswordSerializer(serializers.Serializer):
    model = User

    old_password = serializers.CharField(required=True)
    new_password_1 = serializers.CharField(required=True)
    new_password_2 = serializers.CharField(required=True)


class SmallPageSerializer(serializers.ModelSerializer):
    class Meta:
        model = Page
        fields = '__all__'


class PageSerializer(serializers.ModelSerializer):
    childrens = serializers.SerializerMethodField() 

    def get_childrens(self, obj):
        request = self.context.get('request')
        user = request.user
        # allowed_pages = user.role.pages_set.all()
        
        if obj.has_childrens:
            return SmallPageSerializer(user.role.page_set.filter(parent_page=obj.id), many=True).data
        else:
            return None

    class Meta:
        model = Page
        fields = '__all__'


class UserRoleSerializer(serializers.ModelSerializer):
    permission_set = serializers.PrimaryKeyRelatedField(read_only=True, many=True)
    page_set = serializers.PrimaryKeyRelatedField(read_only=True, many=True)

    class Meta:
        model = UserRole
        fields = '__all__'


class SavedLoadSerializer(serializers.ModelSerializer):
    class Meta:
        model = SavedLoad
        fields = '__all__'



