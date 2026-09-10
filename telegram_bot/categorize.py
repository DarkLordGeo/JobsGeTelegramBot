"""Keyword-based categorizer for scraped jobs.ge/IT listings.

Not NLP - a simple, extensible ordered list of (category, keywords). The
first category whose keyword appears in the job's position title wins, so
order matters (more specific categories should come before generic ones).
Add keywords/categories here as you notice titles falling into "Other".
"""

# Order matters: checked top to bottom, first match wins. Most job titles on
# jobs.ge are Georgian, so most categories carry both English keywords and
# Georgian word roots (matched as plain substrings, so any grammatical case
# ending still matches - "ადმინისტრატორ" catches "ადმინისტრატორი",
# "ადმინისტრატორს", etc).
CATEGORIES = [
    ("Full-Stack Development", [
        "full stack", "full-stack", "fullstack",
    ]),
    ("Backend Development", [
        "backend", "back-end", "back end", "server-side",
        "node.js", "nodejs", "django", "laravel", "spring boot", "spring",
        ".net developer", "dotnet", "golang developer", "go developer",
        "ruby on rails", "api developer", "php developer", "java developer",
        "python developer", "c++ developer", "c# developer",
    ]),
    ("Frontend Development", [
        "frontend", "front-end", "front end",
        "react developer", "reactjs", "vue developer", "vuejs",
        "angular developer", "javascript developer", "js developer",
        "ui developer", "html/css",
    ]),
    ("Mobile Development", [
        "android", "ios developer", "mobile developer",
        "flutter", "react native", "kotlin developer", "swift developer",
    ]),
    ("Data / ML / Analytics", [
        "data scientist", "data analyst", "data engineer", "data ",
        "machine learning", "ml engineer", "ai engineer", "ai ინჟინ",
        "big data", "sql developer", "business intelligence", "bi developer",
        "ანალიტიკოს",  # analyst
        "მონაცემთა",  # (of) data
        "მეცნიერ",  # scientist
    ]),
    ("QA / Testing", [
        "qa", "quality assurance", "test engineer", "automation engineer",
        "tester", "ტესტერ", "ტესტ",  # tester / test
    ]),
    ("Support / Helpdesk", [
        "support engineer", "helpdesk", "help desk", "technical support",
        "it support", "მხარდაჭერ",  # support
        "ტექნიკოს",  # technician
    ]),
    ("DevOps / Infrastructure", [
        "devops", "sre", "site reliability", "system administrator",
        "sysadmin", "cloud engineer", "infrastructure engineer",
        "kubernetes", "network engineer", "network administrator", "noc",
        "administrator", "ადმინისტრატორ",  # administrator
    ]),
    ("Design / UI-UX", [
        "ui/ux", "ux designer", "ui designer", "product designer",
        "graphic designer", "designer", "დიზაინერ",  # designer
    ]),
    ("Management / Leadership", [
        "project manager", "product manager", "product owner", "scrum master",
        "team lead", "tech lead", "engineering manager", "it manager", "cto",
        "მენეჯერ",  # manager
        "ხელმძღვანელ",  # head of / lead
        "თიმ ლიდ",  # team lead (transliterated)
        "სქრამ მასტერ",  # scrum master (transliterated)
        "პროდუქტის მფლობელ",  # product owner
    ]),
    ("Development (general)", [
        "developer", "programmer", "software engineer", "engineer",
        "angular", "react", "vue.js", "node.js",
        "დეველოპერ", "პროგრამისტ",  # developer, programmer
        "ინჟინ",  # engineer (root - Georgian drops the vowel in some cases,
                   # e.g. "ინჟინერი" -> "ინჟინრის", so match the stable stem)
        "არქიტექტორ",  # architect
    ]),
]

OTHER_CATEGORY = "Other / IT"


def categorize(position: str) -> str:
    """Return the best-matching category name for a job's position title."""
    if not position:
        return OTHER_CATEGORY

    title = position.lower()
    for category, keywords in CATEGORIES:
        if any(keyword in title for keyword in keywords):
            return category

    return OTHER_CATEGORY


def group_by_category(jobs: list[dict]) -> dict[str, list[dict]]:
    """Group a list of job records by categorize(job["position"])."""
    grouped: dict[str, list[dict]] = {}
    for job in jobs:
        category = categorize(job.get("position", ""))
        grouped.setdefault(category, []).append(job)
    return grouped
