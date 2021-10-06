from rest_framework.permissions import BasePermission, SAFE_METHODS
from .helpers.get_user_owner import get_user_owner


class IsOwnerProfileOrReadOnly(BasePermission):
    def has_object_permission(self, request, view, obj):
        if request.method in SAFE_METHODS:
            return True
        # return obj.user == request.user


class InChatGroup(BasePermission):
    def has_object_permission(self, request, view, obj):
        if obj.user_initiator == request.user or obj.user_member == request.user:
            return True
        else:
            return False

    
class InChat(BasePermission):
    def has_object_permission(self, request, view, obj):
        if request.user in obj.users.all() or request.user.role.pk == 3 or request.user.role.pk == 4:
            return True
        else:
            return False


        










