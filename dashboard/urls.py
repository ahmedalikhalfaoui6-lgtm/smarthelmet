from django.urls import path
from django.contrib.auth import views as auth_views
from . import views

urlpatterns = [
    path('', views.dashboard, name='dashboard'),
    path('riders/', views.riders_list, name='riders'),
    path('riders/<int:rider_id>/', views.rider_detail, name='rider_detail'),
    path('incidents/', views.incidents_list, name='incidents'),
    path('live-data/', views.live_data, name='live_data'),
    path('mqtt-docs/', views.mqtt_docs, name='mqtt_docs'),
    path('settings/', views.system_settings, name='settings'),
    path('riders/add/', views.add_rider, name='add_rider'),
    path('login/', auth_views.LoginView.as_view(template_name='dashboard/login.html'), name='login'),
    path('logout/', auth_views.LogoutView.as_view(next_page='login'), name='logout'),
]