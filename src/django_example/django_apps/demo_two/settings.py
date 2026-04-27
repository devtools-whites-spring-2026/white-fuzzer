SECRET_KEY = "demo-two"
DEBUG = True
ROOT_URLCONF = "src.django_example.django_apps.demo_two.urls"
ALLOWED_HOSTS = ["testserver", "localhost"]
INSTALLED_APPS = [
    "django.contrib.contenttypes",
    "src.django_example.django_apps.demo_two",
]
MIDDLEWARE = []
DATABASES = {
    "default": {"ENGINE": "django.db.backends.sqlite3", "NAME": ":memory:"}
}
