import json
from datetime import date

# todo
# // solve problem for the updating last element in array
# // sort the dictionary according the count
# // one solution is to did as before to sort list and then update object according to that list

# todo
# ? we kinda solved but performance is still an issue lol
# ? it works but does not mean that we should not make it better
# ? solution would look so that we would just sort dictionary instead of transforming it as list and so on

# * todo is going to be that take care of performance of current code
# * todo is going to be also to create company profiles available jobs
# * todo is going to be clean data of scrapy


def main():
    top_jobs("database/jobs_data.json", "database/top_jobs")
    daily_analytics("database/jobs_data.json", "database/daily_analytics.ndjson")
    print("updated analytics")


def top_jobs(file_name, output):

    with open(file_name, "r", encoding="utf-8") as file:
        # print("Found file!")
        data = json.load(file)
    position = [i["position"] for i in data]

    # company = [i["company"] for i in data]

    """
     using set to have unique elements to then manage to count actual amount of elements
     this might be not readable but here is the point
     we get dictionary first which we transform as list and then struc_arr is
     getting populated by position and data count
    """

    struc_arr = [
        [i, position.count(i)] for i in list(map(lambda x: x, {i for i in position}))
    ]
    sorted_data = sorted(struc_arr, key=lambda count: count[1])
    dict_list = [{"position": i[0], "count": i[1]} for i in sorted_data]
    with open(f"{output}.json", "w", encoding="utf-8") as f:
        json.dump(dict_list[::-1], f, ensure_ascii=False, indent=4)


def daily_analytics(file_name, output):
    # print(input, output)
    with open(file_name, "r", encoding="utf-8") as file:
        data = json.load(file)
        data_length = len(data)
    with open(output, "a", encoding="utf-8") as f:
        today = str(date.today())
        date_analytic = {"date": today, "available_jobs": data_length}
        # json.dumps(date_analytic, separators=(",", ":"), ensure_ascii=False, indent=4 )
        print(json.dumps(date_analytic, separators=(",", ":")), file=f)


if __name__ == "__main__":
    main()


# {
#     "data": [
#         {
#             "date": "2025-10-18",
#             "job_count": 124
#         },
#         {
#             "date": "2025-10-18",
#             "job_count": 124
#         }
#     ]
# }


# def tag_generation():
#     """

#     tag generation would work so that we will generate tags for
#     most frequent jobs, let's say top 10 frequent job based on the top jobs functionality whic
#     will take care of writing that to a sorted.json
#     am thinking how can we make it functional for frontend search bar
#     i mean how can we attach some tags for certain jobs
#     maybe use gemini for generating tags?
#     i think tag searching system is more complex than that lol

#     i have no idea about this line

#     maybe add autocomplete since it might be easier to search that
#     or fuzzy search and not tag search

#     also time based filters are kind of out of hand since we got georgian names for months and not english


#     one thing is left to create company profiles with jobs available for it


#     chill out, this is just junior dev's project lol .

#     """
#     pass
