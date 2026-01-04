#!/bin/bash
# Railway build script

echo "🚀 Starting Railway deployment build..."

# Install dependencies
echo "📦 Installing Python dependencies..."
pip install -r requirements.txt

# Run database migrations
echo "🔄 Running database migrations..."
python manage.py migrate --noinput

# Collect static files
echo "📁 Collecting static files..."
python manage.py collectstatic --noinput

# Create superuser if not exists (for first deploy)
echo "👑 Creating admin user..."
python manage.py shell << END
import os
from django.contrib.auth import get_user_model
User = get_user_model()

admin_username = os.environ.get('ADMIN_USERNAME', 'admin')
admin_email = os.environ.get('ADMIN_EMAIL', 'admin@example.com')
admin_password = os.environ.get('ADMIN_PASSWORD', 'admin123')

if not User.objects.filter(username=admin_username).exists():
    User.objects.create_superuser(admin_username, admin_email, admin_password)
    print(f"✅ Superuser '{admin_username}' created")
else:
    print(f"⚠️ Superuser '{admin_username}' already exists")
END

echo "✅ Build completed successfully!"