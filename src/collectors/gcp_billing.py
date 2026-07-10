from .base import BaseCollector


class GCPBillingCollector(BaseCollector):
    def name(self):
        return "GCP Billing"

    def collect(self) -> list[dict]:
        print("  [GCP Billing] Collector stub — requires google-cloud-billing credentials")
        return []
