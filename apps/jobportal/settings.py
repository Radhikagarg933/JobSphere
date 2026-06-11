import os

# 1. Ensure BASE_DIR is defined (usually at the top, but keeping here for safety)
# If BASE_DIR is already defined at the top of your file, you don't need to repeat it.
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# 2. Static files (CSS, JavaScript, Images)
STATIC_URL = '/static/'
STATICFILES_DIRS = [
    os.path.join(BASE_DIR, 'static'),
]
# This is where Django collects static files for production
STATIC_ROOT = os.path.join(BASE_DIR, 'staticfiles')

# 3. Media files (User uploads like Seeker Photos and Employer Logos)
# This MUST be active (no # at the start) for your images to work
MEDIA_URL = '/media/'
MEDIA_ROOT = os.path.join(BASE_DIR, 'media')