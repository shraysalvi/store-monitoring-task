from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from store_monitor.views import generate_report
from store_monitor.models import Report
from django.http import Http404
from django.shortcuts import get_object_or_404
import uuid


class GenerateReport(APIView):
    def get(self, request):
        # Initiate report generate
        report = Report.objects.create(status='Running')
        try:
            generate_report.delay(report.id)
            return Response({"report_id": report.id}, status=status.HTTP_200_OK)
        except Exception as e:
            report.delete()
            return Response({'error': str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


class GetReport(APIView):
    def post(self, request):
        input_id = request.data.get('report_id')

        if not input_id:
            return Response({'error': 'No Valid inputs', "input parameter": {"report_id": ""}}, status=status.HTTP_400_BAD_REQUEST)

        try:
            uuid.UUID(input_id)  # This will raise a ValueError if input_id is not a valid UUID
        except ValueError:
            return Response({'error': 'Invalid UUID format provided.'}, status=status.HTTP_400_BAD_REQUEST)

        report = get_object_or_404(Report, id=input_id)

        if report.status == 'Running':
            return Response({'status': 'Running'}, status=status.HTTP_200_OK)

        # If the report is completed, send the CSV URL
        return Response({
            'status': 'Complete',
            'report': request.build_absolute_uri(report.file.url)
        }, status=status.HTTP_200_OK)