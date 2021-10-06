def get_user_owner(user):
    if user.user_owner:
        return user.user_owner
    else:
        return user