from __future__ import absolute_import, unicode_literals
from celery.decorators import task
from datetime import datetime, timedelta
from django.utils import timezone
from .models import Load, LoadInHistory, Proposition, Car
from app.helpers.send_email_by_smtp import send_emails_for_loads
from app.helpers.push import send_push
from api import settings
import smtplib, requests


def find_email(subj: str) -> str:
    reg_str = r'\S+@\S+'
    full_str_group = re.search(reg_str, subj)

    if full_str_group == None:
        return ''

    full_str = full_str_group.group(0).strip()
    return re.sub(r'\(|\)', '', full_str)
    


@task(name="every_minute")
def every_minute():
    before_15_min = datetime.now() - timedelta(minutes=15)
    Car.objects.filter(status=4, bid_time__lte=before_15_min).update(status=1, bid_time=None)


@task(name="load_expired")
def load_expired():
    before_30_min = datetime.now() - timedelta(minutes=30)
    before_12_h = datetime.now() - timedelta(hours=12)

    expired_propositions = Proposition.objects.filter(removedDateTime=None, created_date__lte=before_12_h, status="Send").select_related('car')
    if expired_propositions.exists():
        expired_propositions.update(removedDateTime=datetime.now())

    expired_bids = LoadInHistory.objects.filter(removedDateTime=None, created_date__lte=before_30_min, action="Bid").select_related('load')
    if expired_bids.exists():
        expired_bids.update(removedDateTime=datetime.now())

    expired_loads = Load.objects.filter(removedDateTime=None, created_date__lte=before_30_min, status=1, substatus=1, resp_driver=None)
    if expired_loads.count() > 10:
        expired_loads.exclude(bided=True).update(removedDateTime=datetime.now(), sys_ref="")
    Load.objects.filter(removedDateTime=None, created_date__lte=before_12_h, status=1, substatus=1, resp_driver=None).update(removedDateTime=datetime.now(), sys_ref="")



@task(name="update_load_location_email_15min")
def update_load_location_email_15min():
    loads = Load.objects.filter(removedDateTime=None, email_notifications_flag=True, email_notifications_interval='15min').exclude(start_time=None).values_list('brokerage', 'location_update_emails', 'sys_ref', 'resp_car__location', 'resp_car__availableCity', 'resp_car__modifiedDateTime')
    send_emails_for_loads(loads=loads)


@task(name="update_load_location_email_30min")
def update_load_location_email_30min():
    loads = Load.objects.filter(removedDateTime=None, email_notifications_flag=True, email_notifications_interval='30min').exclude(start_time=None).values_list('brokerage', 'location_update_emails', 'sys_ref', 'resp_car__location', 'resp_car__availableCity', 'resp_car__modifiedDateTime')
    send_emails_for_loads(loads=loads)


@task(name="update_load_location_email_1h")
def update_load_location_email_1h():
    loads = Load.objects.filter(removedDateTime=None, email_notifications_flag=True, email_notifications_interval='1h').exclude(start_time=None).values_list('brokerage', 'location_update_emails', 'sys_ref', 'resp_car__location', 'resp_car__availableCity', 'resp_car__modifiedDateTime')
    send_emails_for_loads(loads=loads)


@task(name="update_load_location_email_2h")
def update_load_location_email_2h():
    loads = Load.objects.filter(removedDateTime=None, email_notifications_flag=True, email_notifications_interval='2h').exclude(start_time=None).values_list('brokerage', 'location_update_emails', 'sys_ref', 'resp_car__location', 'resp_car__availableCity', 'resp_car__modifiedDateTime')
    send_emails_for_loads(loads=loads)


@task(name="update_load_location_email_3h")
def update_load_location_email_3h():
    loads = Load.objects.filter(removedDateTime=None, email_notifications_flag=True, email_notifications_interval='3h').exclude(start_time=None).values_list('brokerage', 'location_update_emails', 'sys_ref', 'resp_car__location', 'resp_car__availableCity', 'resp_car__modifiedDateTime')
    send_emails_for_loads(loads=loads)


@task(name="update_load_location_email_4h")
def update_load_location_email_4h():
    loads = Load.objects.filter(removedDateTime=None, email_notifications_flag=True, email_notifications_interval='4h').exclude(start_time=None).values_list('brokerage', 'location_update_emails', 'sys_ref', 'resp_car__location', 'resp_car__availableCity', 'resp_car__modifiedDateTime')
    send_emails_for_loads(loads=loads)


@task(name="update_pubsub")
def update_pubsub():
    requests.get("https://pubsub.altekloads.com/")


@task(name="geo_push_request")
def geo_push_request():
    data_message = {
        'action': "update_location",
        'body': "Location updated",
        'title': "Location service"
    }
    send_push(data_message=data_message, group="/topics/all")
