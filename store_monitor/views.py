from typing import List, Tuple, Dict
from store_monitor.models import PollStore, Report, Store
from datetime import datetime as dt
from datetime import timedelta, time
from django.db.models import F, Max
import pandas as pd
from celery import shared_task
import tempfile, pytz, os
from django.core.files import File


def date_range(start_date: dt.date, end_date: dt.date) -> List[dt.date]:
    """This function return all the weekdays between givrn range inclusive"""
    return [start_date + timedelta(days=i) for i in range((end_date - start_date).days + 1)]


def up_down_calulate(start: dt, end: dt, b_end_utc: dt) -> float:
    return (min(end, b_end_utc) - start).total_seconds()/60  # in minutes


def get_bh_in_utc(date: dt.date, time: dt.time, tz: str) -> dt:
    """Converting Business hurs in utc form local TZ"""
    return dt.combine(date, time, tz).astimezone(pytz.utc).replace(tzinfo=None)


def calc_up_down(store: Store, start: dt, end: dt) -> Tuple[float, float]:
    """
    Calculate uptime and downtime for a store within a specific timeframe.
    Return (uptime, downtime) in minutes.
    """

    # Convert the start and end to the store's local timezone
    tz_l = pytz.timezone(str(store.timezone))
    start_l = start.astimezone(tz_l)
    end_l = end.astimezone(tz_l)

    uptime = 0
    downtime = 0

    """DB optimization using DP (prevent to hit DB again and again)
       This also consider last entered businesshour (if multiple with the same weekday)"""
    dp_bh = {bh.day: bh for bh in store.businesshour.all()}
    for day in date_range(start_l, end_l):

        bh = dp_bh.get(day.weekday(), False)
        open_time_l = bh.start_time_local if bh else time(0, 0, 0)
        close_time_l = bh.end_time_local if bh else time(23, 59, 59)

        b_start_utc = get_bh_in_utc(day, open_time_l, tz_l)
        b_end_utc = get_bh_in_utc(day, close_time_l, tz_l)

        start = max(start, b_start_utc)  # Used as a sliding pointer
        if start > end:  # If the interval out of the business hour
            uptime += 0
            downtime += 0
            continue

        observations = store.pollstore.filter(timestamp_utc__range=(start.timestamp(), min(end.timestamp(), b_end_utc.timestamp()))).order_by('timestamp_utc')
        
        if not observations:
            """ Interpolation Approach:
                - In the absence of observations, the algorithm extrapolates based on the most recent observed status.
                - If no observations are present for an entire day, the entire duration is treated as either uptime or downtime 
                  based on the last known status.
                - This logic also applies to the last hour's calculations.
            """

            if b_start_utc <= start < b_end_utc:
                last_known_poll = store.pollstore.filter(timestamp_utc__lt=start.timestamp()).order_by('-timestamp_utc')
                if last_known_poll.exists() and last_known_poll.first().status == "active":
                    uptime += up_down_calulate(start, end, b_end_utc)
                else:
                    downtime += up_down_calulate(start, end, b_end_utc)
            continue

        # This calculate uptime and downtime in a specific day
        for obs in observations:
            duration = (obs.timestamp_utc_as_datetime - start).total_seconds() / 60
            if obs.status == 'active':
                uptime += duration
            else:
                downtime += duration
            start = obs.timestamp_utc_as_datetime

        remaining_duration = up_down_calulate(start, end, b_end_utc)
        if observations and observations.last().status == 'active':
            uptime += remaining_duration
        else:
            downtime += remaining_duration
    return uptime, downtime


def report_for_store(store: Store) -> Dict[str, float]:
    now = dt.utcnow()
    
    uptime_hour, downtime_hour = calc_up_down(store, now-timedelta(hours=1), now)
    uptime_day, downtime_day = calc_up_down(store, now-timedelta(days=1), now)
    uptime_week, downtime_week = calc_up_down(store, now-timedelta(weeks=1), now)

    return {
        'store_id': store.id,
        'uptime_last_hour(in minutes)': uptime_hour,
        'uptime_last_day(in hours)': uptime_day / 60,  # Convert to hours
        'uptime_last_week(in hours)': uptime_week / 60,  # Convert to hours
        'downtime_last_hour(in minutes)': downtime_hour,
        'downtime_last_day(in hours)': downtime_day / 60,  # Convert to hours
        'downtime_last_week(in hours)': downtime_week / 60,  # Convert to hours
    }


@shared_task
def generate_report(report_id):
    columns=["store_id", "uptime_last_hour(in minutes)", "uptime_last_day(in hours)", "uptime_last_week(in hours)", 
             "downtime_last_hour(in minutes)", "downtime_last_day(in hours)", "downtime_last_week(in hours)"]

    # Using a temporary file to store the CSV content
    fd, csv_path = tempfile.mkstemp()

    # Write the header first
    pd.DataFrame(columns=columns).to_csv(csv_path, index=False)
    
    chunk_size = 1
    result = []
    for store in Store.objects.all():
        result.append(report_for_store(store))
        if chunk_size == 500:  # Inserting data to csv in chuks of 500
            chunk_size = 0
            df = pd.DataFrame(result, columns=columns)
            result.clear()
            df.to_csv(csv_path, mode='a', header=False, index=False)  # Append mode, no header
        chunk_size+=1
    if result:
        df = pd.DataFrame(result, columns=columns)
        df.to_csv(csv_path, mode='a', header=False, index=False)
    
    # Save the report to the model
    report = Report.objects.get(id=report_id)
    with open(csv_path, 'rb') as f:
        report.file.save(f'r_{report_id}.csv', File(f))
    report.status = "Complete"
    report.save()
    
    # Clean up temporary file
    os.close(fd)
    os.remove(csv_path)


# This function populates the main Store table with stores found in PollStore but not in Store.
# Used only once during initialization.
def create_store_from_poll():
    for store in PollStore.objects.values_list('store', flat=True).distinct():
        created = Store.objects.get_or_create(id=store)


# This function updates the timestamp in PollStore to the current time for hourly store observations.
def change_poll_to_current_timestamp():
    current_timestamp = dt.utcnow().timestamp()
    max_timestamp = PollStore.objects.aggregate(Max('timestamp_utc'))['timestamp_utc__max']
    PollStore.objects.update(timestamp_utc=F('timestamp_utc') + current_timestamp - max_timestamp)
