import uuid
from django.db import models
from timezone_field import TimeZoneField
from datetime import datetime, time


class Store(models.Model):
    """
    Model of a store and it's timezone
    """
    id = models.BigIntegerField(primary_key=True)
    timezone = TimeZoneField(default='America/Chicago')

    def __str__(self):
        return str(self.id)


class PollStore(models.Model):
    """
    Model for store polling data.
    """
    store = models.ForeignKey(Store, on_delete=models.CASCADE, related_name="pollstore")
    # store = models.BigIntegerField(default=0)
    STATUS_CHOICES = [
        ('active', 'Active'),
        ('inactive', 'Inactive')
    ]
    status = models.CharField(max_length=10, choices=STATUS_CHOICES)
    timestamp_utc = models.FloatField()  # Timestamps (UTC) in Uinx format

    class Meta:
        unique_together = ('store', 'timestamp_utc')

    def __str__(self):
        return f"{self.store} | {self.status}"

    @property
    def timestamp_utc_as_datetime(self):
        return datetime.fromtimestamp(self.timestamp_utc)


class BusinessHour(models.Model):
    """
    Model for business hours of a store.
    """
    store = models.ForeignKey(Store, on_delete=models.CASCADE, related_name="businesshour")
    day_of_week_choices = [
        (0, 'Monday'),
        (1, 'Tuesday'),
        (2, 'Wednesday'),
        (3, 'Thursday'),
        (4, 'Friday'),
        (5, 'Saturday'),
        (6, 'Sunday')
    ]
    day = models.PositiveSmallIntegerField(choices=day_of_week_choices)
    start_time_local = models.TimeField(default=time(0, 0, 0))  # Local time zone of the store
    end_time_local = models.TimeField(default=time(23, 59, 59))  # Local time zone of the store

    def __str__(self):
        return f"{self.store}"


class Report(models.Model):
    id = models.UUIDField(default=uuid.uuid4, primary_key=True, editable=False)
    status = models.CharField(max_length=50, choices=[('Running', 'Running'), ('Complete', 'Complete')])
    file = models.FileField(upload_to='reports/', null=True, blank=True)  # To store CSV files

    def __str__(self):
        return f"{self.id}"

    def delete(self, *args, **kwargs):
        # Remove the file if it exists
        if self.file:
            self.file.delete()
            super(Report, self).delete(*args, **kwargs)
        else:
            super(Report, self).delete(*args, **kwargs)
