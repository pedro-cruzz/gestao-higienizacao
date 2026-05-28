from service.access import is_admin_user, is_dev_user, is_team_user


def auth_roles(request):
    user = getattr(request, "user", None)
    return {
        "hf_is_dev": is_dev_user(user) if user else False,
        "hf_is_admin": is_admin_user(user) if user else False,
        "hf_is_team": is_team_user(user) if user else False,
    }
