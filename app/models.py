import os, requests, json, hashlib, re
from pathlib import Path

from django.contrib.auth.models import AbstractUser
from django.db import models
from django.utils import timezone
from django.dispatch import receiver
from django.db.models.signals import pre_delete
from django.db.models import Q, UniqueConstraint

from rest_framework.response import Response

from app.helpers.image import resize_image
from app.helpers.data_filters import phone_filter
from app.managers import CustomUserManager

from api import settings
from .helpers.data_filters import separate_location

from PIL import Image


def user_directory_path(instance, filepath):
    return 'avatars/user_{0}/{1}'.format(instance.id, filepath)

def chat_directory_path(instance, filepath):
    return 'chats/{0}'.format(filepath)

def user_company_logo_path(instance, filepath):
    return 'companies/user_{0}/{1}'.format(instance.pk, filepath)


class CompanyType(models.Model):
    name = models.CharField(max_length=100, default="")


class Company(models.Model):
    name = models.CharField(max_length=100, default="")
    logo = models.ImageField(upload_to=user_company_logo_path, null=True, blank=True)
    address = models.CharField(max_length=200, default="None")
    phone =  models.CharField(max_length=20, blank=True, null=True)
    billing_preferences = models.TextField(blank=True, null=True, default="None")

    brokers_blacklist = models.TextField(default="")
    companies_blacklist = models.TextField(default="")
    email_template = models.TextField(default="")
    sms_template = models.TextField(default="")
    tutorial = models.TextField(default="")

    twilio_account_sid = models.CharField(max_length=200, default="")
    twilio_auth_token = models.CharField(max_length=200, default="")
    twilio_messaging_service_sid = models.CharField(max_length=200, default="")

    parsing_email = models.CharField(max_length=200, default="", blank=True)
    parsing_password = models.CharField(max_length=200, default="", blank=True)
    parsing_domain = models.CharField(max_length=200, default="", blank=True)
    parsing_port = models.SmallIntegerField(default=0)

    company_mail_adress = models.CharField(max_length=50, default="", blank=True)
    company_mail_password = models.CharField(max_length=50, default="", blank=True)
    company_mail_host = models.CharField(max_length=50, default="", blank=True)
    company_mail_port = models.SmallIntegerField(default=25, blank=True)

    company_hash = models.BigIntegerField(blank=True, null=True, unique=True)
    company_type = models.ForeignKey(CompanyType, null=True, blank=True, related_name='companies', on_delete=models.SET_NULL)
    
    def save(self, *args, **kwargs):
        super(Company, self).save(*args, **kwargs)

        if self.logo:
            filepath = self.logo.path
            width = self.logo.width
            height = self.logo.height

            min_size = min(width, height)

            if min_size > 300:
                image = Image.open(filepath)
                image = image.resize(
                    (round(width / min_size * 300),
                    round(height / min_size * 300)),
                    Image.ANTIALIAS
                )
                image.save(filepath)


class WorkingGroup(models.Model):
    group_name = models.CharField(max_length=50, default="None")
    color = models.CharField(max_length=7, default="#fff")
    company_id = models.IntegerField(default=0, blank=True)
    company_instance = models.ForeignKey(Company, null=True, blank=True, related_name='groups', on_delete=models.SET_NULL)

    class Meta:
        ordering = ['id']
        indexes = [
            models.Index(fields=['group_name', 'company_id']),
            models.Index(fields=['company_instance']),
            models.Index(fields=['group_name'])
        ]


class DriverStatus(models.Model):
    name = models.CharField(max_length=50, null=True, unique=True)

    def __str__(self):
        return self.name

    
class CarStatus(models.Model):
    name = models.CharField(max_length=50, null=True, unique=True)

    def __str__(self):
        return self.name


class DriverBonus(models.Model):
    name = models.CharField(max_length=200, blank=True, null=True)
    value = models.PositiveIntegerField(default=0)
    company_instance = models.ForeignKey(Company, null=True, blank=True, related_name='driver_bonuses', on_delete=models.SET_NULL)


class DriverFine(models.Model):
    name = models.CharField(max_length=200, blank=True, null=True)
    value = models.PositiveIntegerField(default=0)
    company_instance = models.ForeignKey(Company, null=True, blank=True, related_name='driver_fines', on_delete=models.SET_NULL)


class LoadStatus(models.Model):
    name = models.CharField(max_length=50, null=True, unique=True)

    def __str__(self):
        return self.name

    
class LoadSubStatus(models.Model):
    name = models.CharField(max_length=50, null=True, unique=True)

    def __str__(self):
        return self.name


class BookkeepingStatus(models.Model):
    name = models.CharField(max_length=50, null=True, unique=True)

    def __str__(self):
        return self.name


class UserRole(models.Model):
    name = models.CharField(max_length=50, blank=True, default="")
    company_type = models.ForeignKey(CompanyType, null=True, blank=True, related_name='roles', on_delete=models.SET_NULL)
    company_instance = models.ForeignKey(Company, null=True, blank=True, related_name='roles', on_delete=models.SET_NULL)


class Permission(models.Model):
    action = models.CharField(max_length=50, blank=True, default="")
    role = models.ManyToManyField(UserRole)


class Page(models.Model):
    modifiedDateTime = models.DateTimeField(auto_now=True)
    removedDateTime = models.DateTimeField(blank=True, null=True)
    name = models.CharField(max_length=50, blank=True, default="Page")
    url = models.CharField(max_length=100, blank=True, default="/")
    icon = models.CharField(max_length=50, blank=True, default="")
    icon_alt = models.CharField(max_length=50, blank=True, null=True)
    has_childrens = models.BooleanField(default=False)

    parent_page = models.ForeignKey('self', null=True, blank=True, related_name='child_pages', on_delete=models.SET_NULL)
    role = models.ManyToManyField(UserRole)


class User(AbstractUser):
    is_authenticated = True
    username = None
    email = models.EmailField(unique=True)

    working_gmail = models.EmailField(blank=True, null=True)
    is_online = models.BooleanField(default=False)

    modifiedDateTime = models.DateTimeField(auto_now=True)
    removedDateTime = models.DateTimeField(blank=True, null=True)
    address = models.CharField(max_length=200, blank=True, default="")
    department = models.CharField(max_length=20, default="User")
    phone_number = models.CharField(max_length=20, blank=True, null=True)
    avatar = models.ImageField(upload_to=user_directory_path, null=True, blank=True)
    last_online = models.DateTimeField(blank=True, null=True)
    credit_card = models.CharField(max_length=30, default="", null=True, blank=True)

    filters_data = models.TextField(blank=True, null=True, default="")

    unit_note = models.TextField(default="", blank=True, null=True)
    fb_token = models.CharField(max_length=200, default="", null=True, blank=True)

    working_group = models.ForeignKey(WorkingGroup, on_delete=models.SET_NULL, related_name='users', null=True)
    my_working_group = models.OneToOneField(WorkingGroup, on_delete=models.SET_NULL, related_name='group_lead', null=True)

    #dispatchers
    parent_department = models.CharField(max_length=20, default="None")
    user_owner = models.ForeignKey('self', null=True, blank=True, related_name='user_workers', on_delete=models.CASCADE)
    added_by = models.ForeignKey('self', null=True, blank=True, related_name='added_users', on_delete=models.SET_NULL)
    responsible_user = models.ForeignKey('self', null=True, blank=True, related_name='workers', on_delete=models.SET_NULL)

    # driver
    zip_code = models.CharField(max_length=20, default="", null=True, blank=True)
    license_expiration_date = models.IntegerField(default=0, blank=True, null=True)
    drive_license = models.TextField(default="", blank=True, null=True)
    emergency_name = models.CharField(max_length=200, blank=True, default="", null=True)
    emergency_phone = models.CharField(max_length=20, blank=True, default="", null=True)
    user_device = models.CharField(max_length=20, blank=True, default="", null=True)

    private_email_password = models.CharField(max_length=50, blank=True, null=True)
    private_email_domain = models.CharField(max_length=50, blank=True, null=True)
    private_email_port = models.SmallIntegerField(default=25, blank=True)
    private_email_imap_domain = models.CharField(max_length=50, blank=True, null=True)
    private_email_imap_port = models.SmallIntegerField(default=993, blank=True)

    company_instance = models.ForeignKey(Company, null=True, blank=True, related_name='users', on_delete=models.SET_NULL)
    role = models.ForeignKey(UserRole, null=True, blank=True, related_name='users', on_delete=models.SET_NULL)

    user_online_log = models.TextField(blank=True, null=True, default="")

    USERNAME_FIELD = 'email'
    REQUIRED_FIELDS = []

    objects = CustomUserManager()

    def save(self, *args, **kwargs):
        self.phone_number = phone_filter(self.phone_number)
        super(User, self).save(*args, **kwargs)

        if self.avatar:
            filepath = self.avatar.path
            width = self.avatar.width
            height = self.avatar.height

            min_size = min(width, height)

            if min_size > 300:
                image = Image.open(filepath)
                image = image.resize(
                    (round(width / min_size * 300),
                    round(height / min_size * 300)),
                    Image.ANTIALIAS
                )
                image.save(filepath)

    # def is_authenticated(self):
    #     return True

    def __str__(self):
        return self.email

    class Meta:
        ordering = ['modifiedDateTime']
        indexes = [
            models.Index(fields=['company_instance']),
            models.Index(fields=['phone_number']),
            models.Index(fields=['user_owner', 'working_group']),
            models.Index(fields=['role']),
            models.Index(fields=['working_group'])
        ]


class CarOwner(models.Model):
    applicant_name = models.CharField(max_length=100, blank=True, null=True)
    ssn = models.CharField(max_length=60, blank=True, null=True)
    city = models.CharField(max_length=60, blank=True, null=True)
    state = models.CharField(max_length=60, blank=True, null=True)
    tax_classification = models.CharField(max_length=60, blank=True, null=True)
    sub_tax_classification = models.CharField(max_length=60, blank=True, null=True)
    other_description = models.TextField(blank=True, null=True)
    routing_number = models.CharField(max_length=60, blank=True, null=True)
    accounting_number = models.CharField(max_length=60, blank=True, null=True)
    bank_name = models.CharField(max_length=60, blank=True, null=True)
    company_street_address = models.CharField(max_length=60, blank=True, null=True)
    company_city_state = models.CharField(max_length=60, blank=True, null=True)
    company_name = models.CharField(max_length=60, blank=True, null=True)
    
    user = models.OneToOneField(User, primary_key=True, on_delete=models.CASCADE, related_name='owner_info')


class DriverInfo(models.Model):
    is_enable = models.BooleanField(default=True)
    available_time = models.DateTimeField(blank=True, null=True)
    app_activity_time = models.DateTimeField(blank=True, null=True)
    in_app = models.BooleanField(default=False)
    location = models.CharField(max_length=60, blank=True, null=True)
    unique_sms_key = models.CharField(max_length=20, blank=True, null=True)
    user = models.OneToOneField(User, on_delete=models.CASCADE, primary_key=True, related_name='driver_info')

    status = models.ForeignKey(DriverStatus, default=1, related_name='drivers_in_status', on_delete=models.SET_DEFAULT)
    owner = models.ForeignKey(CarOwner, on_delete=models.SET_NULL, related_name='drivers', null=True)
    responsible_user = models.ForeignKey(User, on_delete=models.SET_NULL, related_name='my_drivers', null=True)

    def __str__(self):
        return self.user.first_name + ' ' + self.user.last_name

    class Meta:
        indexes = [
            models.Index(fields=['status']),
            models.Index(fields=['owner'])
        ]


class CompanySettings(models.Model):
    company = models.CharField(max_length=200, default="None")
    company_logo = models.ImageField(upload_to=user_company_logo_path, null=True, blank=True)
    company_address = models.CharField(max_length=200, default="None")
    company_phone =  models.CharField(max_length=20, blank=True, null=True)
    billing_preferences = models.TextField(blank=True, null=True, default="None")

    brokers_blacklist = models.TextField(default="")
    companies_blacklist = models.TextField(default="")
    email_template = models.TextField(default="")
    sms_template = models.TextField(default="")
    tutorial = models.TextField(default="")

    twilio_account_sid = models.CharField(max_length=200, default="")
    twilio_auth_token = models.CharField(max_length=200, default="")
    twilio_messaging_service_sid = models.CharField(max_length=200, default="")

    parsing_email = models.CharField(max_length=200, default="", blank=True)
    parsing_password = models.CharField(max_length=200, default="", blank=True)
    parsing_domain = models.CharField(max_length=200, default="", blank=True)
    parsing_port = models.SmallIntegerField(default=0)

    company_mail_adress = models.CharField(max_length=50, default="", blank=True)
    company_mail_password = models.CharField(max_length=50, default="", blank=True)
    company_mail_host = models.CharField(max_length=50, default="", blank=True)
    company_mail_port = models.SmallIntegerField(default=25, blank=True)

    company_hash = models.BigIntegerField(blank=True, null=True, unique=True)

    user = models.OneToOneField(User, on_delete=models.CASCADE, primary_key=True, related_name='company_info')
    
    def save(self, *args, **kwargs):
        super(CompanySettings, self).save(*args, **kwargs)

        if self.company_logo:
            filepath = self.company_logo.path
            width = self.company_logo.width
            height = self.company_logo.height

            min_size = min(width, height)

            if min_size > 300:
                image = Image.open(filepath)
                image = image.resize(
                    (round(width / min_size * 300),
                    round(height / min_size * 300)),
                    Image.ANTIALIAS
                )
                image.save(filepath)


class BrokerCompany(models.Model):
    name = models.CharField(max_length=100, default="", unique=True)


class Broker(models.Model):
    created_date = models.DateTimeField(auto_now_add=True, blank=True, null=True)
    modifiedDateTime = models.DateTimeField(auto_now=True)
    removedDateTime = models.DateTimeField(blank=True, null=True)
    name = models.CharField(max_length=100, default="")
    phone_number = models.CharField(max_length=100, default="", unique=True)

    company = models.ForeignKey(BrokerCompany, on_delete=models.CASCADE, related_name="brokers", null=True)
    company_instance = models.ForeignKey(Company, null=True, blank=True, related_name='brokers', on_delete=models.SET_NULL)

    class Meta:
        indexes = [
            models.Index(fields=['company_instance']),
            models.Index(fields=['phone_number'])
        ]


class Car(models.Model):
    created_date = models.DateTimeField(auto_now_add=True, blank=True, null=True)
    modifiedDateTime = models.DateTimeField(auto_now=True)
    removedDateTime = models.DateTimeField(blank=True, null=True)
    bid_time = models.DateTimeField(blank=True, null=True)
    number = models.CharField(max_length=50, blank=True, default="000000")
    type = models.CharField(max_length=50, blank=True, default="Default")
    width = models.FloatField(default=1)
    height = models.FloatField(default=1)
    length = models.FloatField(default=1)
    availableCity = models.CharField(max_length=200, blank=True, default="")
    availableDates = models.TextField(blank=True, default="None")
    weight = models.FloatField(blank=True, default=0.00)
    carModel = models.CharField(max_length=50, blank=True, default="")
    carYear = models.PositiveSmallIntegerField(default=0)
    vin = models.CharField(max_length=200, blank=True, default="")
    licensePlate = models.CharField(max_length=200, blank=True, null=True)
    licenseState = models.CharField(max_length=200, blank=True, null=True)
    licenseExpiryDate = models.DateField(blank=True, null=True)
    insuranceExpiry = models.DateField(blank=True, null=True)
    note = models.TextField(blank=True, default="")
    payload = models.IntegerField(blank=True, null=True, default=0)
    last_status_change = models.DateTimeField(blank=True, null=True)
    location = models.CharField(max_length=60, blank=True, null=True)
    two_drivers = models.BooleanField(default=False)

    status = models.ForeignKey(CarStatus, default=2, related_name='cars_in_status', on_delete=models.SET_DEFAULT, null=True)
    car_creator = models.ForeignKey(User, on_delete=models.CASCADE, related_name='created_cars', null=True)
    car_owner = models.ForeignKey(CarOwner, on_delete=models.CASCADE, related_name='owner_cars', null=True)
    drivers = models.ManyToManyField(DriverInfo)
    dispatcher = models.ForeignKey(User, on_delete=models.SET_NULL, related_name='dispatcher_cars', null=True)
    active_driver = models.OneToOneField(DriverInfo, on_delete=models.SET_NULL, null=True, related_name="working_car")

    company_instance = models.ForeignKey(Company, null=True, blank=True, related_name='cars', on_delete=models.SET_NULL)

    def save(self, *args, **kwargs):
        if self.active_driver == None and self.id != None:
            free_car_drivers = self.drivers.filter(working_car=None)
            if free_car_drivers.count() > 0:
                self.active_driver = free_car_drivers[0]
             
        super(Car, self).save(*args, **kwargs)

    def __str__(self):
        return '#' + str(self.id) + ' ' +self.number

    class Meta:
        ordering = ['-modifiedDateTime']
        indexes = [
            models.Index(fields=['company_instance']),
            models.Index(fields=['status']),
            models.Index(fields=['type'])
        ]


class Load(models.Model):
    created_date = models.DateTimeField(auto_now_add=True, blank=True, null=True)
    modifiedDateTime = models.DateTimeField(auto_now=True)
    removedDateTime = models.DateTimeField(blank=True, null=True)
    # локации
    pickUpAt = models.CharField(max_length=200, blank=True, default="")
    pickUpAt_city = models.CharField(max_length=200, blank=True, default="")
    pickUpAt_state = models.CharField(max_length=200, blank=True, default="")
    pickUpAt_zip = models.CharField(max_length=10, blank=True, default="")
    pickUpAt_changed = models.CharField(max_length=200, blank=True, default="")
    pick_up_date = models.CharField(max_length=50, blank=True, default="")
    # pick_up_date = models.DateTimeField(blank=True, null=True)
    deliverTo = models.CharField(max_length=200, blank=True, default="")
    deliverTo_city = models.CharField(max_length=200, blank=True, default="")
    deliverTo_state = models.CharField(max_length=200, blank=True, default="")
    deliverTo_zip = models.CharField(max_length=10, blank=True, default="")
    deliverTo_changed = models.CharField(max_length=200, blank=True, default="")
    delivery_date = models.CharField(max_length=50, blank=True, default="")
    # delivery_date = models.DateTimeField(blank=True, null=True)
    # размеры
    width = models.PositiveSmallIntegerField(default=1)
    height = models.PositiveSmallIntegerField(default=1)
    length = models.PositiveSmallIntegerField(default=1)
    dimensions_units = models.CharField(max_length=20, blank=True, default="Inches")
    weight = models.PositiveIntegerField(default=1)
    weight_changed = models.PositiveIntegerField(blank=True, null=True)
    weight_units = models.CharField(max_length=20, blank=True, default="Pounds")
    dims = models.CharField(max_length=200, blank=True, null=True)
    total_cargo = models.PositiveIntegerField(default=1) 
    # цены
    price = models.FloatField(default=0)
    driver_price = models.FloatField(default=0)
    broker_price = models.FloatField(default=0)
    # boolean
    isDanger = models.BooleanField(default=False)
    isUrgent = models.BooleanField(default=False)
    isCanPutOnTop = models.BooleanField(default=False)
    liftgate = models.BooleanField(default=False)
    dock_level = models.BooleanField(default=False)
    team = models.BooleanField(default=False)
    wait_and_return = models.BooleanField(default=False)

    requirements = models.CharField(max_length=150, default="None", blank=True)
    pallets = models.PositiveIntegerField(default=0)
    pieces = models.PositiveIntegerField(default=0)
    pieces_changed = models.PositiveIntegerField(blank=True, null=True)
    items_count = models.PositiveIntegerField(default=0)
    
    car = models.TextField(default="Any")
    miles = models.FloatField(default=0)
    bided = models.BooleanField(default=False)

    start_time = models.DateTimeField(blank=True, null=True)
    finish_time = models.DateTimeField(blank=True, null=True)
    start_location = models.CharField(max_length=60, blank=True, null=True)
    end_location = models.CharField(max_length=60, blank=True, null=True)
    miles_out = models.PositiveSmallIntegerField(default=0)
    
    last_car = models.CharField(max_length=200, blank=True, null=True)
    approximate_time = models.PositiveIntegerField(default=0)
    
    company = models.CharField(max_length=200, blank=True, null=True)
    BOL = models.CharField(max_length=200, blank=True, null=True)
    unloaded_by = models.CharField(max_length=200, blank=True, null=True)
    recieved_by = models.CharField(max_length=200, blank=True, null=True)
    brokerage = models.CharField(max_length=200, blank=True, null=True)

    stat_No = models.CharField(max_length=200, blank=True, null=True)
    hash = models.BigIntegerField(blank=True, null=True)

    users_saw = models.TextField(default="", null=True, blank=True)
    # уведомления
    email_notifications_flag = models.BooleanField(default=False)
    email_notifications_interval = models.CharField(max_length=5, default='1h', choices=(
        ('15min', '15 min'), ('30min', '30 min'), ('1h', '1 h'), ('2h', '2 h'), ('3h', '3 h'), ('4h', '4 h')
        ), null=True)
    location_update_emails = models.TextField(default="", null=True, blank=True)
    status_update_emails = models.TextField(default="", null=True, blank=True)
    # статусы
    status = models.ForeignKey(LoadStatus, default=1, related_name='loads_in_status', on_delete=models.SET_DEFAULT)
    substatus = models.ForeignKey(LoadSubStatus, default=1, related_name='loads_in_substatus', on_delete=models.SET_NULL, null=True)
    status_info = models.TextField(default="", null=True, blank=True)

    sys_ref = models.CharField(max_length=60, default="")
    mail_part = models.TextField(default="", null=True, blank=True)
    mail_subject = models.TextField(default="", null=True, blank=True)
    mail_id = models.CharField(max_length=100, default="", blank=True, null=True)
    mail_thread = models.CharField(max_length=100, default="", blank=True, null=True)
    reply_email = models.CharField(max_length=100, default="", blank=True, null=True)
    broker_company = models.CharField(max_length=100, default="", blank=True, null=True)
    broker_name = models.CharField(max_length=100, default="", blank=True, null=True)
    broker_phone = models.CharField(max_length=20, default="", blank=True, null=True)
    broker_fax = models.CharField(max_length=20, default="", blank=True, null=True)
    # примечания
    dispatcher_note = models.TextField(default="", null=True, blank=True)
    driver_note = models.TextField(default="", null=True, blank=True)
    note = models.TextField(default="", null=True, blank=True)
    actions_json = models.TextField(default="", null=True, blank=True)

    shipper = models.ForeignKey(User, on_delete=models.CASCADE, related_name="shipper_loads", null=True)
    carrier = models.ForeignKey(User, on_delete=models.SET_NULL, related_name="carrier_loads", null=True)
    resp_car = models.OneToOneField(Car, on_delete=models.SET_NULL, related_name="load", null=True)
    resp_driver = models.ForeignKey(DriverInfo, on_delete=models.SET_NULL, related_name="driver_loads", null=True)
    resp_shipper_dispatcher = models.ForeignKey(User, on_delete=models.SET_NULL, related_name="shipper_dispatcher_loads", null=True)
    resp_carrier_dispatcher = models.ForeignKey(User, on_delete=models.SET_NULL, related_name="carrier_dispatcher_loads", null=True)

    company_instance = models.ForeignKey(Company, null=True, blank=True, related_name='loads', on_delete=models.SET_NULL)

    def save(self, *args, **kwargs):
        point_from = self.pickUpAt.replace(' ', '%20')
        point_to = self.deliverTo.replace(' ', '%20')
        approximate_time = 0
        miles = 0
        start_location = ""
        end_location = ""
        pickUpAt_city = ''
        pickUpAt_state = ''
        pickUpAt_zip = ''
        deliverTo_city = ''
        deliverTo_state = ''
        deliverTo_zip = ''


        if self.id == None:
            bing_req = requests.get("http://dev.virtualearth.net/REST/v1/Routes?wp.1=" + point_from + "&wp.2=" + point_to + "&key=" + settings.BING_API_KEY + "&distanceUnit=mi")
            json_bing_req = json.loads(bing_req.text)

            if json_bing_req['statusCode'] == 200:
                if len(json_bing_req['resourceSets'][0]['resources']) > 0:
                    route = json_bing_req['resourceSets'][0]['resources'][0]

                    approximate_time = route['travelDuration']
                    miles = round(route['travelDistance'])
                    coords = route['routeLegs'][0]['actualStart']['coordinates']
                    start_location = str(coords[0]) + ',' + str(coords[1])

                    coords = route['routeLegs'][0]['actualEnd']['coordinates']
                    end_location = str(coords[0]) + ',' + str(coords[1])

                    pickUpAt_city = route['routeLegs'][0]['startLocation']['address']['locality']
                    pickUpAt_state = route['routeLegs'][0]['startLocation']['address']['adminDistrict']
                    pickUpAt_zip = route['routeLegs'][0]['startLocation']['address']['postalCode'] if 'postalCode' in route['routeLegs'][0]['startLocation']['address'] else ''
                    deliverTo_city = route['routeLegs'][0]['endLocation']['address']['locality']
                    deliverTo_state = route['routeLegs'][0]['endLocation']['address']['adminDistrict']
                    deliverTo_zip = route['routeLegs'][0]['endLocation']['address']['postalCode'] if 'postalCode' in route['routeLegs'][0]['endLocation']['address'] else ''
                
            else:
                return

            self.start_location = start_location
            self.end_location = end_location
            

        if self.approximate_time == 0:
            self.approximate_time = approximate_time

        if self.miles == 0:
            self.miles = miles

        s_hash = hash(str(self.pk) + str(self.sys_ref) + '__salt')
        if int(s_hash) < 0:
            s_hash = s_hash * -1
        self.hash = s_hash

        separated_pickup = separate_location(self.pickUpAt)
        self.pickUpAt_city = pickUpAt_city if pickUpAt_city != '' else separated_pickup['city']
        self.pickUpAt_state = pickUpAt_state if pickUpAt_state != '' else separated_pickup['state']
        self.pickUpAt_zip = pickUpAt_zip if pickUpAt_zip != '' else separated_pickup['zip']

        separated_deliverto = separate_location(self.deliverTo)
        self.deliverTo_city = deliverTo_city if deliverTo_city != '' else separated_deliverto['city']
        self.deliverTo_state = deliverTo_state if deliverTo_state != '' else separated_deliverto['state']
        self.deliverTo_zip = deliverTo_zip if deliverTo_zip != '' else separated_deliverto['zip']

        super(Load, self).save(*args, **kwargs)


    class Meta:
        constraints = [
            UniqueConstraint(fields=['pickUpAt', 'deliverTo', 'broker_company'], condition=Q(removedDateTime=None, start_time=None, status=1), name='unique_loads_from_broker')
        ]
        indexes = [
            models.Index(fields=['status']),
            models.Index(fields=['pickUpAt_state']),
            models.Index(fields=['deliverTo_state']),
            models.Index(fields=['company_instance'])
        ]


class SavedLoad(models.Model):
    location_from = models.CharField(max_length=200, blank=True, default="")
    state_from = models.CharField(max_length=20, blank=True, default="")
    location_to = models.CharField(max_length=200, blank=True, default="")
    state_to = models.CharField(max_length=20, blank=True, default="")

    miles = models.FloatField(default=0)
    gross = models.FloatField(default=0)
    driver_cost = models.FloatField(default=0)
    profit = models.FloatField(default=0)
    percents = models.FloatField(default=0)


class Cargo(models.Model):
    package_type = models.CharField(max_length=40, blank=True, default="")
    quantity = models.PositiveIntegerField(default=1)
    total_weight = models.PositiveIntegerField(default=0)
    width = models.PositiveSmallIntegerField(default=1)
    height = models.PositiveSmallIntegerField(default=1)
    length = models.PositiveSmallIntegerField(default=1)

    load = models.ForeignKey(Load, on_delete=models.CASCADE, related_name="cargos", null=True)


class LoadPoint(models.Model):
    type = models.CharField(max_length=50, blank=True, default="")
    full_name = models.CharField(max_length=100, blank=True, default="")
    country = models.CharField(max_length=40, blank=True, default="USA")
    state = models.CharField(max_length=40, blank=True, default="")
    city = models.CharField(max_length=40, blank=True, default="")
    zip_code = models.CharField(max_length=10, blank=True, default="")
    location = models.CharField(max_length=50, blank=True, default="")
    # datetime = models.DateTimeField(blank=True, null=True)
    datetime = models.CharField(max_length=50, blank=True, default="")

    load = models.ForeignKey(Load, on_delete=models.CASCADE, related_name="points", null=True)


class Documents(models.Model):
    created_date = models.DateTimeField(auto_now_add=True, blank=True, null=True)
    name = models.CharField(max_length=100, blank=True, default="")
    file = models.FileField(upload_to='uploads/%Y/%m/%d/', blank=True, null=True)
    sender = models.ForeignKey(User, on_delete=models.SET_NULL, related_name='documents', null=True)
    load = models.ForeignKey(Load, on_delete=models.CASCADE, related_name="documents", null=True)

    class Meta:
        indexes = [
            models.Index(fields=['sender']),
            models.Index(fields=['load'])
        ]


class Tutorial(models.Model):
    created_date = models.DateTimeField(auto_now_add=True, blank=True, null=True)
    name = models.CharField(max_length=100, blank=True, default="")
    text = models.TextField(default="", null=True, blank=True)
    
    company = models.ForeignKey(CompanySettings, on_delete=models.CASCADE, related_name="tutorials", null=True)
    company_instance = models.ForeignKey(Company, null=True, blank=True, related_name='tutorials', on_delete=models.CASCADE)

    class Meta:
        indexes = [
            models.Index(fields=['company_instance'])
        ]

    
class LoadInHistory(models.Model):
    created_date = models.DateTimeField(auto_now_add=True, blank=True, null=True)
    removedDateTime = models.DateTimeField(blank=True, null=True)
    driver_price = models.FloatField(default=0)
    action = models.CharField(max_length=50, default="", blank=True)
    success = models.BooleanField(default=False)

    driver = models.ForeignKey(DriverInfo, on_delete=models.CASCADE, related_name="saved_loads")
    load = models.ForeignKey(Load, on_delete=models.CASCADE, related_name="saved_in_history", null=True)

    class Meta:
        indexes = [
            models.Index(fields=['driver']),
            models.Index(fields=['load']),
            models.Index(fields=['action']),
        ]


class Proposition(models.Model):
    created_date = models.DateTimeField(auto_now_add=True, blank=True, null=True)
    removedDateTime = models.DateTimeField(blank=True, null=True)
    status = models.CharField(max_length=20, default="Send")
    agree = models.BooleanField(default=False)
    driver_price = models.FloatField(default=0)
    broker_price = models.FloatField(default=0)
    price = models.FloatField(default=0)
    mail = models.TextField(default="")
    miles_out = models.PositiveSmallIntegerField(default=0)

    driver = models.ForeignKey(DriverInfo, on_delete=models.CASCADE, related_name="driver_propositions", null=True)
    car = models.ForeignKey(Car, on_delete=models.CASCADE, related_name="car_propositions", null=True)
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name="user_propositions")
    load = models.ForeignKey(Load, on_delete=models.CASCADE, related_name="load_propositions")

    class Meta:
        ordering = ['-created_date']
        indexes = [
            models.Index(fields=['driver']),
            models.Index(fields=['load']),
            models.Index(fields=['status']),
        ]


class Location(models.Model):
    point = models.CharField(max_length=200, default="")
    timestamp = models.PositiveIntegerField(default=1)
    location_name = models.CharField(max_length=200, default="")

    driver = models.ForeignKey(DriverInfo, on_delete=models.CASCADE, related_name="driver_locations")
    load = models.ForeignKey(Load, on_delete=models.CASCADE, related_name="load_locations", null=True)

    class Meta:
        ordering = ['-timestamp']

# чаты 1 на 1 (2 класса - чат и сообщение)
class ChatGroup(models.Model):
    created_date = models.DateTimeField(auto_now_add=True, blank=True, null=True)
    modifiedDateTime = models.DateTimeField(auto_now=True)
    removedDateTime = models.DateTimeField(blank=True, null=True)

    user_initiator = models.ForeignKey(User, on_delete=models.CASCADE, related_name="chat_groups_initiator")
    user_member = models.ForeignKey(User, on_delete=models.CASCADE, related_name="chat_groups_member")

    class Meta:
        ordering = ['-modifiedDateTime']
        indexes = [
            models.Index(fields=['user_initiator', 'user_member'])
        ]


class Message(models.Model):
    created_date = models.DateTimeField(auto_now_add=True, blank=True, null=True)
    modifiedDateTime = models.DateTimeField(auto_now=True)
    removedDateTime = models.DateTimeField(blank=True, null=True)
    content = models.TextField(blank=True, default="")
    status = models.CharField(max_length=20, default="Send")
    type = models.CharField(max_length=20, default="Simple")

    user_from = models.ForeignKey(User, on_delete=models.CASCADE, related_name="user_from_messages")
    user_to = models.ForeignKey(User, on_delete=models.CASCADE, related_name="user_to_messages")
    chat_group = models.ForeignKey(ChatGroup, on_delete=models.CASCADE, related_name="chat_group_messages")
    working_group = models.ForeignKey(WorkingGroup, on_delete=models.SET_NULL, related_name='working_group_messages', null=True)

    def __str__(self):
        return self.content

    class Meta:
        ordering = ['-modifiedDateTime']

# групповые чаты (2 класса - чат и сообщение)
class Chat(models.Model):
    created_date = models.DateTimeField(auto_now_add=True, blank=True, null=True)
    modifiedDateTime = models.DateTimeField(auto_now=True)
    removedDateTime = models.DateTimeField(blank=True, null=True)
    company_id = models.IntegerField(default=0, blank=True)
    hash = models.BigIntegerField(blank=True, null=True)
    
    users = models.ManyToManyField(User)
    working_group = models.OneToOneField(WorkingGroup, on_delete=models.CASCADE, null=True)
    driver = models.OneToOneField(DriverInfo, on_delete=models.CASCADE, null=True)
    load = models.OneToOneField(Load, on_delete=models.CASCADE, null=True, related_name='load_chat')

    company_instance = models.ForeignKey(Company, null=True, blank=True, related_name='chats', on_delete=models.CASCADE)

    def save(self, *args, **kwargs):
        if not hasattr(self, 'hash') or self.hash == '' or self.hash == None:
            s_hash = hash(str(self.pk) + '_' + str(self.company_id))
            if int(s_hash) < 0:
                s_hash = s_hash * -1
            self.hash = s_hash
        super(Chat, self).save(*args, **kwargs)

    class Meta:
        ordering = ['-modifiedDateTime']
        indexes = [
            models.Index(fields=['company_instance', 'load']),
            models.Index(fields=['company_instance', 'working_group'])
        ]

    
class ChatMessage(models.Model):
    created_date = models.DateTimeField(auto_now_add=True, blank=True, null=True)
    modifiedDateTime = models.DateTimeField(auto_now=True)
    removedDateTime = models.DateTimeField(blank=True, null=True)
    content = models.TextField(blank=True, default="")

    users_read = models.ManyToManyField(User)
    chat_group = models.ForeignKey(Chat, on_delete=models.CASCADE, related_name="messages")
    user_from = models.ForeignKey(User, on_delete=models.CASCADE, related_name="messages_in_chat")

    class Meta:
        ordering = ['-created_date']
        indexes = [
            models.Index(fields=['chat_group'])
        ]


class TwilioMessage(models.Model):
    modifiedDateTime = models.DateTimeField(auto_now=True)
    removedDateTime = models.DateTimeField(blank=True, null=True)
    content = models.TextField(blank=True, default="")
    media = models.TextField(blank=True, default="")
    status = models.CharField(max_length=20, default="Send")
    type = models.CharField(max_length=20, default="SMS")
    toNumber = models.CharField(max_length=20, default="")
    fromNumber = models.CharField(max_length=20, default="")

    user_from = models.ForeignKey(User, on_delete=models.CASCADE, related_name="twilio_from_messages", null=True)
    user_to = models.ForeignKey(User, on_delete=models.CASCADE, related_name="twilio_to_messages", null=True)

    broker_from = models.ForeignKey(Broker, on_delete=models.CASCADE, related_name="twilio_from_messages", null=True)
    broker_to = models.ForeignKey(Broker, on_delete=models.CASCADE, related_name="twilio_to_messages", null=True)

    company_instance = models.ForeignKey(Company, null=True, blank=True, related_name='twilio_messages', on_delete=models.CASCADE)

    class Meta:
        ordering = ['id']
        indexes = [
            models.Index(fields=['company_instance'])
        ]


class Email(models.Model):
    created_date = models.DateTimeField(auto_now_add=True, blank=True, null=True)
    removedDateTime = models.DateTimeField(blank=True, null=True)
    content = models.TextField(blank=True, default="")

    user_from = models.ForeignKey(User, on_delete=models.CASCADE, related_name="user_from_emails")
    user_to = models.ForeignKey(User, on_delete=models.CASCADE, related_name="user_to_emails")


class Notice(models.Model):
    created_date = models.DateTimeField(auto_now_add=True, blank=True, null=True)
    modifiedDateTime = models.DateTimeField(auto_now=True)
    removedDateTime = models.DateTimeField(blank=True, null=True)
    content = models.TextField(blank=True, default="")
    status = models.CharField(max_length=20, default="Send")
    type = models.CharField(max_length=20, default="Notice")
    entity_type = models.CharField(max_length=50, default="")
    entity_id = models.PositiveIntegerField(default=0)

    user_to = models.ForeignKey(User, on_delete=models.CASCADE, related_name="user_notices")

    def __str__(self):
        return self.content

    class Meta:
        ordering = ['-modifiedDateTime']


class Call(models.Model):
    created_date = models.DateTimeField(auto_now_add=True, null=True)
    modifiedDateTime = models.DateTimeField(auto_now=True)
    duration = models.CharField(max_length=20, default="")
    record_link = models.URLField(blank=True, default="")
    number_to = models.CharField(max_length=20, default="")
    name_to = models.CharField(max_length=100, default="")
    avatar_to = models.CharField(max_length=200, default="")
    number_from = models.CharField(max_length=20, default="")
    name_from = models.CharField(max_length=100, default="")
    avatar_from = models.CharField(max_length=200, default="")
    note = models.CharField(max_length=200, default="")
    direction = models.CharField(max_length=50, default="")
    status = models.CharField(max_length=20, default="")

    company = models.ForeignKey(CompanySettings, on_delete=models.CASCADE, related_name="calls", null=True)
    company_instance = models.ForeignKey(Company, null=True, blank=True, related_name='calls', on_delete=models.CASCADE)
    author = models.ForeignKey(User, on_delete=models.CASCADE, related_name="calls", null=True)


class UserAction(models.Model):
    modifiedDateTime = models.DateTimeField(auto_now=True)
    removedDateTime = models.DateTimeField(blank=True, null=True)
    content = models.CharField(max_length=200, default="")
    time = models.PositiveIntegerField(default=1)

    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name="user_actions")

    class Meta:
        ordering = ['-modifiedDateTime']


class System(models.Model):
    modifiedDateTime = models.DateTimeField(auto_now=True)
    optionName = models.CharField(max_length=200, default="", blank=True)
    optionValue = models.TextField(default="", blank=True, null=True)


class RegistrationRequest(models.Model):
    modifiedDateTime = models.DateTimeField(auto_now=True)
    removedDateTime = models.DateTimeField(blank=True, null=True)
    status = models.CharField(max_length=20, default="Send")

    company_instance = models.ForeignKey(Company, null=True, blank=True, related_name='requests', on_delete=models.SET_NULL)
    role = models.ForeignKey(UserRole, on_delete=models.CASCADE, related_name="requests", null=True)
    new_user = models.OneToOneField(User, on_delete=models.CASCADE, primary_key=True)
    resp_user = models.ForeignKey(User, on_delete=models.CASCADE, related_name="user_requests")


class File(models.Model):
    created_date = models.DateTimeField(auto_now_add=True, blank=True, null=True)
    name = models.CharField(max_length=100, blank=True, default="")
    file_name = models.CharField(max_length=100, blank=True, default="")
    size = models.CharField(max_length=20, blank=True, default="")
    extension = models.CharField(max_length=10, blank=True, default="")
    path = models.FileField(upload_to=chat_directory_path, blank=True, null=True)
    
    chat = models.ForeignKey(Chat, on_delete=models.SET_NULL, related_name='files', null=True)
    message = models.ForeignKey(ChatMessage, on_delete=models.SET_NULL, related_name='files', null=True)
    tutorial = models.ForeignKey(Tutorial, on_delete=models.CASCADE, related_name="files", null=True)
    sender = models.ForeignKey(User, on_delete=models.SET_NULL, related_name='files', null=True)

    # def save(self, *args, **kwargs):
    #     if self.path:
    #         filepath = Path(r'' + str(self.path.path))
    #         fileinfo = filepath.stat()
    #         name = os.path.basename(filepath)

    #         self.file_name = os.path.splitext(name)[0]
    #         self.size = fileinfo.st_size
    #         self.extension = os.path.splitext(name)[1]
    #         super().save(*args, **kwargs)

    class Meta:
        ordering = ['-created_date']


class Payment(models.Model):
    created_date = models.DateTimeField(auto_now_add=True, blank=True, null=True)
    modifiedDateTime = models.DateTimeField(auto_now=True)
    removedDateTime = models.DateTimeField(blank=True, null=True)
    
    week = models.SmallIntegerField(default=0)
    amount = models.FloatField(default=0)
    status =  models.ForeignKey(BookkeepingStatus, related_name='payments', on_delete=models.SET_NULL, null=True)
    load = models.ForeignKey(Load, related_name='payments', on_delete=models.SET_NULL, null=True)
    user = models.ForeignKey(User, related_name='payments', on_delete=models.SET_NULL, null=True)




@receiver(pre_delete, sender=Proposition)
def delete_proposition_hook(sender, instance, using, **kwargs):
    car = instance.car
    status = CarStatus.objects.get(pk=1)
    car.status = status
    car.save(update_fields=['status'])

@receiver(pre_delete, sender=Documents)
def delete_documennt_hook(sender, instance, using, **kwargs):
    instance.file.delete()

@receiver(pre_delete, sender=File)
def delete_file_hook(sender, instance, using, **kwargs):
    instance.path.delete()
