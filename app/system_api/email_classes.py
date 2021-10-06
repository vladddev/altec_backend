from datetime import datetime, timedelta

from app.views import AppAuthClass

import smtplib, imaplib, email, re, time, base64, urllib.parse, os.path, pickle

from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework import generics, viewsets

from app.models import User
from app.serializers import *
from app.permissions import *
from app.pagination import *
from app.helpers.data_filters import *
from app.helpers.get_user_owner import get_user_owner
from app.helpers.send_email_by_smtp import SMTP

from api import settings

def is_base64(s):
    try:
        if base64.b64encode(base64.b64decode(s)) == s.encode('utf-8'):
            return True
        return False
    except Exception:
        return False

def get_first_text_block(email_message_instance):
    maintype = email_message_instance.get_content_maintype()
    if maintype == 'multipart':
        for part in email_message_instance.get_payload():
            if part.get_content_maintype() == 'text':
                return part.get_payload(decode=True).decode('utf-8')
    elif maintype == 'text':
        return email_message_instance.get_payload()


class LoadParser():
    mail = {
        'headers': None,
        'body': None
    }

    def set_mail(self, headers=None, body=None):
        self.mail['headers'] = headers
        self.mail['body'] = body

    def find(self, subj: str, reg: str, end_tag: str = 'br') -> str:
        reg_str = r'(' + reg + '\s?\??\s?:\s?.+?<\/?\s?' + end_tag + ')'
        full_str_group = re.search(reg_str, subj)

        if full_str_group == None:
            return ''

        full_str = full_str_group.group(0)
        clean_str = re.sub(r'(' + reg + '\s?\??\s?:\s?)', '', re.sub(r'<\/?\s?' + end_tag, '', full_str))

        return clean_str.strip()

    def find_text(self, subj: str) -> str:
        reg_str = r'(This posting expires).+?(ORDER NUMBER).+?(\<br\s?\/\>?)'
        full_str_group = re.search(reg_str, subj)

        if full_str_group == None:
            return ''

        full_str = full_str_group.group(0)

        return full_str.strip()

    def find_email(self, subj: str) -> str:
        reg_str = r'\S+@\S+'
        full_str_group = re.search(reg_str, subj)

        if full_str_group == None:
            return ''

        full_str = full_str_group.group(0).strip()
        return re.sub(r'\(|\)', '', full_str)

    def get_int_from_str(self, input_string: str) -> int:
        return int(re.findall(r'\d+', input_string)[0])

    def find_brokerage(self, subj: str) -> str:
        reg_str = r'((please contact)|(New Shipment Available))\s?\:\s?(\<br\s?\/\>?)?.+?((\<br\s?\/\>?)|(\<\/p\s?\>?))'
        full_str_group = re.search(reg_str, subj)

        if full_str_group == None:
            return ''

        full_str = full_str_group.group(0)
        clean_str = re.sub(r'((please contact)|(New Shipment Available))\s?\:\s?', '', re.sub(r'((\<br\s?\/\>?)|(\<\/p\s?\>?))', '', full_str))

        return clean_str.strip()

    def get_time_from_str(self, subj: str):
        if subj == None or subj == '':
            return None
        time_array = None
        type = '/' if (subj.find('/') != -1) else '.'
        
        if type == '/':
            time_array = subj.split('/')
        else:
            time_array = subj.split('.')

        end_part = time_array[2].split(' ')
        year = end_part[0]
        if type == '/':
            if int(time_array[1]) > 12:
                month = time_array[0]
                day = time_array[1]
            else:
                month = time_array[1]
                day = time_array[0]
        else:
            month = time_array[1]
            day = time_array[0]
            
        hour_minute = end_part[1].split(':')
        hour = hour_minute[0]
        minute = hour_minute[1]

        return year + '-' + month + '-' + day + 'T' + hour + ':' + minute
        # return datetime(int(year), int(month), int(day), int(hour), int(minute)) 

    def hide_email_n_price(self, subj: str) -> str:
        output = subj

        reg_str = r'\S+@\S+\.\S+'
        full_str_group = re.findall(reg_str, subj)
        for email_str in full_str_group:
            output = output.replace(email_str, '******@****.***')

        reg_str = r'\S*\$\S*'
        full_str_group = re.findall(reg_str, subj)
        for price_str in full_str_group:
            output = output.replace(price_str, '***$')

        return output.strip()

    def parse(self):
        dog_index = self.mail['headers']['From'].find('@')
        first_letter = self.mail['headers']['From'][dog_index + 1].upper()
        html = self.mail['body']
        reply_email = self.find_email(html)

        pick_up_date = self.get_time_from_str(self.find(html, 'Pick-up date \(EST\)').strip())
        delivery_date = self.get_time_from_str(self.find(html, 'Delivery date \(EST\)').strip())
        
        pick_up_at = self.find(html, 'Pick-up at').strip()
        deliver_to = self.find(html, 'Deliver to')
        urgent = self.find(html, 'FAST Load')
        car = self.find(html, 'Suggested Truck Size', '(br|p)')
        miles = float(self.find(html, 'Miles'))
        note = self.hide_email_n_price(self.find(html, 'Notes', 'p'))
        dims = self.find(html, 'Dims')                    

        pieces = self.find(html, 'Pieces') 
        pieces = 0 if (pieces == '') else self.get_int_from_str(pieces)

        items_count = self.find(html, 'No\.of items') 
        items_count = 1 if (items_count == '') else self.get_int_from_str(items_count)

        pallets = self.find(html, 'Pallets') 
        pallets = 0 if (pallets == '') else self.get_int_from_str(pallets)

        price = self.find(html, 'Price') 
        price = 0 if (price == 'Best Price' or price == '') else self.get_int_from_str(price)

        stackable = self.find(html, 'Stackable')
        stackable = True if (stackable == 'Yes' or stackable == 'Y') else False

        dangerous = self.find(html, 'Hazardous')
        dangerous = True if (dangerous == 'Yes' or dangerous == 'Y') else False

        urgent = self.find(html, 'FAST Load')
        urgent = True if (urgent == 'Yes' or urgent == 'Y') else False

        dock_level = self.find(html, 'Dock Level')
        dock_level = True if (dock_level == 'Yes' or dock_level == 'Y') else False

        wait_and_return = self.find(html, 'Wait and return')
        wait_and_return = True if (wait_and_return == 'Yes' or wait_and_return == 'Y') else False

        team = self.find(html, 'Team')
        team = True if (team == 'Yes' or team == 'Y') else False

        liftgate = self.find(html, 'Liftgate')
        liftgate = True if (liftgate == 'Yes' or liftgate == 'Y') else False

        company = '(' + first_letter + ') ' + self.find_brokerage(html)
        descr = self.find_text(html)

        approximate_time = round(time.strptime(self.find(html, 'Delivery date (EST)'), '%m/%d/%Y %H:%M').timestamp() - datetime.now().timestamp()) if (self.find(html, 'Delivery date (EST)') != "") else 0

        sys_ref = self.find(html, 'ORDER NUMBER')

        try:
            size = self.find(html, 'Dims').split('x')
            width = self.get_int_from_str(size[0])
            height = self.get_int_from_str(size[1])
            length = self.get_int_from_str(size[2])
        except:
            width = 0
            height = 0
            length = 0
        
        weight = self.find(html, 'Weight')

        mail_from = self.mail['headers']['From']

        if Load.objects.filter(removedDateTime=None, pickUpAt=pick_up_at, deliverTo=deliver_to, miles=miles, status=1).count() == 0 and Load.objects.filter(removedDateTime=None, sys_ref=sys_ref).count() == 0:                    
            new_load = Load.objects.create(
                pickUpAt=pick_up_at,
                pick_up_date=pick_up_date,
                deliverTo=deliver_to,
                width=width,
                height=height,
                length=length,
                weight=self.get_int_from_str(weight),
                broker_price=price,
                price=price,
                miles=miles,
                isDanger=dangerous,
                isUrgent=urgent,
                isCanPutOnTop=stackable,
                reply_email=reply_email,
                car=car,
                sys_ref=sys_ref,
                approximate_time=approximate_time,
                note=note,
                company=company,
                mail_part=descr,
                pieces=pieces,
                pallets=pallets,
                dock_level=dock_level,
                dims=dims,
                liftgate=liftgate,
                wait_and_return=wait_and_return,
                team=team,
                items_count=items_count,
                brokerage=mail_from
            )
            # Documents.objects.create(load=new_load)
            return True

        return False


class MailClient(AppAuthClass, viewsets.ViewSet):
    permission_classes = [IsAuthenticated]
    mail_to_address = ''
    mail_address = ''
    mail_password = ''
    mail_imap_host = ''
    mail_smtp_host = ''
    mail_subj = ''
    reply = None

    def get_test(self, request):
        user = request.user
        gmail = self.create_gmail(user.id)

        creds = None
        id = user.id
        if user.id == 108 or user.id == 199:
            id = 7

        output = {}
        if os.path.exists('tokens/token_' + str(id) + '.pickle'):
            with open('tokens/token_' + str(id) + '.pickle', 'rb') as token:
                creds = pickle.load(token)

                output = creds.__dict__

                # attrs = dir(creds)
                # for attr in attrs:
                #     output[attr] = str(getattr(creds, attr))

        # if creds:
        #     from googleapiclient.discovery import build
        #     from google.auth.transport.requests import Request
        #     if creds.expired and creds.refresh_token:
                
        #         creds.refresh(Request())
        #         with open('tokens/token_' + str(id) + '.pickle', 'wb') as token:
        #             pickle.dump(creds, token)

        return Response(output)

    def create_gmail(self, user_id):
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

    def decode_subj(self, subj):
        splitted_subj = subj.split('?')
        if len(splitted_subj) > 1 and splitted_subj[1] == 'UTF-8':
            if is_base64(splitted_subj[3]):
                return base64.b64decode(splitted_subj[3])
            
        return subj

    def decode_body(self, body):
        splitted_body = body.strip('\r\n').split('\r\n')
        output = list()
        return body

        for body_part in splitted_body:
            if body_part == splitted_body[0]:
                continue
            if is_base64(body_part):
                return body_part
                output.append(base64.b64decode(body_part).decode('utf-8'))
            else:
                # return ''
                output.append(body_part)
     
        return '\r\n'.join(output) 

    def send_system_email(self, request):
        user = request.user
        user_from = user.email
        user_to = None

        if 'user_to' in request.data:
            user_to = list(User.objects.get(id=request.data['user_to']).email)
        elif 'adress' in request.data:
            user_to = request.data['adress']
        else:
            return Response({
                'status': 'fail',
                'message': 'Empty adress'
            })

        mail_subj = "Message from Altek"
        if 'mail_subj' in request.data:
            mail_subj = request.data['mail_subj']

        if 'reply' in request.data:
            self.reply = request.data['reply']

        self.mail_to_address = user_to
        self.mail_address = settings.EMAIL_HOST_USER
        self.mail_password = settings.EMAIL_HOST_PASSWORD
        self.mail_smtp_host = settings.EMAIL_HOST
        self.mail_subj = mail_subj

        self.send_mail(request.data['content'])

        return Response({
            'status': 'ok'
        })

    def send_personal_email(self, request):
        user = request.user
        user_from = user.email
        user_to = None

        if 'user_to' in request.data:
            user_to = list(User.objects.get(id=request.data['user_to']).email)
        elif 'adress' in request.data:
            user_to = request.data['adress']
        else:
            return Response({
                'status': 'fail',
                'message': 'Empty adress'
            })
        
        mail_subj = "Message from " + user_from
        if 'mail_subj' in request.data:
            mail_subj = request.data['mail_subj']

        self.mail_to_address = user_to
        self.mail_address = 'ruslan-welbex-dev@yandex.ru'
        self.mail_password = 'vF%-3y_g$Vvzs!w'
        self.mail_smtp_host = 'smtp.yandex.com'
        self.mail_subj = mail_subj

        if 'reply' in request.data:
            self.reply = request.data['reply']

        gmail = self.create_gmail(user.id)

        if gmail != None:
            self.send_gmail(gmail, request.data['content'])
        else:
            self.send_mail(request.data['content'])

        return Response({
            'status': 'ok'
        })

    def send_company_email(self, request):
        user = request.user
        user_from = user.email
        user_company = user.company_instance
        user_to = None

        return Response({
            'status': 'fail',
            'message': 'Not realised yet'
        })

        if 'user_to' in request.data:
            user_to = list(User.objects.get(id=request.data['user_to']).email)
        elif 'adress' in request.data:
            user_to = request.data['adress']
        else:
            return Response({
                'status': 'fail',
                'message': 'Empty adress'
            })

        mail_subj = "Message from " + user_company.name
        if 'mail_subj' in request.data:
            mail_subj = request.data['mail_subj']

        if 'reply' in request.data:
            self.reply = request.data['reply']

        self.mail_to_address = user_to
        self.mail_address = user_company.company_mail_adress
        self.mail_password = user_company.company_mail_password
        self.mail_smtp_host = user_company.company_mail_host
        self.mail_subj = mail_subj

        gmail = self.create_gmail(0)

        if gmail != None:
            self.send_gmail(gmail, request.data['content'])
        else:
            self.send_mail(request.data['content'])

        return Response({
            'status': 'ok'
        })

    def get_personal_emails(self, request):
        user = request.user

        gmail = self.create_gmail(user.id)

        if gmail != None:
            output = self.get_gmails(request, gmail)
        else:
            user_email = user.email
            user_password = user.private_email_password
            user_domain = user.private_email_domain
            user_port = user.private_email_port

            # user_email = 't-welbex@yandex.ru'
            # user_password = '1234user'
            # user_domain = 'imap.yandex.com'
            # user_port = 993

            self.mail_address = 'ruslan-welbex-dev@yandex.ru'
            self.mail_password = 'vF%-3y_g$Vvzs!w'
            self.mail_imap_host = 'imap.yandex.com'

            output = self.get_mails(request)

        return Response(output)

    def get_company_emails(self, request):
        user = request.user
        get = request.query_params
        user_from = user.email
        user_company = user.company_instance

        return Response({
            'status': 'fail',
            'message': 'Not realised yet'
        })

        gmail = self.create_gmail(0)

        if gmail != None:
            output = self.get_gmails(request, gmail)
        else:
            self.mail_address = user_company.company_mail_adress
            self.mail_password = user_company.company_mail_password
            self.mail_imap_host = user.private_email_domain

            output = self.get_mails(request)

        return Response(output)
    
    def get_system_emails(self, request):
        self.mail_address = settings.EMAIL_HOST_USER
        self.mail_password = settings.EMAIL_HOST_PASSWORD
        self.mail_imap_host = 'imap.yandex.ru'

        output = self.get_mails(request)

        return Response(output)
    
    def get_mails(self, request):
        user = request.user
        get = request.query_params

        user_email = self.mail_address
        user_password = self.mail_password
        user_domain = self.mail_imap_host

        mail = imaplib.IMAP4_SSL(user_domain)
        mail.login(user_email, user_password)
        search_query = list()

        # return mail.list()

        if 'date_from' in get and 'date_to' in get:
            search_query.append("(SINCE {0})".format(datetime.utcfromtimestamp(int(get['date_from'])).strftime("%d-%b-%Y")))
            search_query.append("(BEFORE {0})".format(datetime.utcfromtimestamp(int(get['date_to'])).strftime("%d-%b-%Y")))
        elif 'type' in get and get['type'] == 'full':
            search_query.append("ALL")
        else:
            search_query.append("(SINCE {0})".format(time.strftime("%d-%b-%Y")))

        if 'search_from' in get:
            search_query.append('(FROM "' + urllib.parse.unquote(get['search_from']) + '")')

        if 'search_subj' in get:
            search_query.append('(SUBJECT "' + urllib.parse.unquote(get['search_subj']) + '")')
        
        mail.select('INBOX')
        result, data = mail.search(None, *search_query)

        mail_from = 0
        mail_to = 100

        if 'mail_from' in get:
            mail_from = int(get['mail_from'])

        if 'mail_to' in get:
            mail_to = int(get['mail_to'])

        output = list()
        for num in data[0].split()[mail_from:mail_to]:
            typ, message_data = mail.fetch(num, '(RFC822)')
            raw_email = message_data[0][1]
            raw_email_string = raw_email.decode('utf-8')
            email_message = email.message_from_string(raw_email_string)
            mail_from_address = email.utils.parseaddr(email_message['From'])
            mail_to_address = email.utils.parseaddr(email_message['To'])

            email_from_addr = mail_from_address[1]
            if email_from_addr == user_email:
                email_from_addr = 'self'

            email_to_addr = mail_to_address[1]
            if email_to_addr == user_email:
                email_to_addr = 'self'

            mail_struct = {
                'num': num,
                'from': email_from_addr,
                'to': email_to_addr,
                'date': email_message['Date'],
                'id': email_message['Message-ID'].replace("<", "").replace(">", ""),
                'subject': self.decode_subj(email_message['Subject'])
            }

            if 'type' in get and get['type'] == 'full':
                try:
                    mail_struct['body'] = email_message.get_payload(decode=True).decode('utf-8')
                except:
                    mail_struct['body'] = get_first_text_block(email_message)
                    # mail_struct['body'] = self.decode_body(email_message.get_payload()[0].get_payload())
            
            output.append(mail_struct)

        mail.select('Sent')
        result, data = mail.search(None, *search_query)

        for num in data[0].split()[mail_from:mail_to]:
            typ, message_data = mail.fetch(num, '(RFC822)')
            raw_email = message_data[0][1]
            raw_email_string = raw_email.decode('utf-8')
            email_message = email.message_from_string(raw_email_string)
            mail_from_address = email.utils.parseaddr(email_message['From'])
            mail_to_address = email.utils.parseaddr(email_message['To'])

            email_from_addr = mail_from_address[1]
            if email_from_addr == user_email:
                email_from_addr = 'self'

            email_to_addr = mail_to_address[1]
            if email_to_addr == user_email:
                email_to_addr = 'self'

            mail_struct = {
                'num': num,
                'from': email_from_addr,
                'to': email_to_addr,
                'date': email_message['Date'],
                'id': email_message['Message-ID'].replace("<", "").replace(">", ""),
                'subject': self.decode_subj(email_message['Subject'])
            }

            if 'type' in get and get['type'] == 'full':
                try:
                    mail_struct['body'] = email_message.get_payload(decode=True).decode('utf-8')
                except:
                    mail_struct['body'] = get_first_text_block(email_message)
                    # mail_struct['body'] = self.decode_body(email_message.get_payload()[0].get_payload())

            output.append(mail_struct)

            # 'date': datetime.strptime(email_message['Date'], '%a, %d %b %Y %H:%M:%S %z'),

        mail.close()
        mail.logout()

        return output

    def get_gmails(self, request, gmail):
        user = request.user
        get = request.query_params

        query_str = ''
        if 'date_from' in get and 'date_to' in get:
            query_str += 'before:{0} '.format(datetime.utcfromtimestamp(int(get['date_to'])).strftime("%d/%m/%Y"))
            query_str += 'after:{0} '.format(datetime.utcfromtimestamp(int(get['date_from'])).strftime("%d/%m/%Y"))

        if 'search_from' in get:
            query_str += 'from:{0} '.format(urllib.parse.unquote(get['search_from']))

        if 'search_subj' in get:
            query_str += 'subject:{0} '.format(urllib.parse.unquote(get['search_subj']))

        results = gmail.users().messages().list(
            userId='me',
            maxResults=10,
            q=query_str
        ).execute()

        messages = results.get('messages', [])
        output = []

        for message in messages:
            mail = gmail.users().messages().get(userId='me', id=message['id']).execute()
            
            payload = mail.get('payload')
            headers = {}
            for header in payload['headers']:
                headers[header['name']] = header['value']
            mail_struct = {
                'num': message['id'],
                'from': headers['From'],
                'to': headers['To'],
                'date': headers['Date'],
                'id': message['id'],
                'subject': headers['Subject'],
                'body': parse_msg(mail)
            }

            output.append(mail_struct)

        return output

    def get_selected_email(self, request):
        user = request.user
        user_email = self.mail_address
        user_password = self.mail_password
        user_domain = self.mail_imap_host

        mail = imaplib.IMAP4_SSL(user_domain, user_port)
        mail.login(user_email, user_password)
        num = request.query_params['num']
        
        mail.select('INBOX')
        typ, message_data = mail.fetch(num, '(RFC822)')

        raw_email = message_data[0][1]
        raw_email_string = raw_email.decode('utf-8')
        email_message = email.message_from_string(raw_email_string)
        mail_from = email.utils.parseaddr(email_message['From'])
        mail_to = email.utils.parseaddr(email_message['To'])
        body = email_message.get_payload(decode=True).decode('utf-8')
        
        mail.store(num, '+FLAGS', '\\Seen')
        mail.expunge()
        mail.close()
        mail.logout()

        output = {
            'num': request.query_params['num'],
            'from': mail_from[1],
            'to': mail_to[1],
            'date': email_message['Date'],
            'subject': self.decode_subj(email_message['Subject']),
            'body': self.decode_body(body)
        }
        return Response(output)

    def get_selected_gmail(self, request, gmail):
        user = request.user
        get = request.query_params

        mail = gmail.users().messages().get(userId='me', id=get['num']).execute()
        payload = mail.get('payload')
        headers = {}
        for header in payload['headers']:
            headers[header['name']] = header['value']

        mail_struct = {
            'num': message['id'],
            'from': headers['From'],
            'to': headers['To'],
            'date': headers['Date'],
            'id': message['id'],
            'subject': headers['Subject'],
            'body': parse_msg(mail)
        }
        return Response(output)

    def send_mail(self, content = ''):
        smtpObj = smtplib.SMTP(self.mail_smtp_host)
        smtpObj.ehlo()
        smtpObj.starttls()
        smtpObj.ehlo()
        smtpObj.login(self.mail_address, self.mail_password)

        adresses_list = self.mail_to_address
        adresses_list.append(self.mail_address)
        
        headers = (
            "From: %s" % self.mail_address,
            "To: %s" % ','.join(adresses_list),
            "Subject: %s" % self.mail_subj ,
            "",
            content
        )

        if self.reply != None:
            headers = (
                "From: %s" % self.mail_address,
                "To: %s" % self.mail_to_address,
                "Subject: RE: %s" % self.mail_subj.replace("Re: ", "").replace("RE: ", ""),
                "In-Reply-To: %s" % self.reply,
                "References: %s" % self.reply,
                "",
                content
            )

        BODY = "\r\n".join(headers)

    
        smtpObj.sendmail(self.mail_address, adresses_list, BODY)
        smtpObj.quit()

    def send_gmail(self, gmail, content=''):
        from email.mime.multipart import MIMEMultipart
        from email.mime.text import MIMEText

        msg = MIMEMultipart('alternative')

        adresses_list = self.mail_to_address
        adresses_list.append(self.mail_address)
        msg['Subject'] = self.mail_subj
        msg['From'] = self.mail_address
        msg['To'] = ','.join(adresses_list)
        
        if self.reply != None:
            msg['Subject'] = "RE: " + self.mail_subj.replace("Re: ", "").replace("RE: ", "")
            msg['To'] = self.mail_to_address
            msg['In-Reply-To'] = self.reply
            msg['References'] = self.reply

        msg.attach(MIMEText(content, 'plain'))
        msg.attach(MIMEText(content, 'html'))

        body = {'raw': base64.urlsafe_b64encode(msg.as_string())}

        gmail.users().messages().send(userId='me', body=body).execute()


class LoadsParse(AppAuthClass, LoadParser, viewsets.ViewSet):
    permission_classes = []

    def parse(self, request):
        if 'push' not in request.query_params:
            return Response()
            
        before_two_days = datetime.now() - timedelta(minutes=120)
        loads = Load.objects.filter(removedDateTime=None, created_date__lte=before_two_days, status=1, substatus=1, resp_driver=None).delete()

        # return Response(dict(
        #             result="User id doesn\`t exist"
        #         )) 

        if 'user_id' in request.query_params:
            user_id = request.query_params['user_id']
            user = None

            try:
                user = User.objects.get(id=user_id)
                result = user
            except:
                return Response(dict(
                    result="User doesn\`t exist"
                ))  
            
            mail = imaplib.IMAP4_SSL(user.company_instance.parsing_domain, user.company_instance.parsing_port)
            # mail = imaplib.IMAP4_SSL("imap.yandex.com", "993")
            mail.login(user.company_instance.parsing_email, user.company_instance.parsing_password)
            # mail.login("t-welbex@yandex.ru", "1234user")
            
            mail.select('INBOX')

            counter = 0

            result, data = mail.search(None, "(SINCE {0})".format(time.strftime("%d-%b-%Y")), 'UNSEEN')
            # result, data = mail.search(None, "(SINCE {0})".format(datetime.utcfromtimestamp(1603655922).strftime("%d-%b-%Y")), 'UNSEEN')
      
            for num in data[0].split():
                typ, message_data = mail.fetch(num, '(RFC822)')
                raw_email = message_data[0][1]
                raw_email_string = raw_email.decode('utf-8')
                email_message = email.message_from_string(raw_email_string)

                mail_from = email.utils.parseaddr(email_message['From'])

                # if "postedloads@sylectus.com" == mail_from[1] or "loads@myvirtualfleet.com" == mail_from[1]:  
                body = email_message.get_payload(decode=True).decode('utf-8')  
                html = re.sub(r'=[\n\r\t]', '', body)
                html = re.sub(r'\n', '', re.sub(r'=[\n\r\t]', '', body))
                first_letter = ''
                
                if "postedloads@sylectus.com" in mail_from[1]:
                    first_letter = 'S'
                elif "loads@myvirtualfleet.com" in mail_from[1]:
                    first_letter = 'M'
                else: 
                    from_mail = mail_from[1][0]
                    dog_index = from_mail.find('@')
                    first_letter = from_mail[dog_index + 1].upper()

                    
                reply_email = self.find_email(html)

                pick_up_date = self.get_time_from_str(self.find(html, 'Pick-up date \(EST\)').strip())
                delivery_date = self.get_time_from_str(self.find(html, 'Delivery date \(EST\)').strip())
                
                pick_up_at = self.find(html, 'Pick-up at').strip()
                deliver_to = self.find(html, 'Deliver to')
                urgent = self.find(html, 'FAST Load')
                car = self.find(html, 'Suggested Truck Size', '(br|p)')
                miles = float(self.find(html, 'Miles'))
                note = self.hide_email_n_price(self.find(html, 'Notes', 'p'))
                dims = self.find(html, 'Dims')                    

                pieces = self.find(html, 'Pieces') 
                pieces = 0 if (pieces == '') else self.get_int_from_str(pieces)

                items_count = self.find(html, 'No\.of items') 
                items_count = 1 if (items_count == '') else self.get_int_from_str(items_count)

                pallets = self.find(html, 'Pallets') 
                pallets = 0 if (pallets == '') else self.get_int_from_str(pallets)

                price = self.find(html, 'Price') 
                price = 0 if (price == 'Best Price' or price == '') else self.get_int_from_str(price)

                stackable = self.find(html, 'Stackable')
                stackable = True if (stackable == 'Yes' or stackable == 'Y') else False

                dangerous = self.find(html, 'Hazardous')
                dangerous = True if (dangerous == 'Yes' or dangerous == 'Y') else False

                urgent = self.find(html, 'FAST Load')
                urgent = True if (urgent == 'Yes' or urgent == 'Y') else False

                dock_level = self.find(html, 'Dock Level')
                dock_level = True if (dock_level == 'Yes' or dock_level == 'Y') else False

                wait_and_return = self.find(html, 'Wait and return')
                wait_and_return = True if (wait_and_return == 'Yes' or wait_and_return == 'Y') else False

                team = self.find(html, 'Team')
                team = True if (team == 'Yes' or team == 'Y') else False

                liftgate = self.find(html, 'Liftgate')
                liftgate = True if (liftgate == 'Yes' or liftgate == 'Y') else False

                company = '(' + first_letter + ') ' + self.find_brokerage(html)
                descr = self.find_text(html)

                approximate_time = round(time.strptime(self.find(html, 'Delivery date (EST)'), '%m/%d/%Y %H:%M').timestamp() - datetime.now().timestamp()) if (self.find(html, 'Delivery date (EST)') != "") else 0

                sys_ref = self.find(html, 'ORDER NUMBER')

                try:
                    size = self.find(html, 'Dims').split('x')
                    width = self.get_int_from_str(size[0])
                    height = self.get_int_from_str(size[1])
                    length = self.get_int_from_str(size[2])
                except:
                    width = 0
                    height = 0
                    length = 0
                
                weight = self.find(html, 'Weight')

                mail.store(num, '+FLAGS', '\Seen')


                if Load.objects.filter(removedDateTime=None, pickUpAt=pick_up_at, deliverTo=deliver_to, miles=miles, status=1).count() == 0 and Load.objects.filter(removedDateTime=None, sys_ref=sys_ref).count() == 0:                    
                    new_load = Load.objects.create(pickUpAt=pick_up_at,
                                        pick_up_date=pick_up_date,
                                        deliverTo=deliver_to,
                                        width=width,
                                        height=height,
                                        length=length,
                                        weight=self.get_int_from_str(weight),
                                        broker_price=price,
                                        price=price,
                                        miles=miles,
                                        isDanger=dangerous,
                                        isUrgent=urgent,
                                        isCanPutOnTop=stackable,
                                        reply_email=reply_email,
                                        car=car,
                                        sys_ref=sys_ref,
                                        approximate_time=approximate_time,
                                        note=note,
                                        company=company,
                                        mail_part=descr,
                                        pieces=pieces,
                                        pallets=pallets,
                                        dock_level=dock_level,
                                        dims=dims,
                                        liftgate=liftgate,
                                        wait_and_return=wait_and_return,
                                        team=team,
                                        items_count=items_count,
                                        brokerage=mail_from[1]
                                        )
                    # Documents.objects.create(load=new_load)
                    counter = counter + 1

            mail.expunge()
            mail.close()
            mail.logout()

            # if counter > 1:
            #     with websockets.connect("wss://green-node.ru/ws/company/0") as ws:
            #         ws.send('{"action": "update_loads"}')
            #         ws.recv()

            return Response(dict(
                    result="Loads count: " + str(counter)
                )) 

        else:
            return Response(dict(
                    result="User id doesn\`t exist"
                )) 









