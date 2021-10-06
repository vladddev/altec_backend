from asgiref.sync import async_to_sync
from channels.generic.websocket import WebsocketConsumer, JsonWebsocketConsumer
from app.serializers import *
from app.models import *
from api import settings
from datetime import datetime
from app.helpers.send_email_by_smtp import send_emails_for_loads
from app.helpers.model_helpers import add_history_action_to_model
from app.helpers.push import send_push

import json, requests


class GeneralConsumer(JsonWebsocketConsumer):
    def connect(self):
        self.group_id = self.scope['url_route']['kwargs']['company_hash']
        self.room_group_name = 'general_%s' % self.group_id
        print('Connect: ' + str(self.scope['user']))
        self.gen_group_name = 'general'

        async_to_sync(self.channel_layer.group_add)(
            self.room_group_name,
            self.channel_name
        )

        async_to_sync(self.channel_layer.group_add)(
            self.gen_group_name,
            self.channel_name
        )

        self.accept()

        # if str(self.group_id) == '0':
        #     self.update_loads()

        if self.scope['user'] != None:
            user = User.objects.get(id=self.scope['user'])
            user.is_online = True
            user.last_online = datetime.now()
            user.save(update_fields=['is_online', 'last_online'])
            if hasattr(user, 'driver_info') and user.driver_info != None:
                self.driver_online_change(driver_id=self.scope['user'], is_online=True)
                user.driver_info.in_app = True
                user.driver_info.app_activity_time = datetime.now()
                print('Driver online: ' + str(datetime.now()))
                user.driver_info.save(update_fields=['in_app', 'app_activity_time'])
                self.driver_connect(self.scope['user'])

    def disconnect(self, close_code):
        async_to_sync(self.channel_layer.group_discard)(
            self.room_group_name,
            self.channel_name
        )
        async_to_sync(self.channel_layer.group_discard)(
            self.gen_group_name,
            self.channel_name
        )

        if self.scope['user'] != None:
            user = User.objects.get(id=self.scope['user'])
            user.is_online = False
            user.save(update_fields=['is_online'])
            if hasattr(user, 'driver_info') and user.driver_info != None:
                self.driver_online_change(driver_id=self.scope['user'], is_online=False)
                user.driver_info.in_app = False
                user.driver_info.app_activity_time = datetime.now()
                print('Driver offline: ' + str(datetime.now()))
                user.driver_info.save(update_fields=['in_app', 'app_activity_time'])

    def receive_json(self, content):
        curr_user_id = self.scope['user']
        action = content['action']

        # if action != 'update_loads':
        #     if not curr_user_id:
        #         # self.close(code=3009)
        #         raise

        company_hash = self.scope['url_route']['kwargs']['company_hash']

        method = getattr(self, action)
        method(content['data'], curr_user_id, company_hash)

    def load_status_change(self, content=None, curr_user_id=None, company_hash=None):
        responded_load = content['load_id']
        curr_user = User.objects.get(id=self.scope['user'])
        load_instance = None
        resp_car = None
        resp_driver = None
        notice = ''
        print('Load: #' + str(responded_load) + '; Status: ' + str(content['status']) + '; Substatus: ' + str(content['substatus']))
   
        company = None
        try:
            company = Company.objects.get(company_hash=company_hash)
        except:
            pass
            # self.close(code=3008)

        try:
            load_instance = Load.objects.select_related('resp_driver', 'shipper', 'carrier', 'resp_carrier_dispatcher', 'resp_shipper_dispatcher').get(id=int(responded_load))
            resp_car = load_instance.resp_car
            resp_driver = load_instance.resp_driver
            print('Load2: #' + str(responded_load) + '; Status2: ' + str(load_instance.status.pk) + '; Substatus2: ' + str(load_instance.substatus.pk))
        except:
            pass
            # self.close(code=3007)

        if 'notice' in content:
            notice = content['notice']

        if load_instance == None:
            return
        else:
            resp_users_id = list()
            if load_instance.shipper != None: 
                resp_users_id.append(load_instance.shipper.pk)
            if load_instance.carrier != None: 
                resp_users_id.append(load_instance.carrier.pk)
            if load_instance.resp_carrier_dispatcher != None: 
                resp_users_id.append(load_instance.resp_carrier_dispatcher.pk)
            if load_instance.resp_shipper_dispatcher != None: 
                resp_users_id.append(load_instance.resp_shipper_dispatcher.pk)
            if load_instance.resp_driver != None: 
                resp_users_id.append(load_instance.resp_driver.pk)       

            if int(content['status']) == 6 and load_instance.resp_driver != None:

                if self.scope['user'] != load_instance.resp_driver.pk:
                    data_message = {
                        'action': "update_load_status",
                        'title': "Load status change",
                        'body': "You've been released by dispatcher on the load " + load_instance.pickUpAt + " —> " + load_instance.deliverTo + "!",
                        'id': int(responded_load),
                        'status': int(content['status']),
                        'substatus': int(content['substatus'])
                    }
                    send_push(data_message=data_message, tokens=[load_instance.resp_driver.user.fb_token], sound=True)

                LoadInHistory.objects.create(load=load_instance, action="Complete", driver_price=load_instance.driver_price, driver=load_instance.resp_driver)
                
                resp_car = load_instance.resp_car
                if resp_car != None:
                    load_instance.last_car = resp_car.id
                    if resp_car.status != 2:
                        resp_car.status = CarStatus.objects.get(pk=1)
                        resp_car.save(update_fields=['status'])
                        
                load_instance.resp_car = None
                load_instance.resp_driver = None
                load_instance.end_time = datetime.now()
                load_instance.save(update_fields=['last_car', 'resp_car', 'resp_driver'])

                Chat.objects.filter(load=load_instance.pk).update(removedDateTime=datetime.now())
                
        Load.objects.filter(removedDateTime=None, id=int(responded_load)).update(status=int(content['status']), substatus=int(content['substatus']))

        load = Load.objects.get(id=int(responded_load))
        print('Load3: #' + str(responded_load) + '; Status3: ' + str(load.status.pk) + '; Substatus3: ' + str(load.substatus.pk))

        add_history_action_to_model(load_instance, 'Status has changed to "' + load_instance.status.name + '" and sub-status "' + load_instance.substatus.name + '" by ' + curr_user.first_name + ' ' + curr_user.last_name)

        notice_content = 'Load #' + str(load_instance.pk) + ' (' + load_instance.pickUpAt + ' - ' + load_instance.deliverTo + ') has changed status to "' + load_instance.status.name + '" and sub-status "' + load_instance.substatus.name + '"'
        
        for user_id in set(resp_users_id):
            Notice.objects.create(user_to=User.objects.get(id=user_id), content=notice_content, entity_type="load", entity_id=load_instance.id)

        message = {
                'type': 'send_json',
                'content': {
                    'action': 'load_status_change',
                    'data': {
                        'status': int(content['status']),
                        'substatus': int(content['substatus']),
                        'notice': notice
                    }
                },
                'responded_users': resp_users_id
            }
            
        async_to_sync(self.channel_layer.group_send)(
            self.room_group_name,
            message
        )

        if resp_car != None:
            load = (load_instance.brokerage, load_instance.status_update_emails, load_instance.sys_ref, resp_car.location, resp_car.availableCity, resp_car.modifiedDateTime)
            
            try:
                send_emails_for_loads(loads=[load])
            except:
                pass

    def new_load_offer(self, content=None, curr_user_id=None, company_hash=None):
        responded_load = content['load_id']
        load_instance = None

        try:
            company = Company.objects.get(company_hash=company_hash)
        except:
            # self.close(code=3008)
            pass

        try:
            load_instance = Load.objects.get(id=int(responded_load))
        except :
            # self.close(code=3007)
            pass

        resp_driver = load_instance.resp_driver.pk
        
        load_data = LoadSerializer(load_instance).data
        message = {
                'type': 'send_json',
                'content': {
                    'action': 'new_load_offer',
                    'data': load_data
                },
                'responded_users': [resp_driver]
            }
        
        async_to_sync(self.channel_layer.group_send)(
            self.room_group_name,
            message
        )
    
    def new_load_auction(self, content=None, curr_user_id=None, company_hash=None):
        responded_load = content['load_id']
        load_instance = None

        try:
            company = Company.objects.get(company_hash=company_hash)
        except:
            # self.close(code=3008)
            pass

        try:
            load_instance = Load.objects.get(id=int(responded_load))
        except :
            # self.close(code=3007)
            pass

        resp_driver = load_instance.resp_driver.pk
        
        load_data = LoadSerializer(load_instance).data
        message = {
                'type': 'send_json',
                'content': {
                    'action': 'new_load_auction',
                    'data': load_data
                },
                'responded_users': content['drivers']
            }
        
        async_to_sync(self.channel_layer.group_send)(
            self.room_group_name,
            message
        )

    def driver_bid(self, content=None, curr_user_id=None, company_hash=None):
        company = None
        user = User.objects.get(id=self.scope['user'])
        company = Company.objects.get(company_hash=company_hash)
        
        load = Load.objects.get(id=content['load_id'])
        load.bided = True
        load.save(update_fields=['bided'])
        LoadInHistory.objects.create(load=load, action="Bid", driver_price=content['price'], driver=user.driver_info)

        dispatchers = User.objects.filter(company_instance=company, driver_info=None, owner_info=None)
        notice_content = f"{user.first_name + ' ' + user.last_name} has made a bid of {content['price']}$ on a load {load.pickUpAt} → {load.deliverTo}." 
        for dispatcher in dispatchers:
            Notice.objects.create(user_to=dispatcher, content=notice_content, entity_type="driver bid", entity_id=load.id)

        dispatchers_ids = list(User.objects.filter(company_instance=company).values_list('id', flat=True))
        dispatchers_ids.append(company.pk)
        dispatchers_ids.append(self.scope['user'])

        message = {
                    'type': 'send_json',
                    'content': {
                        'action': 'driver_bid',
                        'data': {
                            'load_id': content['load_id'],
                            'phone_number': user.phone_number,
                            'full_name': user.first_name + ' ' + user.last_name,
                            'notice_content': notice_content
                        }
                    },
                    'responded_users': dispatchers_ids
                }

        async_to_sync(self.channel_layer.group_send)(
            self.room_group_name,
            message
        )
        
    def update_loads(self, content=None, curr_user_id=None, company_hash=None):
        message = {
            'type': 'send_json',
            'content': {
                'action': 'update_loads',
                'data': content
            },
            'responded_users': '__all__'
        }
        
        async_to_sync(self.channel_layer.group_send)(
            self.gen_group_name,
            message
        )

    def group_chat_message(self, content=None, curr_user_id=None, company_hash=None):
        chat_group = None
        try:
            chat_group = Chat.objects.get(pk=int(content['chat_id']), users=curr_user_id)
        except:
            return

        user_from = User.objects.get(pk=curr_user_id)
        new_message = ChatMessage.objects.create(user_from=user_from, chat_group=chat_group, content=content['content'])
        new_message.users_read.add(user_from)
        chat_users = chat_group.users.all().values('id', 'fb_token')
        responded_users = list(map(lambda el: el['id'], chat_users))           
        driver_tokens = list(map(lambda el: el['fb_token'], chat_users))


        message = {
            'type': 'send_json',
            'content': {
                'action': 'group_chat_message',
                'data': {
                    'chat_id': int(content['chat_id']),
                    'chat_data': UserChatsSerializer(chat_group).data,
                    'modifiedDateTime': new_message.modifiedDateTime.isoformat(),
                    'content': content['content'],
                    'media': False,
                    'files': False,
                    'user_from': {
                        'id': user_from.id,
                        'email': user_from.email,
                        'avatar': '/backend/api/media/' + str(user_from.avatar),
                        'role': user_from.role,
                        'first_name': user_from.first_name,
                        'last_name': user_from.last_name,
                        'last_online': str(user_from.last_online)
                    }
                }
            },
            'responded_users': responded_users
        }
        media = None
        if 'media' in content:
            media = content['media']

        if 'files' in content:
            media = content['files']

        if media != None:
            files = File.objects.filter(id__in=media)
            files.update(message=new_message, chat=chat_group)
            file_data = FileSerializer(files, many=True).data

            message['content']['data']['media'] = file_data
            message['content']['data']['files'] = file_data

        
        async_to_sync(self.channel_layer.group_send)(
            self.gen_group_name,
            message
        )

        data_message = {
            'action': "chat_message",
            'title': user_from.first_name + ' ' + user_from.last_name,
            'body': content['content'],
            'id': int(content['chat_id'])
        }
        
        send_push(data_message=data_message, tokens=driver_tokens, sound=True)
        
    def new_load_add(self, content=None, curr_user_id=None, company_hash=None):
        drivers_ids = list(DriverInfo.objects.values_list('pk', flat=True))
        responded_load = content['load']
        load_instance = Load.objects.get(id=int(responded_load))
        load_data = LoadSerializer(load_instance).data

        message = {
                    'type': 'send_json',
                    'content': {
                        'action': 'new_load_add',
                        'data': {
                            'load': load_data
                        }
                    },
                    'responded_users': drivers_ids
                }

        async_to_sync(self.channel_layer.group_send)(
            self.gen_group_name,
            message
        )
    
    def update_sms(self, content=None, curr_user_id=None, company_hash=None):
        company = None
        try:
            company = Company.objects.get(company_hash=company_hash)
        except:
            self.close(code=3008)

        dispatchers_ids = list(User.objects.filter(company_instance=company, driver_info=None, owner_info=None).values_list('pk', flat=True))
        dispatchers_ids.append(company.pk)
        message = {
                'type': 'send_json',
                'content': {
                    'action': 'update_sms',
                    'data': content
                },
                'responded_users': dispatchers_ids
            }

        async_to_sync(self.channel_layer.group_send)(
            self.gen_group_name,
            message
        )
    
    def driver_connect(self, curr_user_id=None):
        message = {
            'type': 'send_json',
            'content': {
                'action': 'driver_connect',
                'data': {}
            },
            'responded_users': [curr_user_id]
        }
        
        async_to_sync(self.channel_layer.group_send)(
            self.gen_group_name,
            message
        )

    def driver_online_change(self, driver_id=0, is_online=False):
        message = {
            'type': 'send_json',
            'content': {
                'action': 'driver_online_change',
                'data': {
                    'id': driver_id,
                    'is_online': is_online
                }
            },
            'responded_users': '__all__'
        }
        
        async_to_sync(self.channel_layer.group_send)(
            self.gen_group_name,
            message
        )
    
    def send_json(self, content):
        curr_user_id = self.scope['user']
        cont = content['content']
        responded_users = content['responded_users']
        print('Send to ' + str(curr_user_id))
        print(responded_users)
        
        if responded_users == '__all__' or curr_user_id in set(responded_users):
            super().send(text_data=self.encode_json(cont))
    


# Не удаляю на всякий случай для обратной совместимости)

class ChatConsumer(WebsocketConsumer):
    def connect(self):
        self.group_id = self.scope['url_route']['kwargs']['id']
        self.room_group_name = 'chat_%s' % self.group_id

        async_to_sync(self.channel_layer.group_add)(
            self.room_group_name,
            self.channel_name
        )

        self.accept()

    def disconnect(self, close_code):
        async_to_sync(self.channel_layer.group_discard)(
            self.room_group_name,
            self.channel_name
        )

    def receive(self, text_data):
        user_from_id = self.scope['user']

        if user_from_id == None:
            return

        text_data_json = json.loads(text_data)

        content = text_data_json['content']
        # chat_id = text_data_json['chat_id']
        # media = text_data_json['media']
        chat_id = self.scope['url_route']['kwargs']['id']
        user_to = None
        chat_group = ChatGroup.objects.get(pk=chat_id)

        chat_initiator = chat_group.user_initiator.id
        chat_member = chat_group.user_member.id

        if chat_initiator == user_from_id and chat_member != user_from_id:
            user_to = User.objects.get(pk=chat_member) 
        elif chat_member == user_from_id and chat_initiator != user_from_id:
            user_to = User.objects.get(pk=chat_initiator)
        else:
            return

        user_from = User.objects.get(pk=user_from_id)
        new_message = Message.objects.create(user_from=user_from, user_to=user_to, chat_group=chat_group, content=content)

        async_to_sync(self.channel_layer.group_send)(
            self.room_group_name,
            {
                'type': 'chat_message',
                'modifiedDateTime': new_message.modifiedDateTime.isoformat(),
                'content': content,
                # 'media': media,
                'user_to': {
                    'id': user_to.id
                },
                'user_from': {
                    'id': user_from.id
                }
            }
        )

    def chat_message(self, event):
        content = event['content']
        modifiedDateTime = event['modifiedDateTime']
        # media = event['media']
        user_to = event['user_to']
        user_from = event['user_from']

        self.send(text_data=json.dumps({
            'modifiedDateTime': modifiedDateTime,
            'content': content,
            # 'media': media,
            'user_to': user_to,
            'user_from': user_from
        }))


class GroupChatConsumer(WebsocketConsumer):
    def connect(self):
        self.group_id = self.scope['url_route']['kwargs']['id']
        self.room_group_name = 'chat_%s' % self.group_id

        async_to_sync(self.channel_layer.group_add)(
            self.room_group_name,
            self.channel_name
        )

        self.accept()

    def disconnect(self, close_code):
        async_to_sync(self.channel_layer.group_discard)(
            self.room_group_name,
            self.channel_name
        )

    def receive(self, text_data):
        user_from_id = self.scope['user']

        if user_from_id == None:
            return

        text_data_json = json.loads(text_data)

        content = text_data_json['content']
        
        # chat_id = text_data_json['chat_id']
        chat_id = self.scope['url_route']['kwargs']['id']
        chat_group = None
        
        try:
            chat_group = Chat.objects.get(pk=chat_id, users=user_from_id)
        except:
            return
        

        user_from = User.objects.get(pk=user_from_id)
        new_message = ChatMessage.objects.create(user_from=user_from, chat_group=chat_group, content=content)

        msg = {
                'type': 'chat_message',
                'modifiedDateTime': new_message.modifiedDateTime.isoformat(),
                'content': content,
                'media': False,
                'user_from': {
                    'id': user_from.id,
                    'email': user_from.email,
                    'avatar': '/backend/api/media/' + str(user_from.avatar),
                    'role': user_from.role,
                    'first_name': user_from.first_name,
                    'last_name': user_from.last_name,
                    'last_online': str(user_from.last_online)
                }
            }

        if 'media' in text_data_json:
            media = text_data_json['media']
            files = File.objects.filter(id__in=media)
            files.update(message=new_message, chat=chat_group)

            msg['media'] = FileSerializer(files, many=True).data

        async_to_sync(self.channel_layer.group_send)(
            self.room_group_name,
            msg
        )
        
    def chat_message(self, event):
        content = event['content']
        modifiedDateTime = event['modifiedDateTime']
        user_from = event['user_from']
        media = event['media']

        self.send(text_data=json.dumps({
            'modifiedDateTime': modifiedDateTime,
            'content': content,
            'media': media,
            'user_from': user_from
        }))


class LoadsConsumer(WebsocketConsumer):
    def connect(self):
        self.group_id = 'loads'
        self.room_group_name = 'group_%s' % self.group_id

        async_to_sync(self.channel_layer.group_add)(
            self.room_group_name,
            self.channel_name
        )

        self.accept()

    def disconnect(self, close_code):
        async_to_sync(self.channel_layer.group_discard)(
            self.room_group_name,
            self.channel_name
        )

    def receive(self, text_data):
        user_id = self.scope['user']

        if user_id == None:
            return

        user = User.objects.get(pk=user_id)
        text_data_json = json.loads(text_data)

        if text_data_json['price'] == '':
            text_data_json['price'] = 0

        point_from = text_data_json['pickUpAt'].replace(' ', '%20')
        point_to = text_data_json['deliverTo'].replace(' ', '%20')
        text_data_json['approximate_time'] = 0

        bing_req = requests.get("http://dev.virtualearth.net/REST/v1/Routes?wp.1=" + point_from + "&wp.2=" + point_to + "&key=" + settings.BING_API_KEY)
        json_bing_req = json.loads(bing_req.text)

        if json_bing_req['statusCode'] == 200:
            if len(json_bing_resp['resourceSets'][0]['resources']) > 0:
                text_data_json['approximate_time'] = json_bing_req['resourceSets'][0]['resources'][0]['travelDuration']
        
        new_load = Load.objects.create(
            shipper=user,
            **text_data_json
        )

        async_to_sync(self.channel_layer.group_send)(
            self.room_group_name,
            {
                'type': 'new_load',
                "id": new_load.id,
                "shipper": new_load.shipper.first_name + ' ' + new_load.shipper.last_name,
                "modifiedDateTime": new_load.modifiedDateTime.isoformat(),
                "pickUpAt": new_load.pickUpAt,
                "deliverTo": new_load.deliverTo,
                "width": new_load.width,
                "height": new_load.height,
                "length": new_load.length,
                "weight": new_load.weight,
                "price": new_load.price,
                "car": new_load.car,
                "isDanger": new_load.isDanger,
                "isUrgent": new_load.isUrgent,
                "isCanPutOnTop": new_load.isCanPutOnTop,
                "status": "In search",
                "approximate_time": new_load.approximate_time
            }
        )

    def new_load(self, event):
        self.send(text_data=json.dumps(
            {
                "id": event['id'],
                "shipper": event['shipper'],
                "load_propositions": [],
                "modifiedDateTime": event['modifiedDateTime'],
                "pickUpAt": event['pickUpAt'],
                "deliverTo": event['deliverTo'],
                "width": event['width'],
                "height": event['height'],
                "length": event['length'],
                "weight": event['weight'],
                "price": event['price'],
                "car": event['car'],
                "isDanger": event['isDanger'],
                "isUrgent": event['isUrgent'],
                "isCanPutOnTop": event['isCanPutOnTop'],
                "status": "In search",
                "approximate_time": event['approximate_time']
            }
        ))      


class DriverBidsConsumer(WebsocketConsumer):
    def connect(self):
        self.group_id = self.scope['url_route']['kwargs']['group_id']
        self.room_group_name = 'chat_%s' % self.group_id

        async_to_sync(self.channel_layer.group_add)(
            self.room_group_name,
            self.channel_name
        )

        self.accept()

    def disconnect(self, close_code):
        async_to_sync(self.channel_layer.group_discard)(
            self.room_group_name,
            self.channel_name
        )

    def receive(self, text_data):
        user_from_id = self.scope['user']

        if user_from_id == None:
            return

        text_data_json = json.loads(text_data)

        load_id = text_data_json['load_id']
        phone_number = text_data_json['phone_number']

        async_to_sync(self.channel_layer.group_send)(
            self.room_group_name,
            {
                'type': 'bid',
                'load_id': load_id,
                'phone_number': phone_number
            }
        )

    def bid(self, event):
        load_id = event['load_id']
        phone_number = event['phone_number']

        self.send(text_data=json.dumps({
            'load_id': load_id,
            'phone_number': phone_number
        }))