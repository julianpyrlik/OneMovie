import requests
from flask import Flask, render_template, redirect, url_for, request, session
from flask_session import Session
from flask_bootstrap import Bootstrap5
from country_data import country_dict
import random
import os

app = Flask(__name__)
# essential for securing your application's sessions, cookies, and cryptographic functions
app.config['SECRET_KEY'] = os.environ.get('SECRET')
# configure session
app.config["SESSION_PERMANENT"] = False
app.config["SESSION_TYPE"] = "filesystem"
Session(app)

Bootstrap5(app)

# API configuration
movie_db_endpoint = "https://api.themoviedb.org/3/discover/movie?"
movie_db_person_endpoint = "https://api.themoviedb.org/3/search/person?"

headers = {
    "accept": "application/json",
    "Authorization": os.environ.get('MOVIE_DB_API_KEY')
}

# -------------------------------create constants---------------------------------------
SERVICE_LIST = ["Netflix", "Amazon Prime Video", "Disney Plus", "Apple TV Plus"]
STREAMING_LINKS = {
    "Netflix": "https://www.netflix.com/",
    "Amazon Prime Video": "https://www.primevideo.com/",
    "Disney Plus": "https://www.disneyplus.com/",
    "Apple TV Plus": "https://www.apple.com/apple-tv-plus/"
}

GENRE_LIST = {
    "Action": 28,
    "Drama": 18,
    "Comedy": 35,
    "Horror": 27,
    "Romance": 10749
}
DECADES = {
    "Before 1950": ["1000-01-01", "1951-01-01"],
    "1950 - 1970": ["1950-01-01", "1971-01-01"],
    "1970 - 2000": ["1970-01-01", "2001-01-01"],
    "2000 - today": ["2000-01-01", "3000-01-01"]
}

LENGTH_LIST = {
    "Short (-90min)": [0, 90],
    "Medium (90-120min)": [90, 120],
    "Long (120+min)": [120, 600]
}


# --------------------------------create functions---------------------------------------

@app.route("/")
def home():
    session.clear()
    print("session cleared")
    return render_template("index.html", service_list=SERVICE_LIST, genre_list=GENRE_LIST, decades=DECADES,
                           lengths=LENGTH_LIST)


@app.route("/result", methods=["POST", "GET"])
def result():
    if request.method == "POST":
        # ----------------get the form data and handle default values-------------------------------
        name = request.form.get("name")
        country = request.form.get("country")
        decade = request.form.get("decade")
        genres = request.form.getlist("genre")  # list
        streaming_services = request.form.getlist("streaming_services")  # list
        length = request.form.get("length")
        min_rating = request.form.get("rating")
        print(f"length {length} decade {decade}")

        # lower case country
        if country:
            country = country.lower()

        # RATING
        if not min_rating:
            min_rating = 5

        # store rating in session if it doesn't exist yet
        if 'min_rating' not in session:
            session['min_rating'] = min_rating
        else:
            min_rating = session['min_rating']

        # LENGTH
        if length:
            min_length = LENGTH_LIST[length][0]
            max_length = LENGTH_LIST[length][1]
        else:
            min_length = 0
            max_length = 6000

        # store length in session if it doesn't exist yet
        if 'min_length' not in session:
            session['min_length'] = min_length
            session['max_length'] = max_length
        else:
            min_length = session['min_length']
            max_length = session['max_length']

        # YEARS
        if decade:
            minimal_year = DECADES[decade][0]
            maximal_year = DECADES[decade][1]
        else:
            minimal_year = 0
            maximal_year = 3000

        # store minimal and maximal year in session if it doesn't exist yet
        if 'minimal_year' not in session:
            session['minimal_year'] = minimal_year
            session['maximal_year'] = maximal_year
        else:
            minimal_year = session['minimal_year']
            maximal_year = session['maximal_year']

        print(f"minimal year {minimal_year}")
        print(f"maximal year {maximal_year}")

        # STREAMING SERVICES
        # if no streaming services are selected, use the default ones
        if not streaming_services:
            streaming_services = ["Netflix", "Amazon Prime Video", "Disney Plus", "Apple TV Plus"]
        # if session doesn't exist yet, store the streaming services in it
        if 'streaming_services' not in session:
            session['streaming_services'] = streaming_services

        # COUNTRY CODE
        try:
            country_code = country_dict[country]
        except KeyError:
            country_code = "US"

        # store country code in session
        if 'country_code' not in session:
            session['country_code'] = country_code

        # 1. PERSON_ID
        # I first need to get the Person ID so that I can get the name
        # for this I need to use the other mdb endpoint
        if name:
            parameter_person = {
                "query": name
            }
            response = requests.get(movie_db_person_endpoint, headers=headers, params=parameter_person)
            person_data = response.json()
            if person_data["results"]:
                person_id = person_data["results"][0]["id"]
                person_not_found_message = ""
            else:
                person_id = ""
                person_not_found_message = "Person not found, but here is another movie you might like"
        else:
            person_id = ""
            person_not_found_message = ""

        # 2. GENRES
        # creating a list with all the genre ids that the user put in
        genres_mdb = []  # stays like that if no genres are input

        if len(genres) != 0:  # if the user put in at least 1 genre
            for genre in genres:
                genre_id = GENRE_LIST[genre]
                genres_mdb.append(f"{genre_id}")
        else:  # add all genres
            for genre_name, genre_id in GENRE_LIST.items():
                genres_mdb.append(f"{genre_id}")

        # store genres in session
        if 'genres_mdb' not in session:
            session['genres_mdb'] = genres_mdb
        else:
            genres_mdb = session['genres_mdb']

        print(f"genres: {genres_mdb}")

        def movie_db_request(page):
            """Searches for movies on the movie db api and returns the data."""
            # setting parameters for the api request
            parameters = {
                "page": page,  # for now
                "sort_by": "popularity.desc",
                "vote_count.gte": 500,  # depending on if box office or rating
                "with_genres": genres_mdb,
                "language": "en-US",
                "release_date.gte": minimal_year,
                "release_date.lte": maximal_year,
                "with_original_language": "en",
                "with_runtime.gte": min_length,
                "with_runtime.lte": max_length,
                "vote_average.gte": min_rating
            }
            # Add "with_crew" parameter if person_id exists
            if person_id:
                parameters["with_crew"] = person_id
            response = requests.get(movie_db_endpoint, headers=headers, params=parameters)
            return response.json()

        # -------------------------movie db API request------------------------------------------------------
        # if its the first request, make the request to get the total pages and add them to the session
        if not session.get('movie_results'):
            movie_db_data = movie_db_request(1)
            pages = movie_db_data["total_pages"]
            session['pages'] = pages  # can't exist yet so it's safe to overwrite


            print(f"pages: {pages}")
        print(f"streamingservices {streaming_services}")

        if "current_page" not in session:
            session["current_page"] = 1  # only the first time

        while session["current_page"] <= session["pages"]:  # as long as there are pages left
            # make the API request for the next 5 pages depending on the current page and replace the movie_db_data with the result
            # only if current results didn't give any movie
            # if current page is smaller than the total pages make the request for the next page and delete the old data
            movie_db_data = movie_db_request(session["current_page"])  # Pageflip

            print(f"current page: {session['current_page']}")
            print(f"movie_db_data: {movie_db_data}")

            # check if the data is empty and there are no matches
            if not movie_db_data["results"]:
                return redirect(url_for("no_result"))

            # all movies that fit parameters (except streaming)
            if session.get('movie_results'):  # repeated search
                print(f"SESSION MOVIE RESULT 1 {session.get('movie_results')}")
                movie_results = session.get('movie_results')
                session['movie_results'] = movie_results  # connects it
            else:  # 1st search
                print("SESSION MOVIE RESULT 1 EMPTY")
                movie_results = movie_db_data["results"]  # creating a new movie_results
                print("Movie DB Data Results:", movie_db_data["results"])  # Add this line for debugging
                session['movie_results'] = movie_results  # connects it

            print(f"SESSION MOVIE RESULTS 2 {session.get('movie_results')}")
            print(f"movie_results before loop {movie_results}")

            # else  if there are matches
            # now find out if there are flatrate matches
            # ---------------------- find movie -----------------------------------------------------------

            print(f"current_page: {session["current_page"]}")
            while movie_results:  # as long as there are results left
                # def final_search
                # pick a random index
                random_index = random.randint(0, len(movie_results) - 1)
                # get the selected movie using the random index
                selected_movie = movie_results[random_index]

                del movie_results[random_index]  # also deletes the movie from the session
                # delete the selected movie from the list
                print(f"length result list: {len(movie_results)}")
                print(f"result list:{movie_results}")
                print(f"streaming services {streaming_services}")
                # exists in any case

                if session.get('movie_results') and session.get('movie_results') is not None and random_index < len(
                        session['movie_results']):
                    # Delete the selected movie from session['movie_results']
                    # del session['movie_results'][random_index]
                    print(f"length session list: {len(session['movie_results'])}")
                    print(f"session list:{session['movie_results']}")

                # after this the both might be empty but the selected movie exists
                # put it into the streaming api
                movie_id = selected_movie["id"]

                streaming_api_endpoint = f"https://api.themoviedb.org/3/movie/{movie_id}/watch/providers"
                print(f"endpoint {streaming_api_endpoint}")
                response = requests.get(streaming_api_endpoint, headers=headers)
                streaming_data = response.json()  # streaming data for 1 movie
                # if matched: display
                # try to find out if there is a flatrate list and if yes, check if it is our service
                try:
                    if streaming_data["results"][session['country_code']]["flatrate"]:
                        flatrate_list = streaming_data["results"][session['country_code']]["flatrate"]

                        for flatrate in flatrate_list:
                            if flatrate["provider_name"] in session['streaming_services']:
                                streaming_service = flatrate["provider_name"]
                                title = selected_movie["original_title"]
                                year = selected_movie["release_date"].split("-")[0]
                                streaming_link = STREAMING_LINKS[streaming_service]
                                streaming_logo_path = flatrate["logo_path"]
                                return render_template("result.html", movie=title, year=year,
                                                       streaming=streaming_service, country=session['country_code'],
                                                       poster_path=selected_movie["poster_path"],
                                                       plot=selected_movie["overview"],
                                                       streaming_link=streaming_link,
                                                       streaming_logo=streaming_logo_path,
                                                       not_found=person_not_found_message)
                except KeyError:
                    print("key error and thus no result, next")
            # if this while loop is left without returning anything it means that the first page didnt have a match
            # and we need to go to the next page
            session["current_page"] += 1

        # if movie_results got empty
        return redirect(url_for("no_result"))

    else:  # If method is GET
        return redirect(url_for("home"))


@app.route("/no-result")
def no_result():
    message = "no more results"
    return render_template("no_result.html", message=message)


if __name__ == "__main__":
    app.run(debug=False, port=5002)
