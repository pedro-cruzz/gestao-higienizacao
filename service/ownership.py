from django.db.models import QuerySet

from service.access import is_dev_user


def owned_queryset(queryset: QuerySet, user, owner_field: str = "owner") -> QuerySet:
    if user is None:
        return queryset
    if is_dev_user(user):
        return queryset
    return queryset.filter(**{owner_field: user})


def set_owner(instance, user):
    if hasattr(instance, "owner_id") and not instance.owner_id:
        instance.owner = user
    return instance


def owner_from_related(*objects):
    for obj in objects:
        if obj is not None and getattr(obj, "owner_id", None):
            return obj.owner
    return None
