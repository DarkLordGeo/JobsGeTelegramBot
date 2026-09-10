import json
import os
import scrapy
from jobs_ge.items import JobsGeItem

# from scrapy.exceptions import CloseSpider
# from scrapy.exceptions import StopDownload
import uuid

# import linkge

# link_generator.py writes job_links.json into this same spiders/ directory.
_JOB_LINKS_PATH = os.path.join(os.path.dirname(__file__), "job_links.json")


class JobGeScraperSpider(scrapy.Spider):

    name = "scraper"
    allowed_domains = ["jobs.ge"]
    with open(_JOB_LINKS_PATH, "r") as f:
        data = json.load(f)
        start_urls = [link for link in data.values()]
        # print(start_urls)
        # start_urls = "https://www.jobs.ge/?page=1&q=&cid=6&lid=0&jid=0&in_title=0&has_salary=0&is_ge=0&for_scroll=yes"

    def parse(self, response):
        temp_table = response.css("table#temp_table tr")
        BASE_URL = "https://jobs.ge"
        for row in temp_table:
            base_url = {
                "job_link": BASE_URL + (row.css("td:nth-child(2) a::attr(href)").get()),
            }
            yield scrapy.Request(base_url["job_link"], callback=self.parse_page)

    def parse_page(self, response):

        # if response.status == 404:
        #     print("page not available")
        # BASE_URL = "https://jobs.ge"
        # if response.css("div#job .dtable a::text").getall()[1] == "ინგლისურ ენაზე":
        #     yield scrapy.Request(
        #         BASE_URL + response.css("div#job .dtable a::attr(href)").getall()[1],
        #         callback=self.english_job,
        #     )
        # print(response.url)
        # print("Scraping given job", response.url, response.status)

        position = response.css("div#job .dtable tr:nth-child(1) b::text").get()
        company = response.css("div#job .dtable tr:nth-child(2) a::text").get()
        date = response.css("div#job .dtable tr:nth-child(3) b").getall()
        description = response.css("div#job .dtable tr:nth-child(4) td::text").getall()

        job = JobsGeItem()
        job["job_id"] = str(uuid.uuid4())
        job["company"] = company
        job["position"] = position
        job["date"] = date
        job["desciption"] = description
        job["job_link"] = response.url or "Job link not available"

        yield job

    def english_job(self, response):
        pass

    # def english_job(self, response):
    #     position = response.css("div#job .dtable tr:nth-child(1) b::text").get()
    #     company = response.css("div#job .dtable tr:nth-child(2) td a::text").getall()
    #     date = response.css("div#job .dtable tr:nth-child(3) b").getall()
    #     description = response.css("div#job .dtable tr:nth-child(4) td::text").getall()

    #     yield {
    #         "company": company,
    #         "position": position,
    #         "date": date,
    #         "description": description,
    #         # "email": email or "Email not available",
    #         "job_link": response.url or "Job link not available",
    #     }
    #     pass
