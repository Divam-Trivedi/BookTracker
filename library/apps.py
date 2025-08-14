from django.apps import AppConfig


class LibraryConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "library"


from django.apps import AppConfig
from django.conf import settings


class LibraryConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'library'

    def ready(self):
        from django.contrib.sites.models import Site
        import socket

        try:
            current_domain = socket.getfqdn()

            if settings.DEBUG:
                current_domain = "127.0.0.1:8000"

            site, created = Site.objects.get_or_create(
                domain=current_domain,
                defaults={"name": current_domain}
            )
            settings.SITE_ID = site.id
            if created:
                print(f"✅ Created Site entry for {current_domain} (id={site.id})")
            else:
                print(f"ℹ️ Using existing Site entry for {current_domain} (id={site.id})")
        except Exception as e:
            print(f"⚠️ Could not update SITE_ID automatically: {e}")
