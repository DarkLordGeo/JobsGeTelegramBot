# Define your item pipelines here
#
# Don't forget to add your pipeline to the ITEM_PIPELINES setting
# See: https://docs.scrapy.org/en/latest/topics/item-pipeline.html


# useful for handling different item types with a single interface
from itemadapter import ItemAdapter
from scrapy.exceptions import DropItem
import json

# class JobsGePipeline:
#     def process_item(self, item, spider):
#         return item


class DuplicateFilter:

    def __init__(self):
        self.job_seen = set()
    

    def process_item(self, item, spider):
        adapter = ItemAdapter(item)
        if adapter["job_link"] in self.job_seen:
            raise DropItem(f"Duplicate job found!!")
        else:
            self.job_seen.add(adapter["job_link"])
        return item
