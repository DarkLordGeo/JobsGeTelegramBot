# Define here the models for your scraped items
#
# See documentation in:
# https://docs.scrapy.org/en/latest/topics/items.html

import scrapy


class JobsGeItem(scrapy.Item):
    job_id = scrapy.Field()
    company = scrapy.Field()
    position = scrapy.Field()
    date = scrapy.Field()
    desciption = scrapy.Field()
    job_link = scrapy.Field()
