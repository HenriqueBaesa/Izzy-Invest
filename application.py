import os

from cs50 import SQL
from flask import Flask, flash, redirect, render_template, request, session, json
from flask_session import Session
from tempfile import mkdtemp
from werkzeug.exceptions import default_exceptions, HTTPException, InternalServerError
from werkzeug.security import check_password_hash, generate_password_hash
import yfinance
import math

from helpers import apology, login_required, lookup, usd

# Configure application
app = Flask(__name__)

# Ensure templates are auto-reloaded
app.config["TEMPLATES_AUTO_RELOAD"] = True


# Ensure responses aren't cached
@app.after_request
def after_request(response):
    response.headers["Cache-Control"] = "no-cache, no-store, must-revalidate"
    response.headers["Expires"] = 0
    response.headers["Pragma"] = "no-cache"
    return response


# Custom filter
app.jinja_env.filters["usd"] = usd

# Configure session to use filesystem (instead of signed cookies)
app.config["SESSION_FILE_DIR"] = mkdtemp()
app.config["SESSION_PERMANENT"] = False
app.config["SESSION_TYPE"] = "filesystem"
Session(app)

# Configure CS50 Library to use SQLite database
db = SQL("sqlite:///finance.db")

# Make sure API key is set
if not os.environ.get("API_KEY"):
    raise RuntimeError("API_KEY not set")


@app.route("/")
@login_required
def index():
    """Show portfolio of stocks"""

    shares = db.execute("SELECT symbol, qnt FROM shares WHERE user_id = ?", session.get("user_id"))
    grand_total = 0

    for i in range(len(shares)):
        shares[i].update(lookup(shares[i]["symbol"]))
        shares[i]['total'] = shares[i]['price'] * shares[i]['qnt']
        grand_total += shares[i]['total']

    cash_total = db.execute("SELECT cash FROM users WHERE id = ?", session.get("user_id"))[0]['cash']
    grand_total += cash_total

    return render_template("index.html", shares=shares, cash_total=cash_total, grand_total=grand_total)


@app.route("/buy", methods=["GET", "POST"])
@login_required
def buy():
    """Buy shares of stock"""
    if request.method == "POST":

        # error checking

        if not request.form.get("symbol"):
            return apology("must provide symbol")

        if not lookup(request.form.get("symbol")):
            return apology("symbol not found")

        if not request.form.get("shares"):
            return apology("must provide quantity")

        try:
            qnt = int(request.form.get("shares"))
        except ValueError:
            return apology("must be a positive integer")

        if qnt < 1:
            return apology("must be a positive integer")

        share = lookup(request.form.get("symbol"))
        cash = db.execute("SELECT cash FROM users WHERE id = ?", session.get("user_id"))

        if cash[0]["cash"] < share["price"] * qnt:
            return apology("not enough cash")

        # updating database
        user_id = session.get("user_id")
        symbol = request.form.get("symbol").upper()

        if db.execute("SELECT 1 FROM shares WHERE user_id = ? AND symbol = ?", user_id, symbol) != []:
            db.execute("UPDATE shares SET qnt = qnt + ? WHERE user_id = ? AND symbol = ?", qnt, user_id, symbol)
        else:
            db.execute("INSERT INTO shares (user_id, symbol, qnt) VALUES (?, ?, ?)", user_id, symbol, qnt)

        db.execute("INSERT INTO history (user_id, symbol, unit_price, qnt) VALUES (?, ?, ?, ?)",
                   user_id, symbol, share["price"], qnt)   # action: True means bought, False means sold
        db.execute("UPDATE users SET cash = cash - ? WHERE id = ?", share["price"] * qnt, user_id)

        return redirect("/")

    else:
        return render_template("buy.html")


@app.route("/history")
@login_required
def history():
    """Show history of transactions"""

    log = db.execute("SELECT * FROM history WHERE user_id = ?", session.get("user_id"))

    return render_template("history.html", log=log)


@app.route("/login", methods=["GET", "POST"])
def login():
    """Log user in"""

    # Forget any user_id
    session.clear()

    # User reached route via POST (as by submitting a form via POST)
    if request.method == "POST":

        # Ensure username was submitted
        if not request.form.get("username"):
            return apology("must provide username")

        # Ensure password was submitted
        elif not request.form.get("password"):
            return apology("must provide password")

        # Query database for username
        rows = db.execute("SELECT * FROM users WHERE username = ?", request.form.get("username"))

        # Ensure username exists and password is correct
        if len(rows) != 1 or not check_password_hash(rows[0]["hash"], request.form.get("password")):
            return apology("invalid username and/or password")

        # Remember which user has logged in
        session["user_id"] = rows[0]["id"]

        # Redirect user to home page
        return redirect("/")

    # User reached route via GET (as by clicking a link or via redirect)
    else:
        return render_template("login.html")


@app.route("/logout")
def logout():
    """Log user out"""

    # Forget any user_id
    session.clear()

    # Redirect user to login form
    return redirect("/")


@app.route("/quote", methods=["GET", "POST"])
@login_required
def quote():
    if request.method == "POST":
        symbol = request.form.get("symbol")
        time = request.form['time']
    if request.method == "GET":
        time = "Mes"
        symbol = "TSLA"

    share = yfinance.Ticker(symbol)
        
    if(time == "Ano"):
        hist = share.history(period='1y', interval='1mo')
        closeValues = hist["Close"].tolist()
        datesz = hist.index.strftime("%d/%m/%Y").tolist()            
        print(type(datesz))
        i = 0
        for price in closeValues:
            if math.isnan(price):
                closeValues.remove(price)        
                datesz.pop(i)
            i+=1 
    else:
        hist = share.history(period='1mo', interval='1d')
        closeValues = hist["Close"].tolist()
        datesz = hist.index.strftime("%d/%m/%Y").tolist()
        i = 0
        for price in closeValues:
            if math.isnan(price):
                closeValues.remove(price)        
                datesz.pop(i)
            i+=1 
        
    return render_template("quote.html", values = closeValues,dates = datesz,timeGraph = time, Symbol = symbol)



@app.route("/register", methods=["GET", "POST"])
def register():
    """Register user"""

    if request.method == "POST":

        if not request.form.get("username"):
            return apology("must provide username")

        if not request.form.get("password"):
            return apology("must provide password")

        if not request.form.get("confirmation"):
            return apology("must provide confirmation")

        if request.form.get("password") != request.form.get("confirmation"):
            return apology("passwords don't match up")

        if db.execute("SELECT 1 FROM users WHERE username = ?", request.form.get("username")) != []:
            return apology("username already registered")

        db.execute("INSERT INTO users (username, hash) VALUES (?, ?)", request.form.get(
            "username"), generate_password_hash(request.form.get("password")))

        return redirect("/")

    else:
        return render_template("register.html")


@app.route("/change_password", methods=["GET", "POST"])
@login_required
def change_password():
    """Change user password"""

    if request.method == "POST":

        if not request.form.get("password"):
            return apology("must provide password")

        if not request.form.get("confirmation"):
            return apology("must provide confirmation")

        if request.form.get("password") != request.form.get("confirmation"):
            return apology("passwords don't match up")

        db.execute("UPDATE users SET hash = ? WHERE id = ?", generate_password_hash(
            request.form.get("password")), session.get("user_id"))

        session.clear()

        return redirect("/")

    else:
        return render_template("change_password.html")


@app.route("/sell", methods=["GET", "POST"])
@login_required
def sell():
    """Sell shares of stock"""

    if request.method == "POST":

        symbol = request.form.get("symbol")
        user_id = session.get("user_id")

        if symbol == None:
            return apology("must select symbol")

        qnt_possess = db.execute("SELECT qnt FROM shares WHERE user_id = ? AND symbol = ?", user_id, symbol)
        if qnt_possess == []:
            return apology("you do not have this stock")

        qnt_possess = qnt_possess[0]['qnt']

        if not request.form.get("shares"):
            return apology("must provide quantity")

        qnt_to_sell = float(request.form.get("shares"))
        if qnt_to_sell.is_integer() == False or qnt_to_sell < 1:
            return apology("must be a positive integer")

        if qnt_to_sell > qnt_possess:
            return apology("you don't have that many shares")

        if qnt_to_sell == qnt_possess:
            db.execute("DELETE FROM shares WHERE user_id = ? AND symbol = ?", user_id, symbol)
        else:
            db.execute("UPDATE shares SET qnt = qnt - ? WHERE symbol = ? AND user_id = ?", qnt_to_sell, symbol, user_id)

        price = lookup(symbol)["price"]

        db.execute("UPDATE users SET cash = cash + ? WHERE id = ?", price * qnt_to_sell, user_id)

        db.execute("INSERT INTO history (user_id, symbol, unit_price, qnt) VALUES (?, ?, ?, ?)", user_id, symbol, price, -qnt_to_sell)

        return redirect("/")

    else:

        symbols = db.execute("SELECT symbol FROM shares WHERE user_id = ?", session.get("user_id"))
        symbols = [d['symbol'] for d in symbols]

        return render_template("sell.html", symbols=symbols)


def errorhandler(e):
    """Handle error"""
    if not isinstance(e, HTTPException):
        e = InternalServerError()
    return apology(e.name, e.code)


# Listen for errors
for code in default_exceptions:
    app.errorhandler(code)(errorhandler)
