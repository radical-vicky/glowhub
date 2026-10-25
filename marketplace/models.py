from django.conf import settings
from django.core.exceptions import ValidationError
from django.core.validators import MinValueValidator, MaxValueValidator
from django.db import models

RESERVED_SLUGS = {"admin", "accounts", "search", "dashboard", "book", "inventory",
                  "become-provider", "staff", "rewards", "verification", "earnings", "media", "messages", "legal", "subscription", "support", "robots", "static", "media", "api", "support", "login", "signup"}


class Category(models.Model):
    name = models.CharField(max_length=60, unique=True)
    slug = models.SlugField(unique=True)
    image = models.ImageField(upload_to="categories/", blank=True)

    class Meta:
        verbose_name_plural = "categories"
        ordering = ["name"]

    def __str__(self):
        return self.name


class Business(models.Model):
    class Status(models.TextChoices):
        PENDING = "PENDING"
        APPROVED = "APPROVED"
        SUSPENDED = "SUSPENDED"

    owner = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="business")
    name = models.CharField(max_length=120)
    slug = models.SlugField(max_length=60, unique=True)
    description = models.TextField(blank=True)
    logo = models.ImageField(upload_to="logos/", blank=True)
    cover_image = models.ImageField(upload_to="covers/", blank=True)
    categories = models.ManyToManyField(Category, blank=True)
    phone = models.CharField(max_length=20, blank=True)
    area = models.CharField(max_length=120, help_text="e.g. Westlands, Nairobi")
    latitude = models.DecimalField(max_digits=9, decimal_places=6, null=True, blank=True)
    longitude = models.DecimalField(max_digits=9, decimal_places=6, null=True, blank=True)
    status = models.CharField(max_length=10, choices=Status, default=Status.PENDING, db_index=True)
    verified = models.BooleanField(default=False)
    deposit_percent = models.PositiveSmallIntegerField(
        default=50, validators=[MinValueValidator(10), MaxValueValidator(100)])
    show_exact_location = models.BooleanField(default=True, help_text="Untick to show only your area publicly")
    buffer_minutes = models.PositiveSmallIntegerField(default=0, validators=[MaxValueValidator(120)])
    cancellation_policy = models.TextField(
        default="Free cancellation up to 24 hours before your appointment. "
                "Provider cancellations are refunded in full.")
    created_at = models.DateTimeField(auto_now_add=True)

    def clean(self):
        if self.slug in RESERVED_SLUGS:
            raise ValidationError({"slug": "This web address is reserved."})

    @property
    def is_public(self):
        return self.status == self.Status.APPROVED

    def __str__(self):
        return self.name


class Service(models.Model):
    business = models.ForeignKey(Business, on_delete=models.CASCADE, related_name="services")
    name = models.CharField(max_length=120)
    description = models.TextField(blank=True)
    price = models.DecimalField(max_digits=10, decimal_places=2, validators=[MinValueValidator(1)])
    duration_minutes = models.PositiveIntegerField(validators=[MinValueValidator(10)])
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ["name"]

    def __str__(self):
        return f"{self.name} ({self.business})"


class BusinessHours(models.Model):
    business = models.ForeignKey(Business, on_delete=models.CASCADE, related_name="hours")
    weekday = models.PositiveSmallIntegerField(choices=[(i, d) for i, d in enumerate(
        ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"])])
    opens = models.TimeField()
    closes = models.TimeField()

    class Meta:
        unique_together = ("business", "weekday")

    def clean(self):
        if self.closes <= self.opens:
            raise ValidationError("Closing time must be after opening time.")


class Review(models.Model):
    booking = models.OneToOneField("bookings.Booking", on_delete=models.CASCADE, related_name="review")
    business = models.ForeignKey(Business, on_delete=models.CASCADE, related_name="reviews")
    rating = models.PositiveSmallIntegerField(validators=[MinValueValidator(1), MaxValueValidator(5)])
    comment = models.TextField(blank=True)
    provider_reply = models.TextField(blank=True, max_length=1000)
    is_hidden = models.BooleanField(default=False)  # moderation
    created_at = models.DateTimeField(auto_now_add=True)


class AvailabilityBlock(models.Model):
    business = models.ForeignKey(Business, on_delete=models.CASCADE, related_name="blocks")
    start = models.DateTimeField()
    end = models.DateTimeField()
    reason = models.CharField(max_length=100, blank=True)
    staff = models.ForeignKey("Staff", null=True, blank=True, on_delete=models.CASCADE, help_text="Leave empty to block the whole business")

    def clean(self):
        if self.end <= self.start:
            raise ValidationError("End must be after start.")


class Branch(models.Model):
    business = models.ForeignKey(Business, on_delete=models.CASCADE, related_name="branches")
    name = models.CharField(max_length=100)
    area = models.CharField(max_length=120)
    phone = models.CharField(max_length=20, blank=True)
    latitude = models.DecimalField(max_digits=9, decimal_places=6, null=True, blank=True)
    longitude = models.DecimalField(max_digits=9, decimal_places=6, null=True, blank=True)
    is_active = models.BooleanField(default=True)

    class Meta:
        verbose_name_plural = "branches"

    def __str__(self):
        return f"{self.business} - {self.name}"


class Staff(models.Model):
    business = models.ForeignKey(Business, on_delete=models.CASCADE, related_name="staff")
    name = models.CharField(max_length=100)
    branch = models.ForeignKey(Branch, null=True, blank=True, on_delete=models.SET_NULL)
    services = models.ManyToManyField(Service, blank=True, help_text="Services this person performs")
    is_active = models.BooleanField(default=True)

    class Meta:
        verbose_name_plural = "staff"

    def __str__(self):
        return self.name


class StaffHours(models.Model):
    """If a staff member has any rows here, these replace the business hours for them."""
    staff = models.ForeignKey(Staff, on_delete=models.CASCADE, related_name="hours")
    weekday = models.PositiveSmallIntegerField(choices=BusinessHours._meta.get_field("weekday").choices)
    opens = models.TimeField()
    closes = models.TimeField()

    class Meta:
        unique_together = ("staff", "weekday")


class BusinessPhoto(models.Model):
    business = models.ForeignKey(Business, on_delete=models.CASCADE, related_name="photos")
    image = models.ImageField(upload_to="business_photos/")
    caption = models.CharField(max_length=120, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
