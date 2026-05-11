from django.urls import path
from . import views

urlpatterns = [
    path('', views.inbox, name='inbox'),
    path('login/', views.login_view, name='login'),
    path('register/', views.register_view, name='register'),
    path('logout/', views.logout_view, name='logout'),
    path('search/', views.search_user, name='search_user'),  # صفحه جستجو
    path('chat/<int:user_id>/', views.private_chat, name='private_chat'),
    path('get_or_create_chat/<int:user_id>/', views.get_or_create_chat_api, name='get_or_create_chat_api'),
]