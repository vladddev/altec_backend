from datetime import datetime
from django.urls import path
from django.contrib import admin
from django.conf.urls import url, include
from django.conf.urls.static import static

from rest_framework_jwt.views import refresh_jwt_token
from rest_framework import routers, serializers, viewsets
# from rest_framework_simplejwt.views import TokenObtainPairView, TokenRefreshView
from app import views
from app.mobile_api import mobile_api
from app.system_api import email_classes, get_menu, other, statuses, bonus_system
from api import settings



urlpatterns = [
    path('backend/api/admin/', admin.site.urls),
    path('backend/api/social/', include('authentication.urls')),

    # path('backend/api/auth/', include('djoser.urls')),
    # path('backend/api/auth-token/', include('djoser.urls.jwt')),
    # path('backend/api/token/', TokenObtainPairView.as_view(), name='token_obtain_pair'),
    # path('backend/api/token/refresh/', refresh_jwt_token, name='token_refresh'),

    path('backend/api/driver-chat/<int:pk>/', views.DriverChatView.as_view()),
    path('backend/api/broker-chat/<int:pk>/', views.BrokerChatView.as_view()),
    url(r'backend/api/sms/brokers', views.BrokersList.as_view()),
    url(r'backend/api/sms/all', views.TwilioMessagesView.as_view({'post': 'post'})),
    url(r'backend/api/sms/new', views.TwilioMessagesView.as_view({'post': 'post'})),

    url(r'^backend/api/users/all', views.UserList.as_view()),
    url(r'^backend/api/users/firms', views.FirmsView.as_view()),
    url(r'^backend/api/users/my', views.MyUserList.as_view()),
    url(r'^backend/api/users/add', views.DispatcherAdd.as_view()),
    url(r'^backend/api/users/drivers/update', views.DriversUpdateView.as_view({'post': 'update'})),
    url(r'^backend/api/users/drivers', views.DriversView.as_view()),
    path('backend/api/users/<int:pk>/online/', views.UserOnlineHistory.as_view()),
    path('backend/api/users/<int:pk>/', views.UserDetails.as_view()),
    url(r'^backend/api/users/current/update', views.CurrentUserDetail.as_view()),

    # path('backend/api/users/current/chat-groups/<int:pk>/', views.UserChat.as_view()),
    # url(r'^backend/api/users/current/chat-groups', views.UserChatGroups.as_view()),

    path('backend/api/users/current/chats/<int:pk>/', views.RetrieveChat.as_view()),
    url(r'^backend/api/users/current/chats', views.UserChats.as_view()),

    path('backend/api/users/current/working-groups/<int:pk>/', views.WorkingGroupsDetail.as_view()),
    url(r'^backend/api/users/current/working-groups', views.WorkingGroups.as_view()),
    url(r'^backend/api/users/current', views.CurrentUserDetail.as_view()),

    url(r'^backend/api/owners/my', views.CarOwnersView.as_view()),
    path('backend/api/owners/<int:pk>/', views.CarOwnerDetail.as_view()),

    path('backend/api/driver-statuses/<int:pk>/', statuses.DriversStatusDetails.as_view()),
    url(r'^backend/api/driver-statuses', statuses.DriversStatusesList.as_view()),
    path('backend/api/load-statuses/<int:pk>/', statuses.LoadStatusDetails.as_view()),
    url(r'^backend/api/load-statuses', statuses.LoadStatusesList.as_view()),
    path('backend/api/load-substatuses/<int:pk>/', statuses.LoadSubStatusDetails.as_view()),
    url(r'^backend/api/load-substatuses', statuses.LoadSubStatusesList.as_view()),
    path('backend/api/car-statuses/<int:pk>/', statuses.CarStatusDetails.as_view()),
    url(r'^backend/api/car-statuses', statuses.CarStatusesList.as_view()),
    path('backend/api/bookkeeping-statuses/<int:pk>/', statuses.BookkeepingStatusDetails.as_view()),
    url(r'^backend/api/bookkeeping-statuses', statuses.BookkeepingStatusesList.as_view()),
    url(r'^backend/api/bookkeeping/data', views.BookkeepingView.as_view({'get': 'data', 'post': 'change_statuses'})),

    path('backend/api/bonus-sustem/bonus/<int:pk>/', bonus_system.DriverBonusDetails.as_view()),
    url(r'^backend/api/bonus-sustem/bonus', bonus_system.DriverBonusesList.as_view()),
    path('backend/api/bonus-sustem/fine/<int:pk>/', bonus_system.DriverFineDetails.as_view()),
    url(r'^backend/api/bonus-sustem/fine', bonus_system.DriverFinesList.as_view()),

    url(r'^backend/api/users/requests/all', views.RegistrationRequestView.as_view({'get': 'list'})),
    url(r'^backend/api/users/requests/result', views.RegistrationRequestView.as_view({'post': 'result'})),
    url(r'^backend/api/users/requests/add', views.RegistrationRequestView.as_view({'post': 'add'})),

    path('backend/api/bonus-sustem/fine/<int:pk>/', views.CallDetail.as_view()),
    path('backend/api/calls/<int:pk>/', views.CallDetail.as_view()),
    url(r'^backend/api/calls', views.CallsList.as_view()),

    url(r'^backend/api/chat-message', views.ChatMessageView.as_view()),
    
    url(r'^backend/api/loads/create', views.LoadCreate.as_view()),
    url(r'^backend/api/loads/pubsub-create', views.PubSubLoadCreate.as_view({'post': 'post'})),
    url(r'^backend/api/loads/get-from-gmail', email_classes.LoadsParse.as_view({'get': 'parse'})),
    url(r'^backend/api/loads/all', views.LoadList.as_view()),
    url(r'^backend/api/loads/our', views.OurLoadList.as_view()),
    url(r'^backend/api/loads/completed', views.LoadHistoryList.as_view()),
    path('backend/api/loads/<int:pk>/', views.LoadDetail.as_view()),

    url(r'^backend/api/cars/all', views.CarsList.as_view()),
    url(r'^backend/api/cars/my', views.CarsList.as_view()),
    url(r'^backend/api/cars/update', views.CarsUpdateView.as_view({'post': 'update'})),
    url(r'^backend/api/cars/actual', views.CarsList.as_view()),
    url(r'^backend/api/cars/add', views.CarCreate.as_view()),
    path('backend/api/cars/<int:pk>/', views.CarDetail.as_view()),

    url(r'^backend/api/cars/map', views.LoadsMap.as_view({'get': 'get'})),

    url(r'^backend/api/propositions/add', views.PropositionList.as_view()),
    url(r'^backend/api/propositions/all', views.PropositionList.as_view()),
    path('backend/api/propositions/<int:pk>/', views.PropositionDetail.as_view()),

    url(r'backend/api/bids', views.BidsView.as_view({'get': 'get_bids', 'post': 'update_bids'})),

    url(r'backend/api/notifications/update-all', views.NoticeUpdate.as_view({'post': 'mark_as_read'})),
    url(r'backend/api/notifications/check-all', views.NoticeUpdate.as_view({'post': 'mark_as_read_entity'})),
    url(r'backend/api/notifications/all', views.NoticeList.as_view()),
    path('backend/api/notifications/<int:pk>/', views.NoticeDetail.as_view()),
    path('backend/api/action/<int:pk>/', views.UserActionDetail.as_view()),
    url(r'backend/api/actions/all', views.ActionsList.as_view()),

    path('backend/api/companies/<int:pk>/', views.CompanyDetail.as_view()),
    url(r'backend/api/companies', views.CompaniesList.as_view()),

    url(r'^backend/api/mail-client/test', email_classes.MailClient.as_view({'get': 'get_test'})),
    url(r'^backend/api/mail-client/personal', email_classes.MailClient.as_view({'get': 'get_personal_emails', 'post': 'send_personal_email'})),
    url(r'^backend/api/mail-client/personal/get-mail', email_classes.MailClient.as_view({'get': 'get_personal_selected_email'})),
    url(r'^backend/api/mail-client/company', email_classes.MailClient.as_view({'get': 'get_company_emails', 'post': 'send_company_email'})),
    url(r'^backend/api/mail-client/company/get-mail', email_classes.MailClient.as_view({'get': 'get_company_selected_email'})),
    url(r'^backend/api/mail-client/system', email_classes.MailClient.as_view({'get': 'get_system_emails', 'post': 'send_system_email'})),
    url(r'^backend/api/mail-client/system/get-mail', email_classes.MailClient.as_view({'get': 'get_system_selected_email'})),
    url(r'^backend/api/gmail/logout', other.GmailAuth.as_view({'get': 'logout'})),
    url(r'^backend/api/gmail', other.GmailAuth.as_view({'get': 'auth'})),

    url(r'^backend/api/dashboard', other.DashboardView.as_view({'get': 'list'})),
    url(r'^backend/api/heart', other.Heartbeat.as_view({'get': 'beat'})),
    url(r'^backend/api/settings', views.SettingsView.as_view()),
    url(r'^backend/api/get-menu', get_menu.GenerateMenuList.as_view({'get': 'get'})),
    url(r'^backend/api/upload-docs', other.LoadFileUploadView.as_view()),
    url(r'^backend/api/upload', other.FileUploadView.as_view()),
    path('backend/api/files/<int:pk>/', other.FileDetail.as_view()),
    path('backend/api/tutorials/<int:pk>/', other.TutorialDetail.as_view()),
    url(r'backend/api/tutorials/create', other.TutorialCreateView.as_view()),
    url(r'backend/api/tutorials', other.TutorialUploadView.as_view()),

    path('backend/api/roles/<int:pk>/', other.CompanyRolesView.as_view({'get': 'get_role', 'post': 'update_role', 'delete': 'delete_role'})),
    url(r'^backend/api/roles', other.CompanyRolesView.as_view({'get': 'get_roles', 'post': 'create_role'})),
    url(r'^backend/api/pages', other.CompanyRolesView.as_view({'get': 'get_pages'})),

    url(r'^backend/api/rest-auth/registration/', include('rest_auth.registration.urls')),
    path('backend/api/rest-auth/change-password/<int:pk>/', views.ChangePasswordView.as_view()),
    url(r'^backend/api/rest-auth/refresh/', refresh_jwt_token),
    url(r'^backend/api/rest-auth/', include('rest_auth.urls')),

    url(r'^backend/api/test', mobile_api.MobileAuth.as_view({'get': 'test'})),
    url(r'^backend/api/mob-auth/sms', mobile_api.MobileAuth.as_view({'post': 'get_code_by_sms'})),
    url(r'^backend/api/mob-auth/auth', mobile_api.MobileAuth.as_view({'post': 'auth'})),
    url(r'^backend/api/mobile/update-location', mobile_api.MobileAPI.as_view({'post': 'update_location'})),
    url(r'^backend/api/mobile/send-bid', mobile_api.MobileAPI.as_view({'post': 'send_bid'})),
    url(r'^backend/api/mobile/remove-bid', mobile_api.MobileAPI.as_view({'post': 'remove_bid'})),
    url(r'^backend/api/mobile/profile', mobile_api.MobileAPI.as_view({'post': 'edit_driver', 'get': 'profile'})),
    url(r'^backend/api/mobile/get-loads-history', mobile_api.MobileAPI.as_view({'get': 'get_loads_history'})),
    url(r'^backend/api/mobile/get-loads', mobile_api.MobileAPI.as_view({'get': 'get_loads'})),
    url(r'^backend/api/mobile/upload-docs', other.LoadFileUploadView.as_view()),
    url(r'^backend/api/mobile/chat-groups', views.UserChatGroups.as_view()),
    path('backend/api/mobile/chat-groups/<int:pk>/', views.UserChat.as_view()),

    url(r'^backend/api/hr/add-drivers', other.HRAPIView.as_view({'post': 'add_drivers'})),
    url(r'^backend/api/hr/reject-drivers', other.HRAPIView.as_view({'post': 'reject_drivers'})),
    url(r'^backend/api/hr/update-car', other.HRAPIView.as_view({'post': 'update_car'})),
    url(r'^backend/api/hr/check-drivers', other.HRAPIView.as_view({'get': 'check_drivers'})),
    path('backend/api/guest/load/<int:code>/', other.GuestAPI.as_view({'get': 'get_load'})),
    path('backend/api/guest/map/', other.GuestAPI.as_view({'get': 'get_cars_map'})),
    url(r'^backend/api/google', other.GooglePubSub.as_view({'get': 'get', 'post': 'post'})),

] + static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT, show_indexes=True) + static(settings.STATIC_URL, document_root=settings.STATIC_ROOT, show_indexes=True) 


    
