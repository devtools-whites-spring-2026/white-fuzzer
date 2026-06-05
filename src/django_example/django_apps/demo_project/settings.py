SECRET_KEY = "fuzzer-demo-project"
DEBUG = True
ROOT_URLCONF = "src.django_example.django_apps.demo_project.urls"
ALLOWED_HOSTS = ["testserver", "localhost"]
INSTALLED_APPS = [
    "django.contrib.contenttypes",
    "src.django_example.django_apps.demo_one",
    "src.django_example.django_apps.demo_two",
    "src.django_example.django_apps.demo_three",
]
MIDDLEWARE = []
DATABASES = {"default": {"ENGINE": "django.db.backends.sqlite3", "NAME": ":memory:"}}
