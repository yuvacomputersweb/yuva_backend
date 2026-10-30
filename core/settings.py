import os
from pathlib import Path
from datetime import timedelta
from dotenv import load_dotenv
import datetime
import dj_database_url

BASE_DIR = Path(__file__).resolve().parent.parent
load_dotenv(BASE_DIR / '.env')

SECRET_KEY = os.environ.get('DJANGO_SECRET_KEY')
DEBUG = os.environ.get('DEBUG', 'True') == 'True'
ALLOWED_HOSTS = [
    'api.yuvacomputers.in',
    'admin.yuvacomputers.in',
    'yuvacomputers.in', # Add this
    'www.yuvacomputers.in', # Add this
    '103.138.96.2'
]
SIMPLE_JWT = {
    'LEEWAY': 60, 
}

INSTALLED_APPS = [
    'jazzmin',
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
    'django.contrib.sites',

    # Third Party
    'rest_framework',
    'rest_framework.authtoken',
    'corsheaders',
    'dj_rest_auth',
    'allauth',
    'allauth.account',
    'allauth.socialaccount',
    'allauth.socialaccount.providers.google',
    'dj_rest_auth.registration',
    

    # Local Apps
    'accounts',
    'store',
    'orders',
    'payments',
    'content',
    'mails',
    'engage',
]

SITE_ID = 1

MIDDLEWARE = [
    'corsheaders.middleware.CorsMiddleware',
    'django.middleware.security.SecurityMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
    'allauth.account.middleware.AccountMiddleware',
]

ROOT_URLCONF = 'core.urls'

TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [BASE_DIR / 'templates'],
        'APP_DIRS': True,
        'OPTIONS': {
            'context_processors': [
                'django.template.context_processors.debug',
                'django.template.context_processors.request',
                'django.contrib.auth.context_processors.auth',
                'django.contrib.messages.context_processors.messages',
            ],
        },
    },
]

WSGI_APPLICATION = 'core.wsgi.application'


DATABASES = {
      'default': dj_database_url.config(
           default=os.environ.get('DATABASE_URL'),
           conn_max_age=600,
           ssl_require=False 
    )
}
	
AUTH_USER_MODEL = 'accounts.CustomUser'


# --- REST FRAMEWORK ---
REST_FRAMEWORK = {
    'DEFAULT_RENDERER_CLASSES': [
        'rest_framework.renderers.JSONRenderer',
    ],
    'DEFAULT_AUTHENTICATION_CLASSES': (
        'rest_framework_simplejwt.authentication.JWTAuthentication',
    ),
    'DEFAULT_PERMISSION_CLASSES': [
        'rest_framework.permissions.IsAuthenticatedOrReadOnly',
    ],
    'DEFAULT_THROTTLE_CLASSES': [
        'rest_framework.throttling.AnonRateThrottle',
        'rest_framework.throttling.UserRateThrottle',
    ],
    'DEFAULT_THROTTLE_RATES': {
        'anon': '3000/hour',
        'user': '5000/hour',
    },
}



SIMPLE_JWT = {
    'ACCESS_TOKEN_LIFETIME': timedelta(days=7),
    'AUTH_HEADER_TYPES': ('Bearer',),
    'LEEWAY': timedelta(seconds=300),
}

REST_AUTH = {
    'USE_JWT': True,
    'JWT_AUTH_COOKIE': None,
    'JWT_AUTH_REFRESH_COOKIE': None,
    'JWT_AUTH_HTTPONLY': False,
}

# --- GOOGLE OAUTH ---
SOCIALACCOUNT_PROVIDERS = {
    'google': {
        'SCOPE': ['profile', 'email'],
        'AUTH_PARAMS': {'access_type': 'online'},
        'OAUTH_PKCE_ENABLED': True,
        'FETCH_USERINFO' : True,
    }
}

ACCOUNT_LOGIN_METHODS = {'email'}
ACCOUNT_SIGNUP_FIELDS = ['email*', 'password1*', 'password2*']
ACCOUNT_EMAIL_VERIFICATION = 'none'
ACCOUNT_USER_MODEL_USERNAME_FIELD = None
SOCIALACCOUNT_EMAIL_AUTHENTICATION = True
SOCIALACCOUNT_EMAIL_AUTHENTICATION_AUTO_CONNECT = True


# --- CORS ---
CORS_ALLOWED_ORIGINS = [
    "https://yuvacomputers.in",
    "https://www.yuvacomputers.in",
    "https://api.yuvacomputers.in",
    "https://admin.yuvacomputers.in",
    "http://localhost:5173",
]


CORS_ALLOW_CREDENTIALS = True

CSRF_TRUSTED_ORIGINS = [
    "https://yuvacomputers.in",
    "https://www.yuvacomputers.in",
    "https://api.yuvacomputers.in",
    "https://admin.yuvacomputers.in",
]
SECURE_CROSS_ORIGIN_OPENER_POLICY = "same-origin-allow-popups"

# --- STATIC & MEDIA ---
STATIC_URL = 'static/'
STATIC_ROOT = BASE_DIR / 'staticfiles'
MEDIA_URL = '/media/'
MEDIA_ROOT = BASE_DIR / 'media'

# --- EMAIL ---
EMAIL_BACKEND = "django.core.mail.backends.smtp.EmailBackend"

EMAIL_HOST = "smtp.gmail.com"
EMAIL_PORT = 587
EMAIL_USE_TLS = True

EMAIL_HOST_USER = os.environ.get("EMAIL_HOST_USER")
EMAIL_HOST_PASSWORD = os.environ.get("EMAIL_HOST_PASSWORD")

DEFAULT_FROM_EMAIL = f"Yuva Computers <{EMAIL_HOST_USER}>"

# --- RAZORPAY ---
RAZORPAY_KEY_ID = os.environ.get('RAZORPAY_KEY_ID')
RAZORPAY_KEY_SECRET = os.environ.get('RAZORPAY_KEY_SECRET')

# --- TIMEZONE ---
TIME_ZONE = 'Asia/Kolkata'
USE_TZ = True
USE_I18N = True
LANGUAGE_CODE = 'en-us'

DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'

# --- JAZZMIN ADMIN THEME ---
JAZZMIN_SETTINGS = {
    "site_title": "Yuva Computers Admin",
    "site_header": "Yuva Computers",
    "welcome_sign": "Welcome to Yuva Computers Admin",
    "search_model": ["store.Product"],
    "show_ui_builder": False,
    "navigation_expanded": True,
    "changeform_format": "single",
}
# Production Security (only active when DEBUG is False)
if not DEBUG:
    SECURE_SSL_REDIRECT = True
    SESSION_COOKIE_SECURE = True
    CSRF_COOKIE_SECURE = True
    SECURE_BROWSER_XSS_FILTER = True
    SECURE_CONTENT_TYPE_NOSNIFF = True
    X_FRAME_OPTIONS = 'DENY'
    
    # HSTS Configuration
    SECURE_HSTS_SECONDS = 31536000
    SECURE_HSTS_INCLUDE_SUBDOMAINS = True
    SECURE_HSTS_PRELOAD = True
    
    # Proxy Headers for Nginx
    SECURE_PROXY_SSL_HEADER = ('HTTP_X_FORWARDED_PROTO', 'https')
    USE_X_FORWARDED_HOST = True

DELHIVERY_API_TOKEN = os.environ.get('DELHIVERY_API_TOKEN', '')
DELHIVERY_API_URL   = os.environ.get('DELHIVERY_API_URL', 'https://track.delhivery.com')
DELHIVERY_PICKUP_LOCATION = os.environ.get('DELHIVERY_PICKUP_LOCATION', '')

WA_PHONE_NUMBER_ID = os.environ.get('WA_PHONE_NUMBER_ID', '')
WA_ACCESS_TOKEN    = os.environ.get('WA_ACCESS_TOKEN', '')
WA_TEMPLATE_NAME   = os.environ.get('WA_TEMPLATE_NAME', 'order_placed')
WA_API_URL         = os.environ.get('WA_API_URL', 'https://live-mt-server.wati.io/308273')

# WhatsApp templates for each order stage (WATI, account 308273 / +91 97098 88456).
# Set a variable to an empty string to switch that message off.
WA_TEMPLATE_PAYMENT_RECEIVED = os.environ.get('WA_TEMPLATE_PAYMENT_RECEIVED', 'payment_received')
WA_TEMPLATE_ORDER_SHIPPED    = os.environ.get('WA_TEMPLATE_ORDER_SHIPPED', 'order_shipped')
WA_TEMPLATE_OUT_FOR_DELIVERY = os.environ.get('WA_TEMPLATE_OUT_FOR_DELIVERY', 'out_for_delivery')
WA_TEMPLATE_ORDER_DELIVERED  = os.environ.get('WA_TEMPLATE_ORDER_DELIVERED', 'order_delivered')
WA_TEMPLATE_ORDER_CANCELLED  = os.environ.get('WA_TEMPLATE_ORDER_CANCELLED', 'order_cancelled')

SITE_URL = os.environ.get('SITE_URL', 'https://www.yuvacomputers.in')

# Non-order WhatsApp templates (engage app). Empty string = switched off.
WA_TEMPLATE_BACK_IN_STOCK = os.environ.get('WA_TEMPLATE_BACK_IN_STOCK', 'back_in_stock')
WA_TEMPLATE_CART_REMINDER = os.environ.get('WA_TEMPLATE_CART_REMINDER', 'cart_reminder')
WA_TEMPLATE_LOW_STOCK     = os.environ.get('WA_TEMPLATE_LOW_STOCK', 'low_stock_alert')
WA_TEMPLATE_DAILY_SUMMARY = os.environ.get('WA_TEMPLATE_DAILY_SUMMARY', 'daily_summary')
WA_TEMPLATE_NEW_LEAD      = os.environ.get('WA_TEMPLATE_NEW_LEAD', 'new_lead')
WA_TEMPLATE_RETURN_UPDATE = os.environ.get('WA_TEMPLATE_RETURN_UPDATE', 'return_update')

# Google reviews on the home page (Google Cloud → Places API (New)).
GOOGLE_PLACES_API_KEY = os.environ.get('GOOGLE_PLACES_API_KEY', '')
GOOGLE_PLACE_ID       = os.environ.get('GOOGLE_PLACE_ID', '')

# Where Delhivery sends returned (RTO) parcels.
DELHIVERY_RETURN_ADDRESS = {
    'address': os.environ.get('DELHIVERY_RETURN_ADDRESS', 'Sai Towers, 204, 2nd Floor, Metro Pillar No. 1519, Dilsukhnagar'),
    'city': os.environ.get('DELHIVERY_RETURN_CITY', 'Hyderabad'),
    'state': os.environ.get('DELHIVERY_RETURN_STATE', 'Telangana'),
    'pin': os.environ.get('DELHIVERY_RETURN_PIN', '500060'),
    'phone': os.environ.get('DELHIVERY_RETURN_PHONE', '9709888456'),
}

LOGGING = {
    'version': 1,
    'disable_existing_loggers': False,
    'formatters': {
        'verbose': {
            'format': '[{levelname}] {asctime} {name}: {message}',
            'style': '{',
        },
    },
    'handlers': {
        'console': {
            'class': 'logging.StreamHandler',
            'formatter': 'verbose',
        },
    },
    'loggers': {
        'orders.services': {
            'handlers': ['console'],
            'level': 'INFO',
            'propagate': False,
        },
        'payments': {
            'handlers': ['console'],
            'level': 'INFO',
            'propagate': False,
        },
        'orders.admin': {
            'handlers': ['console'],
            'level': 'INFO',
            'propagate': False,
        },
    },
}
