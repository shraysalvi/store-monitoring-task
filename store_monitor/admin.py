from django.contrib import admin
from import_export.admin import ImportExportModelAdmin, ImportExportActionModelAdmin
from import_export.resources import ModelResource
from store_monitor.models import Store, PollStore, BusinessHour, Report
from import_export.widgets import ForeignKeyWidget, FloatWidget
from import_export import fields
from datetime import datetime
from django.contrib.sessions.models import Session


admin.site.register(Session)


# Store admin
class StoreAdmin(ImportExportModelAdmin, ImportExportActionModelAdmin, admin.ModelAdmin):
    list_display = ("id", "timezone")
    list_display_links = ("id", )
    empty_value_display = "NaN"
    list_per_page = 100
    search_fields = ["id", "timezone"]


admin.site.register(Store, StoreAdmin)


# PollStore admin
class SafeStoreForeignKeyWidget(ForeignKeyWidget):
    def clean(self, value, row=None, *args, **kwargs):
        try:
            return super().clean(value, row, *args, **kwargs)
        except self.model.DoesNotExist:
            # Create the missing store
            store = Store.objects.create(store_id=value)
            return store


def timestamp_to_unix(timestamp_str):
    # List of potential formats
    formats = ['%Y-%m-%d %H:%M:%S.%f %Z', '%Y-%m-%d %H:%M:%S %Z']

    for fmt in formats:
        try:
            timestamp_obj = datetime.strptime(timestamp_str, fmt)
            return timestamp_obj.timestamp()
        except ValueError:
            continue

    raise ValueError(
        f"Time data '{timestamp_str}' does not match known formats. '%Y-%m-%d %H:%M:%S.%f %Z', '%Y-%m-%d %H:%M:%S %Z'")


class SafePollStoreDateTimeWidget(FloatWidget):
    def clean(self, value, row=None, *args, **kwargs):
        try:
            # Convert the custom timestamp to Unix timestamp
            unix_timestamp = timestamp_to_unix(value)
            return super().clean(unix_timestamp, row, *args, **kwargs)
        except ValueError:
            return super().clean(value, row, *args, **kwargs)


class PollStoreDataResource(ModelResource):
    store = fields.Field(
        attribute='store',
        widget=SafeStoreForeignKeyWidget(Store, 'store_id')
    )
    timestamp_utc = fields.Field(
        attribute='timestamp_utc',
        widget=SafePollStoreDateTimeWidget()
    )

    class Meta:
        model = PollStore
        import_id_fields = ['store', 'timestamp_utc']
        # fields = ("id", "store", "status", "timestamp_utc",)


class PollStoreAdmin(ImportExportModelAdmin, ImportExportActionModelAdmin, admin.ModelAdmin):
    resource_class = PollStoreDataResource
    list_display = ("id", "store", "status", "formatted_timestamp")
    list_display_links = ("store", )
    empty_value_display = "NaN"
    list_per_page = 100
    readonly_fields = ['formatted_timestamp']
    search_fields = ["store__id"]

    def formatted_timestamp(self, obj):
        if not obj.timestamp_utc:
            return ""
        dt = datetime.fromtimestamp(obj.timestamp_utc)
        return dt.strftime('%Y-%m-%d %H:%M:%S.%f')
    formatted_timestamp.admin_order_field = 'timestamp_utc'
    formatted_timestamp.short_description = 'Timestamp Preview'


admin.site.register(PollStore, PollStoreAdmin)


# BusinessHour admin
class BusinessHourDataResource(ModelResource):
    store = fields.Field(
        attribute='store',
        widget=SafeStoreForeignKeyWidget(Store, 'store_id')
    )

    class Meta:
        model = BusinessHour


class BusinessHourAdmin(ImportExportModelAdmin, ImportExportActionModelAdmin, admin.ModelAdmin):
    resource_class = BusinessHourDataResource
    list_display = ("store", "day", "start_time_local", "end_time_local")
    list_display_links = ("store", )
    empty_value_display = "NaN"
    list_per_page = 100
    list_filter = ['day']
    search_fields = ["store__id"]


admin.site.register(BusinessHour, BusinessHourAdmin)


class ReportAdmin(admin.ModelAdmin):
    list_display = ("id", "status", "file")
    list_display_links = ("id", )
    empty_value_display = "NaN"
    list_per_page = 100
    list_filter = ['status']
    search_fields = ["id"]


    def delete_queryset(self, request, queryset):
        # Loop through the selected objects to delete their associated files
        for obj in queryset:
            if obj.file:
                obj.file.delete()
        
        # Call the superclass's method to actually delete the objects in the database
        super(ReportAdmin, self).delete_queryset(request, queryset)

admin.site.register(Report, ReportAdmin)
