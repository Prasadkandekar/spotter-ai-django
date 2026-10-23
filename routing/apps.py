from django.apps import AppConfig


class RoutingConfig(AppConfig):
    name = "routing"
    default_auto_field = "django.db.models.BigAutoField"

    def ready(self):
        # Warm the in-memory station store and the offline gazetteer at process start so that
        # no request ever pays the one-time load cost (~2s for the gazetteer).
        try:
            from .gazetteer import _city_index
            from .stations import get_store

            get_store()
            _city_index()
        except Exception:  # e.g. stations.csv not built yet (first run of `build_stations`)
            pass
