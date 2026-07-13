from .base import BaseCollector


class AzureCostCollector(BaseCollector):
    def name(self):
        return "Azure Cost Management"

    def collect(self) -> list[dict]:
        print("  [Azure Cost] Collector stub — requires azure-mgmt-costmanagement credentials")
        return []
