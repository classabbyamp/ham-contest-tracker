#!/usr/bin/env python3
"""
app.py

Copyright (C) 2020 ClassAbbyAmp, thxo
Released under the BSD 2-Clause License
"""


from urllib import parse
from io import BytesIO
from datetime import datetime, timedelta
from babel.dates import format_timedelta
from functools import wraps

# import pprint

from flask import Flask, request, render_template, flash, redirect, url_for
from flask_sqlalchemy import SQLAlchemy
from werkzeug.security import generate_password_hash, check_password_hash
import xmltodict as xd


app = Flask(__name__)
# TODO: don't hard-code these
app.secret_key = "asdf"
app.config["SQLALCHEMY_DATABASE_URI"] = "sqlite:////tmp/test.db"
db = SQLAlchemy(app)

# pp = pprint.PrettyPrinter(indent=4)


# DECORATORS
def login_required(f):
    @wraps(f)
    def login_check(*args, **kwargs):
        if request.authorization is None:
            print("No Auth!")
            return "Login Failed: No Authentication"

        username = request.authorization["username"].upper()
        password = request.authorization["password"]
        user = User.query.filter_by(username=username).first()

        if user is None:
            print("invalid username")
            return "Login Failed: Invalid Username"
        if not check_password_hash(user.password, password):
            print("wrong password")
            return "Login Failed: Incorrect Password"

        return f(*args, **kwargs)
    return login_check


# DATABASE TABLES
class User(db.Model):
    uid = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    password = db.Column(db.String(120), nullable=False)

    def __repr__(self):
        type_ = type(self)
        module = type_.__module__
        qualname = type_.__qualname__
        return (f"<{module}.{qualname} object at {hex(id(self))}, "
                f"uid={self.uid}, username={self.username}>")


class LiveScores(db.Model):
    score_id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("user.uid"), nullable=False)
    contest = db.Column(db.String(120), nullable=False)
    callsign = db.Column(db.String(120), nullable=False)
    ops = db.Column(db.String(120), default="")
    qsos = db.Column(db.Integer, default=0)
    points = db.Column(db.Integer, default=0)
    mults = db.Column(db.Integer, default=0)
    score = db.Column(db.Integer, default=0)
    last_updated = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)

    def __repr__(self):
        type_ = type(self)
        module = type_.__module__
        qualname = type_.__qualname__
        return (f"<{module}.{qualname} object at {hex(id(self))}, "
                f"score_id={self.score_id}, contest={self.contest}, callsign={self.callsign}>")


# Init databases
db.drop_all()
db.create_all()


# ROUTING
@app.route("/", methods=["GET"])
def index():
    return render_template("index.html")


@app.route("/scoreboard", methods=["GET"])
def scoreboard():
    data = LiveScores.query.all()
    return render_template("scoreboard.html", data=data)


@app.route("/register", methods=["GET", "POST"])
def register():
    if request.method == "POST":
        username = request.form.get("callsign").upper()
        password = generate_password_hash(request.form.get("password"))
        print(len(password))

        existing_user = User.query.filter_by(username=username).first()
        if existing_user is None:
            user = User(username=username, password=password)
            db.session.add(user)
            db.session.commit()
            flash("Registration successful!")
            return redirect(url_for("index"))

        flash("user already exists")
        return render_template("register.html")
    return render_template("register.html")


@app.route("/", methods=["POST"])
@login_required
def recv_score():
    with BytesIO(parse.unquote_to_bytes(request.data)) as raw_data:
        xml_data = xd.parse(raw_data)

    # pp.pprint(xml_data)
    # print(request.authorization)
    results_data = xml_data["dynamicresults"]

    user_id = User.query.filter_by(username=request.authorization["username"]).first().uid
    contest = results_data["contest"]
    callsign = results_data["call"]
    ops = ", ".join(results_data["ops"].split())
    qsos = results_data["breakdown"]["qso"][-1]["#text"]
    points = results_data["breakdown"]["point"][-1]["#text"]
    mults = sum([int(x["#text"]) for x in results_data["breakdown"]["mult"] if x["@band"] == "total"])
    score = results_data["score"]
    last_updated = datetime.strptime(results_data["timestamp"], "%Y-%m-%d %H:%M:%S")

    existing_row = LiveScores.query.filter_by(contest=results_data["contest"], callsign=results_data["call"]).first()
    if existing_row and existing_row.user_id == user_id:
        existing_row.ops = ops
        existing_row.qsos = qsos
        existing_row.points = points
        existing_row.mults = mults
        existing_row.score = score
        existing_row.last_updated = last_updated
    else:
        data = LiveScores(
            user_id=user_id,
            contest=contest,
            callsign=callsign,
            ops=ops,
            qsos=qsos,
            points=points,
            mults=mults,
            score=score,
            last_updated=last_updated
        )
        db.session.add(data)

    db.session.commit()

    return "Thanks and 73!"


# CUSTOM FILTERS
@app.template_filter()
def fuzzydate(date: datetime):
    delta = date - datetime.utcnow()
    return format_timedelta(delta) + " ago"
