import json
from channels.generic.websocket import AsyncWebsocketConsumer
from channels.db import database_sync_to_async
from django.contrib.auth.models import User
from django.utils import timezone
from .models import PrivateChat, Message

class PrivateChatConsumer(AsyncWebsocketConsumer):
    async def connect(self):
        self.chat_id = self.scope['url_route']['kwargs']['chat_id']
        self.room_group_name = f'private_chat_{self.chat_id}'
        
        if not await self.check_user_access():
            await self.close()
            return
        
        await self.channel_layer.group_add(
            self.room_group_name,
            self.channel_name
        )
        
        await self.accept()
        print(f"✅ WebSocket connected for chat {self.chat_id}")
    
    async def disconnect(self, close_code):
        print(f"❌ WebSocket disconnected for chat {self.chat_id}")
        await self.channel_layer.group_discard(
            self.room_group_name,
            self.channel_name
        )
    
    async def receive(self, text_data):
        print(f"📨 Received message: {text_data}")
        text_data_json = json.loads(text_data)
        message_content = text_data_json['message']
        sender_username = text_data_json['username']
        
        message = await self.save_message(sender_username, message_content)
        receiver_username = await self.get_receiver_username(sender_username)
        
        # فرمت تاریخ و ساعت به صورت فارسی و کامل
        formatted_time = await self.format_timestamp(message.timestamp)
        
        await self.channel_layer.group_send(
            self.room_group_name,
            {
                'type': 'chat_message',
                'message': message_content,
                'sender': sender_username,
                'receiver': receiver_username,
                'timestamp': formatted_time
            }
        )
    
    async def chat_message(self, event):
        await self.send(text_data=json.dumps({
            'message': event['message'],
            'sender': event['sender'],
            'timestamp': event['timestamp']
        }))
    
    @database_sync_to_async
    def check_user_access(self):
        user = self.scope['user']
        if not user.is_authenticated:
            return False
        
        chat = PrivateChat.objects.filter(id=self.chat_id).first()
        if not chat:
            return False
        
        return user == chat.user1 or user == chat.user2
    
    @database_sync_to_async
    def save_message(self, sender_username, message_content):
        sender = User.objects.get(username=sender_username)
        chat = PrivateChat.objects.get(id=self.chat_id)
        receiver = chat.user2 if chat.user1 == sender else chat.user1
        
        message = Message.objects.create(
            chat=chat,
            sender=sender,
            receiver=receiver,
            content=message_content,
            is_read=False
        )
        
        print(f"💾 Message saved: {message_content} from {sender_username} to {receiver.username}")
        return message
    
    @database_sync_to_async
    def get_receiver_username(self, sender_username):
        sender = User.objects.get(username=sender_username)
        chat = PrivateChat.objects.get(id=self.chat_id)
        
        if chat.user1 == sender:
            return chat.user2.username
        else:
            return chat.user1.username
    
    @database_sync_to_async
    def format_timestamp(self, timestamp):
        """فرمت تاریخ و ساعت به صورت کامل"""
        # تنظیم timezone به تهران
        import pytz
        tehran_tz = pytz.timezone('Asia/Tehran')
        local_time = timestamp.astimezone(tehran_tz)
        
        # فرمت‌های مختلف
        # 1. فقط ساعت و دقیقه
        time_only = local_time.strftime('%H:%M')
        
        # 2. ساعت و دقیقه و ثانیه
        time_second = local_time.strftime('%H:%M:%S')
        
        # 3. تاریخ کامل با ماه فارسی (اختیاری)
        persian_months = {
            1: 'ژانویه', 2: 'فوریه', 3: 'مارس', 4: 'آوریل',
            5: 'مه', 6: 'ژوئن', 7: 'ژوئیه', 8: 'اوت',
            9: 'سپتامبر', 10: 'اکتبر', 11: 'نوامبر', 12: 'دسامبر'
        }
        
        # تاریخ کامل: 15 دی 1403 - 14:30
        full_date = local_time.strftime(f'%d {persian_months[local_time.month]} %Y - %H:%M')
        
        # برای نمایش ساده‌تر: امروز/دیروز/تاریخ
        today = timezone.now().astimezone(tehran_tz).date()
        message_date = local_time.date()
        
        if message_date == today:
            date_text = 'امروز'
        elif message_date == today - timezone.timedelta(days=1):
            date_text = 'دیروز'
        else:
            date_text = local_time.strftime('%Y/%m/%d')
        
        # فرمت نهایی
        return f"{date_text} - {time_only}"