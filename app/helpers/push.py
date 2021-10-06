def send_push(data_message = {}, tokens = None, group = None, push_type='background', priority='hight', sound=False):
    import requests
    from pyfcm import FCMNotification

    push_service = FCMNotification(api_key = "AAAAFeVVz7Q:APA91bG6pwbeqc9Q0dSq3vwCrLKvZ7pM8_M52Xofb9luz-4qNsg0bUjpvWTXkN54rSYFkdEgC8tWXJAQkIqWKG_KAKcII68rvzpRwRMX2ow-ofwnsLnadh8tsEvvwGAUJ_ud_rvfkZJy")
    if tokens != None:
        tokens = push_service.clean_registration_ids(tokens)
    # if tokens == None:
    #     push_service.notify_topic_subscribers(topic_name = "all", data_message = data_message)
    # elif isinstance(tokens, str):
    #     push_service.notify_single_device(registration_id = (tokens), data_message = data_message)
    # elif isinstance(tokens, list):
    #     push_service.notify_multiple_devices(registration_ids = tokens, data_message = data_message)


    url = 'https://fcm.googleapis.com/fcm/send'
    headers = {
        'Authorization': 'key=AAAAFeVVz7Q:APA91bG6pwbeqc9Q0dSq3vwCrLKvZ7pM8_M52Xofb9luz-4qNsg0bUjpvWTXkN54rSYFkdEgC8tWXJAQkIqWKG_KAKcII68rvzpRwRMX2ow-ofwnsLnadh8tsEvvwGAUJ_ud_rvfkZJy',
    }

    data_message['content_available'] = True
    data_message['priority'] = priority
    
    data = {
        "notification": {
            "body": data_message['body'],
            "title": data_message['title'],
            "content_available": data_message['content_available'],
            "priority": priority
        },
        "priority": 10,
        "data": data_message,
        "apns": {
            "headers": {
                "apns-push-type": push_type,
                "apns-priority": 10
            },
            "payload": {
                "aps": {
                    "contentAvailable": True
                }
            }
        }
    }

    if sound:
        data['notification']['sound'] = 'default'
        data['data']['sound'] = 'default'

    if tokens == None:
        data['to'] = group
        data['notification']['tag'] = 'location'
    else:
        data['registration_ids'] = tokens

    response = requests.post(url, headers=headers, json=data)
    