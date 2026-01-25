# Superset Configuration
import os

# Security
SECRET_KEY = os.getenv('SUPERSET_SECRET_KEY', 'your_secret_key_here_change_in_production')

# Database connection for Superset metadata
SQLALCHEMY_DATABASE_URI = 'sqlite:////app/superset_home/superset.db'

# Flask settings
ENABLE_PROXY_FIX = True
PREFERRED_URL_SCHEME = 'http'
WTF_CSRF_ENABLED = False

# Feature flags
FEATURE_FLAGS = {
    'ENABLE_TEMPLATE_PROCESSING': True,
    'DASHBOARD_NATIVE_FILTERS': True,
    'DASHBOARD_CROSS_FILTERS': True,
    'DASHBOARD_NATIVE_FILTERS_SET': True,
    'ALERT_REPORTS': True,
}

# Cache configuration
CACHE_CONFIG = {
    'CACHE_TYPE': 'SimpleCache',
    'CACHE_DEFAULT_TIMEOUT': 300
}

# Superset webserver
SUPERSET_WEBSERVER_PORT = 8088
SUPERSET_WEBSERVER_TIMEOUT = 300

# Row limit for SQL Lab
ROW_LIMIT = 100000
SQL_MAX_ROW = 100000

# Default database connection string template for PostgreSQL
SQLALCHEMY_CUSTOM_PASSWORD_STORE = None

# Disable example dashboards
SUPERSET_LOAD_EXAMPLES = False

# Time grain definitions
TIME_GRAIN_DENYLIST = []
TIME_GRAIN_ADDONS = {}

# Logo
APP_NAME = "E-Commerce BI Dashboard"
