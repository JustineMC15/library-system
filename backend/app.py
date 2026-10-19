from flask import Flask, redirect
from config import FRONTEND_DIR
from routes.books import books_bp

# static_folder makes Flask hand out the pages in frontend/, so the site and the data share one address
app = Flask(__name__, static_folder=str(FRONTEND_DIR), static_url_path="")
app.secret_key = "change-this-before-submission"   # needed later for login sessions

app.register_blueprint(books_bp)                    # add each new routes/ file here


@app.route("/")
def home():
    return redirect("/student/login.html")          # we have no landing page of our own


if __name__ == "__main__":
    app.run(debug=True)
