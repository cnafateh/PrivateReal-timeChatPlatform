from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth import login, authenticate, logout
from django.contrib.auth.forms import UserCreationForm
from django.contrib.auth.decorators import login_required
from django.contrib.auth.models import User
from django.contrib import messages
from django.http import JsonResponse
from django.db import models
from django.db.models import Q
from .models import PrivateChat, Message

def login_view(request):
    if request.method == 'POST':
        username = request.POST['username']
        password = request.POST['password']
        user = authenticate(request, username=username, password=password)
        if user:
            login(request, user)
            return redirect('inbox')
        else:
            messages.error(request, 'نام کاربری یا رمز عبور اشتباه است')
    return render(request, 'chat/login.html')

def register_view(request):
    if request.method == 'POST':
        form = UserCreationForm(request.POST)
        if form.is_valid():
            user = form.save()
            login(request, user)
            return redirect('inbox')
    else:
        form = UserCreationForm()
    return render(request, 'chat/register.html', {'form': form})

def logout_view(request):
    logout(request)
    return redirect('login')

@login_required
def inbox(request):
    """لیست چت‌های خصوصی کاربر"""
    chats = PrivateChat.objects.filter(
        models.Q(user1=request.user) | models.Q(user2=request.user)
    )
    
    chats_data = []
    for chat in chats:
        other_user = chat.get_other_user(request.user)
        last_message = chat.messages.last()
        unread_count = chat.messages.filter(receiver=request.user, is_read=False).count()
        
        chats_data.append({
            'chat': chat,
            'other_user': other_user,
            'last_message': last_message,
            'unread_count': unread_count
        })
    
    return render(request, 'chat/inbox.html', {'chats': chats_data})

@login_required
def search_user(request):
    """جستجوی کاربر با username"""
    query = request.GET.get('q', '').strip()
    users = []
    message = None
    
    if query:
        try:
            # جستجوی دقیق با username
            user = User.objects.get(Q(username__iexact=query))
            if user != request.user:
                users = [user]
            else:
                message = 'نمی‌توانید با خودتان چت کنید!'
        except User.DoesNotExist:
            message = f'کاربری با آیدی "{query}" یافت نشد'
    
    return render(request, 'chat/search_user.html', {
        'users': users,
        'query': query,
        'message': message
    })

@login_required
def private_chat(request, user_id):
    """صفحه چت خصوصی با یک کاربر خاص"""
    other_user = get_object_or_404(User, id=user_id)
    
    # دریافت یا ساخت چت
    chat = PrivateChat.get_or_create_chat(request.user, other_user)
    
    if not chat:
        messages.error(request, 'خطا در ایجاد چت')
        return redirect('inbox')
    
    # علامت زدن پیام‌ها به عنوان خوانده شده
    Message.objects.filter(chat=chat, receiver=request.user, is_read=False).update(is_read=True)
    
    # دریافت تاریخچه پیام‌ها
    messages_history = Message.objects.filter(chat=chat).select_related('sender', 'receiver')[:100]
    
    return render(request, 'chat/private_chat.html', {
        'chat': chat,
        'other_user': other_user,
        'messages': messages_history,
        'username': request.user.username
    })

@login_required
def get_or_create_chat_api(request, user_id):
    """API برای شروع چت جدید (Ajax)"""
    other_user = get_object_or_404(User, id=user_id)
    chat = PrivateChat.get_or_create_chat(request.user, other_user)
    
    if chat:
        return JsonResponse({'success': True, 'chat_id': chat.id})
    return JsonResponse({'success': False})