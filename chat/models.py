from django.db import models
from django.contrib.auth.models import User
from django.db.models import Q
from django.utils import timezone

class PrivateChat(models.Model):
    user1 = models.ForeignKey(User, on_delete=models.CASCADE, related_name='chat_user1')
    user2 = models.ForeignKey(User, on_delete=models.CASCADE, related_name='chat_user2')
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        unique_together = ['user1', 'user2']
    
    def __str__(self):
        return f"{self.user1.username} <-> {self.user2.username}"
    
    @staticmethod
    def get_or_create_chat(user_a, user_b):
        if user_a == user_b:
            return None
        
        chat = PrivateChat.objects.filter(
            Q(user1=user_a, user2=user_b) | Q(user1=user_b, user2=user_a)
        ).first()
        
        if chat:
            return chat
        
        return PrivateChat.objects.create(user1=user_a, user2=user_b)
    
    def get_other_user(self, current_user):
        return self.user2 if self.user1 == current_user else self.user1

class Message(models.Model):
    chat = models.ForeignKey(PrivateChat, on_delete=models.CASCADE, related_name='messages')
    sender = models.ForeignKey(User, on_delete=models.CASCADE, related_name='sent_messages')
    receiver = models.ForeignKey(User, on_delete=models.CASCADE, related_name='received_messages')
    content = models.TextField()
    is_read = models.BooleanField(default=False)
    timestamp = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        ordering = ['timestamp']
    
    def __str__(self):
        return f"{self.sender.username} -> {self.receiver.username}: {self.content[:30]}"