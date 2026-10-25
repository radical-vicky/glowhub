# Scheduled jobs (cron or Celery beat)
* * * * *      python manage.py expire_bookings
*/5 * * * *    python manage.py reconcile_payments
*/10 * * * *   python manage.py retry_notifications
0 * * * *      python manage.py send_reminders
0 8 * * *      python manage.py subscription_reminders
30 2 * * *     python manage.py purge_verification_images
