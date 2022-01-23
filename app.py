from flask import (  # type:ignore
    Flask,
    render_template,
    request,
    g,
    flash,
    redirect,
    jsonify,
)
import sqlite3

from flask_login import (  # type:ignore
    LoginManager,
    login_user,
    UserMixin,
    current_user,
    logout_user,
)
from datetime import datetime, date
import os
from os.path import join, dirname
from dotenv import load_dotenv, find_dotenv  # type:ignore
from filestack import Client, Security, Filelink  # type:ignore

load_dotenv(find_dotenv())
APIKEY = os.environ.get("APIKEY")
APPSECRET = os.environ.get("APPSECRET")
HANDLE = os.environ.get("HANDLE")

policy = {"expiry": 1735689600, "handle": HANDLE}
security = Security(policy, APPSECRET)


DATABASE = "mhd.db"
login_manager = LoginManager()
app = Flask(__name__)
login_manager.init_app(app)
app.config.update(TESTING=True, DEBUG=True, SECRET_KEY='_5#y2L"F4Q8z')


class User(UserMixin):
    pass


def get_db():
    db = getattr(g, "_database", None)
    if db is None:
        db = g._database = sqlite3.connect(DATABASE)
    return db


def count_users():
    cursor = get_db().execute("SELECT MAX(ID) FROM USERS")
    for row in cursor:
        cu = row[0]
        if cu is None:
            cu = 0
        return cu
    return 0


def calculate(date):
    date = datetime.strptime(date, "%Y-%m-%d")
    diffdate = date - datetime.today()
    return -diffdate.days if diffdate.days < 0 else 0


@login_manager.user_loader
def load_user(user_id):
    user = User()
    user.id = user_id
    return user


def insert_user(name, password):
    global users
    users = count_users()
    get_db().execute(
        "INSERT INTO USERS (ID,NAME,PASSWORD)             VALUES ("
        + str(users + 1)
        + ", '"
        + name
        + "', '"
        + password
        + "')"
    )

    get_db().commit()
    print(f"User {name} created")
    users += 1

    filelink = Filelink(HANDLE)

    filelink.overwrite(filepath=DATABASE, security=security)
    filelink.signed_url(security=security)

    filelink.download(DATABASE)


@app.teardown_appcontext
def close_connection(exception):
    db = getattr(g, "_database", None)
    if db is not None:
        db.close()


def insert_entry(id, currentdate, mhd, points):
    get_db().execute(
        "INSERT INTO PROTOCOLL (ID,CURRENTDATE,MHD,POINTS)             VALUES ("
        + str(id)
        + ", '"
        + currentdate
        + "', '"
        + mhd
        + "', "
        + str(points)
        + ")"
    )

    get_db().commit()
    print(f"Entry with id {id} created")

    filelink = Filelink(HANDLE)

    filelink.overwrite(filepath=DATABASE, security=security)
    filelink.signed_url(security=security)

    filelink.download(DATABASE)


@app.route("/create", methods=["POST", "GET"])
def create():
    if request.method == "POST":
        if request.form["password"] == request.form["passwordrepeat"]:
            try:
                filelink = Filelink(HANDLE)
                filelink.download(DATABASE)
                insert_user(request.form["username"], request.form["password"])
                correct, id_ = check_password(
                    request.form["username"], request.form["password"]
                )
                user = User()
                user.id = id_
                login_user(user)
                return redirect("/mhd", code=302)
            except:
                flash("Username taken")
        else:
            flash("Passwords don't match")

    return render_template("Profil.html")


def check_password(name, password):
    cursor = get_db().execute(
        "SELECT COUNT(1), ID FROM USERS             WHERE name = '"
        + name
        + "'             AND password = '"
        + password
        + "'"
    )
    for row in cursor:
        return row[0], row[1]
    return False, None


def total_points(id):
    cursor = get_db().execute(
        "SELECT SUM(Points) FROM Protocoll                   WHERE id = " + str(id)
    )

    for row in cursor:
        total = row[0]
        if total is None:
            total = 0

        return total


@app.route("/login", methods=["POST", "GET"])
def login():
    if request.method == "POST":
        filelink = Filelink(HANDLE)
        filelink.download(DATABASE)
        correct, id_ = check_password(
            request.form["username"], request.form["password"]
        )
        if bool(correct):
            user = User()
            user.id = id_
            login_user(user)
            return redirect("/mhd", code=302)
        else:
            flash("Username doesn't exist/Wrong Password")

    return render_template("Einloggen.html")


@app.route("/mhd", methods=["POST", "GET"])
def mhd():
    if request.method == "POST":
        if request.form["date"] == "":
            flash("Enter a Date")
        else:
            points = calculate(request.form["date"])
            insert_entry(
                current_user.id, str(datetime.today()), request.form["date"], points
            )
            return redirect("/points/" + str(points), code=302)

    return render_template("index.html")


@app.route("/points/<pluspoints>")
def points(pluspoints):
    return render_template(
        "Punkte_2.html", pluspoints=pluspoints, total=total_points(current_user.id)
    )


@app.route("/")
def home():
    try:
        return render_template("Punkte.html", total=total_points(current_user.id))
    except:
        return redirect("/create")


@app.route("/logout")
def logout():
    logout_user()
    if os.path.exists(DATABASE):
        os.remove(DATABASE)
    return redirect("/create", code=302)


@app.route("/spiele")
def spiele():
    return render_template("Spielesammlung.html")


@app.route("/totalpoints")
def totalpoints():
    return jsonify(total_points(current_user.id))


@app.route("/minuspoints/<points>")
def minuspoints(points):
    insert_entry(
        current_user.id,
        date.today().strftime("%d.%m.%Y"),
        date.today().strftime("%d.%m.%Y"),
        -int(points),
    )
    return totalpoints()


@app.route("/game")
def game():
    return render_template("game.html")


@app.errorhandler(404)
def page_not_found(e):
    # note that we set the 404 status explicitly
    return render_template("404.html"), 404


if __name__ == "__main__":
    app.run(debug=True)
