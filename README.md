# GlowHub (Django)

Beauty & wellness marketplace: provider pages, M-Pesa deposit bookings, inventory.

## Run
    python -m venv .venv && source .venv/bin/activate
    pip install -r requirements.txt
    cp .env.example .env        # set DATABASE_URL to your Supabase Postgres URI for production
    python manage.py migrate
    python manage.py createsuperuser
    python manage.py seed_demo
    python manage.py runserver

First run `python manage.py makemigrations marketplace bookings inventory` if migrations are missing.
In /admin/ open Sites and set the domain, then approve providers (Businesses > action "Approve").

## M-Pesa
Fill the MPESA_* values in .env. The callback URL must be public HTTPS (use ngrok in dev).
Run `python manage.py expire_bookings` every minute (cron/Celery beat) to release unpaid slots.

## Modules
accounts (Allauth + staff TOTP 2FA) | marketplace (providers, services, hours, blocks, reviews, maps, search incl. near-me, reports + CSV)
bookings (availability, atomic booking, state machine, M-Pesa, idempotent callbacks, reconciliation, refunds, provider actions)
subscriptions (plans, 14-day trial, grace period, server-side entitlements, M-Pesa billing) | inventory | messaging | support (tickets + disputes with deadlines)
core (audit log, email notifications with retry, rate limiting, CSP and security headers, legal page drafts, robots.txt).

## Before launch
1. `python manage.py makemigrations marketplace bookings inventory subscriptions messaging support core && python manage.py migrate`
2. `python manage.py test` then `python manage.py check --deploy`
3. Create a "Finance" group with the `bookings.approve_refund` permission. Refunds are approved in the admin; the actual M-Pesa reversal is done in your Safaricom portal and the reference recorded (automated B2C/reversal needs separate Safaricom approval).
4. Schedule the jobs in CRON.md. Configure SMTP (SPF/DKIM/DMARC), Redis (`REDIS_URL`), and a private object store if you add uploads.
5. Replace the draft legal pages and settle the open decisions in section 26 of the spec (who holds funds, payouts, pricing).
6. Commission a penetration test and test backup restores.

## Added in the second round
- **Identity verification** (/verification/): ID or passport, selfie holding a one-time code, explicit consent, images re-encoded and stored privately,
  reviewer-only access with every view audited, keyed hash of the ID number blocks one ID on many accounts, images auto-deleted after
  `VERIFICATION_RETENTION_DAYS`. Review is manual. For automated face matching and liveness plug in a vendor such as Smile ID.
- **Payouts** (/earnings/): central collection model. Ledger is append-only; platform fee and hold period configurable; provider requests
  payouts, staff approve, Daraja B2C sends (or staff pay manually and enter the receipt). Requires ID-verified provider and verified phone.
- **Diamonds** (/rewards/): referrals, bookings, reviews and profile tasks. Earnings are held 7 days, capped daily, reversed on refunds,
  frozen per account, and only pay out after a paid booking. Withdrawals to M-Pesa are OFF until `WITHDRAWALS_ENABLED=True`, need a verified phone,
  account age, a verified provider identity (for providers) and staff approval.
- **Staff schedules and branches**, **photo uploads** (validated and re-encoded), **SMS/WhatsApp** (Africa's Talking, WhatsApp Cloud API; opt-in, urgent
  notices only), **phone OTP** (hashed codes, expiry, attempt and request limits).

## Before enabling money features
1. Run `python manage.py setup_groups` and give finance staff the Finance group.
2. Daraja B2C needs separate Safaricom approval, a B2C shortcode, initiator name and security credential (MPESA_B2C_* in .env).
3. Decide who holds the money (spec 7.5) with a lawyer and accountant: collecting and paying out customer funds and cash-out rewards can
   bring payment-service, tax (e.g. withholding on rewards) and consumer-protection obligations in Kenya.
4. Biometric and ID data are sensitive personal data under the Data Protection Act, 2019: complete a DPIA, register with the ODPC,
   publish the privacy notice, and use private object storage with signed URLs in production.
5. Rewards are a marketing cost the platform funds. Tune `REWARDS` and `PLATFORM_FEE_PERCENT` so referral payouts stay below customer lifetime value.

## Known gaps
Automated face matching, ID document OCR, Daraja automated customer refunds, proper private object storage adapter, branch-level reports,
and a UI for admins beyond Django admin. Tests cover core money, booking, availability, OTP and rewards paths, not every screen.

## Images and background (Cloudinary + database)
1. Put your Cloudinary URL in `.env`: `CLOUDINARY_URL=cloudinary://API_KEY:API_SECRET@CLOUD_NAME` (without it, images use local disk).
2. `pip install -r requirements.txt`, then `python manage.py makemigrations core marketplace && python manage.py migrate`.
3. Admin > Core > Site settings: upload the background image and set the overlay strength. Providers upload a logo and cover under
   Dashboard > Business details; category images are set in Admin > Categories; gallery photos under Dashboard > Photos.
4. ID documents and selfies are intentionally NOT sent to Cloudinary (they stay in private storage).
