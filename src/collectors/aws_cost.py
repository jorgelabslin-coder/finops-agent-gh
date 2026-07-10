from .base import BaseCollector


class AWSCostCollector(BaseCollector):
    def name(self):
        return "AWS Cost Explorer"

    def collect(self) -> list[dict]:
        print("  [AWS Cost] Collector stub — requires boto3 credentials")
        return []
