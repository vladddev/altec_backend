import smtplib
from datetime import datetime
from api import settings

class SMTP():
    login = None
    password = None
    domain = None
    port = None
    smtpObj = None

    def __init__(self, login, password, domain, port):
        self.login = login
        self.domain = domain
        self.password = password
        self.port = port

    def send_mail(self, mail_from, mail_to, body):
        smtpObj = smtplib.SMTP(self.domain, self.port, timeout=10)
        smtpObj.ehlo()
        smtpObj.starttls()
        smtpObj.ehlo()
        smtpObj.login(self.login, self.password)

        smtpObj.sendmail(mail_from, [mail_to], body)

        smtpObj.quit()



def send_emails_for_loads(type="location_update", loads=None):
    from email.mime.multipart import MIMEMultipart
    from email.mime.text import MIMEText

    content = ""

    if type == "status_update":
        with open('email_load_notification.html') as email_template:
            content = email_template.read()
    elif type == "location_update":
        with open('email_load_notification.html') as email_template:
            content = email_template.read()

    mail_address = settings.EMAIL_HOST_USER
    mail_password = settings.EMAIL_HOST_PASSWORD
    mail_smtp_host = settings.EMAIL_HOST
    
    smtpObj = smtplib.SMTP(mail_smtp_host, 587)
    smtpObj.ehlo()
    smtpObj.starttls()
    smtpObj.ehlo()
    try:
        smtpObj.login(mail_address, mail_password)
    except:
        return

    
    
    for load in loads:
        brokerage, location_update_emails, sys_ref, coordinates, location, update_on = load

        if location_update_emails == '':
            continue

        try:
            content = content.replace('[[ref]]', sys_ref).replace('[[location]]', location).replace('[[coordinates]]', coordinates).replace('[[update_on]]', update_on.strftime("%Y-%m-%d-%H.%M.%S"))
        except:
            continue
        
        mail_subj = "Location update for " + sys_ref

        # brokerage = find_email(brokerage)
        adress_to = location_update_emails.split('|')
        # adress_to = 'lukashov9182@gmail.com'

        msg = MIMEMultipart('alternative')
        msg['Subject'] = mail_subj
        msg['From'] = mail_address
        msg['To'] = ','.join(adress_to)

        part = MIMEText(content, 'html')
        msg.attach(part)
        smtpObj.sendmail(mail_address, adress_to, msg.as_string())
        
    smtpObj.quit()
    