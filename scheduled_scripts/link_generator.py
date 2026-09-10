from bs4 import BeautifulSoup
import requests
import json
import time



def get_pages(endpoint_url, status, page_index, urls, file_name):
    while not status:
        page_index += 1
        url = endpoint_url.format(page=page_index)
        req = requests.get(url)
        # * request delay is going to be 5
        # ! one second is for test purposes
        time.sleep(1)
        soup = BeautifulSoup(req.text, "html.parser")
        job_count = soup.find_all("tr")
        urls[f"{page_index}"] = url
        with open(
            f"jobs_ge/jobs_ge/spiders/{file_name}.json",
            "w",
        ) as f:
            json.dump(urls, f, indent=4)
            print("wrote")
        if len(job_count) < 300:
            status = True


def main():
    get_pages(
        "https://www.jobs.ge/?page={page}&q=&cid=6&lid=0&jid=0&in_title=0&has_salary=0&is_ge=0&for_scroll=yes",
        False,
        0,
        {},
        "job_links",
    )


if __name__ == "__main__":
    main()
