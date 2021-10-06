from datetime import datetime, timedelta

from django.shortcuts import render, get_object_or_404
from django.http import HttpRequest, JsonResponse
from django.db.models import Q, Max, Count, Func, F, Value
from rest_framework.parsers import MultiPartParser, FormParser
from app.views import AppAuthClass

import smtplib, imaplib, email, re, time, json, requests, copy, random, operator, base64, urllib.parse
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart

from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework import generics, status, viewsets
from rest_framework.views import APIView
from rest_framework_jwt.authentication import JSONWebTokenAuthentication
from rest_framework.authentication import BasicAuthentication, SessionAuthentication

from twilio.rest import Client
from geopy import distance

from app.models import User
from app.serializers import *
from app.permissions import *
from app.pagination import *
from app.helpers.data_filters import *
from app.helpers.get_user_owner import get_user_owner
from app.helpers.send_email_by_smtp import SMTP

from api import settings



class DriverFinesList(AppAuthClass, generics.ListCreateAPIView):
    permission_classes = [IsAuthenticated]
    serializer_class = DriverFineSerializer
    queryset = DriverFine.objects.all()

    def perform_create(self, serializer):
        user = self.request.user
        serializer.save(company_instance=user.company_instance)


class DriverFineDetails(AppAuthClass, generics.RetrieveUpdateDestroyAPIView):
    queryset = DriverFine.objects.filter()
    permission_classes = [IsAuthenticated]
    serializer_class = DriverFineSerializer


class DriverBonusesList(AppAuthClass, generics.ListCreateAPIView):
    permission_classes = [IsAuthenticated]
    serializer_class = DriverBonusSerializer
    queryset = DriverBonus.objects.all()

    def perform_create(self, serializer):
        user = self.request.user
        serializer.save(company_instance=user.company_instance)


class DriverBonusDetails(AppAuthClass, generics.RetrieveUpdateDestroyAPIView):
    queryset = DriverBonus.objects.filter()
    permission_classes = [IsAuthenticated]
    serializer_class = DriverBonusSerializer