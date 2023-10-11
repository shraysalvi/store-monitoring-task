from django.urls import path
from api.views import GenerateReport, GetReport

urlpatterns = [
    path('trigger_report/', GenerateReport.as_view()),
    path('get_report/', GetReport.as_view()),
]