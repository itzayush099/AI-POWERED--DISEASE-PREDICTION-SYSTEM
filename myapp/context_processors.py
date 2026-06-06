from .models import Message

def unread_messages(request):
    """
    Adds the unread message count for the logged-in user to all templates.
    """
    if request.user.is_authenticated:
        count = Message.objects.filter(receiver=request.user, is_read=False).count()
    else:
        count = 0
    return {
        "unread_messages_count": count
    }
