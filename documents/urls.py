
from django.urls import path
from . import views

urlpatterns = [
    path('', views.home, name='home'),
    path('compare/', views.compare_documents, name='compare_documents'),
    path('download-report/', views.download_report, name='download_report'),
    path('history/', views.comparison_history, name='comparison_history'),
]
