import re, base64

def phone_filter(phone_number: str, country_code: str = ''):
    if not phone_number:
        return ''
    
    # clean_number = re.sub(r'\s|\(|\)|\-', '', phone_number)
    clean_number = re.sub(r'[^0-9\+]', '', phone_number)

    if clean_number[0] != '+' and len(clean_number) > 9:
        if len(clean_number) == 11:
            clean_number = '+' + clean_number
        else:
            clean_number = '+' + country_code + clean_number

    return clean_number


def parse_msg(msg):
    if msg.get("payload").get("body").get("data"):
        return base64.urlsafe_b64decode(msg.get("payload").get("body").get("data").encode("ASCII")).decode("utf-8")
    return msg.get("snippet")
    

def time_transform(timestamp, time_unit='min'):
    output = str(timestamp) + time_unit
    minutes_time = ''
    hours_time = ''
    days_time = ''
    hours = 0
    days = 0

    if time_unit == 'min':
        hours = round(timestamp / 60)
        minutes_time = ' ' + str(timestamp % 60) + 'min'
        hours_time = str(hours) + 'h'
    elif time_unit == 'h':
        hours = time_unit
        hours_time = str(hours) + 'h'

    if hours < 1:
        return output
    elif hours > 24:
        days = round(hours / 24)
        hours_less = hours % 24
        days_time = str(days) + 'd '
        hours_time = str(hours_less) + 'h'

    return days_time + hours_time + minutes_time


def add_zero(num):
    if len(num) == 1:
        return '0' + num
    else:
        return num


def reformatting_date_for_hr(wrong_date):
    output = ''
    data_arr = wrong_date.split('/')
    output = data_arr[2] + '-' + add_zero(data_arr[0]) + '-' + add_zero(data_arr[1])

    return output


def reformatting_date_for_email(wrong_date):
    output = ''
    if len(wrong_date) < 16:
        return wrong_date
    year = wrong_date[0:3]
    month = wrong_date[5:6]
    day = wrong_date[8:9]
    hour = wrong_date[11:12]
    minute = wrong_date[14:15]
    output = year + '-' + month + '-' + day + ' ' + hour + ':' + minute

    return output


def separate_location(location):
    output = {
        'zip': '',
        'city': '',
        'state': ''
    }

    zip_reg = r'[0-9]{5,6}'
    zips = re.search(zip_reg, location)
    if zips != None:
        zip = zips.group(0)
        city_state = location.replace(zip, '').strip().split(',')

        output['zip'] = zip
        output['city'] = city_state[0].strip()
        output['state'] = city_state[1].strip() if len(city_state) > 1 else ''
    else:
        output['city'] = location
    
    return output

