"""Run the full scrape pipeline locally: generate links, crawl, then analyze.

Mirrors what .github/workflows/test.yml does in CI. Run from the repo root.
"""

import os
import subprocess

REPO_ROOT = os.path.dirname(os.path.abspath(__file__))
SCRAPY_PROJECT_DIR = os.path.join(REPO_ROOT, "jobs_ge")
JOBS_DATA_PATH = os.path.join(REPO_ROOT, "database", "jobs_data.json")


def run(command, cwd=REPO_ROOT):
    print(f"$ {' '.join(command)}  (in {cwd})")
    subprocess.run(command, cwd=cwd, check=True)


def main():
    run(["python", "scheduled_scripts/link_generator.py"])

    # scrapy.cfg lives in jobs_ge/, and -O (overwrite, not -o/append) since
    # database/jobs_data.json already has content from previous runs.
    run(["scrapy", "crawl", "scraper", "-O", JOBS_DATA_PATH], cwd=SCRAPY_PROJECT_DIR)

    run(["python", "scheduled_scripts/data_analysis.py"])


if __name__ == "__main__":
    main()
