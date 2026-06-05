SECRET_KEY = "demo-one"
DEBUG = True
ROOT_URLCONF = "src.django_example.django_apps.demo_one.urls"
ALLOWED_HOSTS = ["testserver", "localhost"]
INSTALLED_APPS = [
    "django.contrib.contenttypes",
    "src.django_example.django_apps.demo_one",
]
MIDDLEWARE = []
DATABASES = {"default": {"ENGINE": "django.db.backends.sqlite3", "NAME": ":memory:"}}
