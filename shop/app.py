"""ShopEasy: a small e-commerce site used as the application under test (AUT).

Test account: tester@shop.com / Test@123

Set SHOP_BUGS (comma separated) to switch on deliberate defects for testing:
  checkout_address  -> checkout accepts invalid delivery addresses
  api_login         -> /api/login accepts a wrong password for the test account
"""
import itertools
import os
import re
from functools import wraps

from flask import (Flask, flash, jsonify, redirect, render_template, request,
                   session, url_for)
from itsdangerous import BadSignature, SignatureExpired, URLSafeTimedSerializer
from werkzeug.security import check_password_hash, generate_password_hash

TEST_EMAIL = "tester@shop.com"
TEST_PASSWORD = "Test@123"
EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")

PRODUCTS = [
    {"id": 1, "name": "Wireless Mouse", "price": 799},
    {"id": 2, "name": "Mechanical Keyboard", "price": 2999},
    {"id": 3, "name": "Laptop Stand", "price": 1499},
    {"id": 4, "name": "USB-C Hub", "price": 1899},
    {"id": 5, "name": "Noise Cancelling Headphones", "price": 5999},
    {"id": 6, "name": "Laptop Backpack", "price": 1999},
    {"id": 7, "name": "Webcam HD", "price": 2499},
    {"id": 8, "name": "Gaming Laptop", "price": 74999},
]


def search_products(query):
    q = (query or "").strip().lower()
    return [p for p in PRODUCTS if q in p["name"].lower()]


def validate_login(email, password):
    if not email or not password:
        return "Email and password are required."
    if not EMAIL_RE.match(email):
        return "Enter a valid email address."
    if len(password) < 6:
        return "Password must be at least 6 characters."
    return None


def create_app(test_config=None):
    app = Flask(__name__)
    bugs = {b.strip() for b in os.environ.get("SHOP_BUGS", "").split(",") if b.strip()}
    app.config.update(
        SECRET_KEY=os.environ.get("SHOP_SECRET_KEY", "shop-dev-secret"),
        BUGS=bugs,
    )
    if test_config:
        app.config.update(test_config)
    app.config["BUGS"] = set(app.config["BUGS"])
    test_hash = generate_password_hash(TEST_PASSWORD)
    serializer = URLSafeTimedSerializer(app.config["SECRET_KEY"])
    order_seq = itertools.count(1001)

    def credentials_ok(email, password):
        return email.strip().lower() == TEST_EMAIL and check_password_hash(test_hash, password)

    def login_required(view):
        @wraps(view)
        def wrapped(*a, **kw):
            if "email" not in session:
                return redirect(url_for("login"))
            return view(*a, **kw)
        return wrapped

    def cart_lines():
        lines = []
        for pid, qty in session.get("cart", {}).items():
            product = next((p for p in PRODUCTS if p["id"] == int(pid)), None)
            if product:
                lines.append({"product": product, "qty": qty, "subtotal": product["price"] * qty})
        return lines

    @app.context_processor
    def inject_cart_count():
        return {"cart_count": sum(session.get("cart", {}).values())}

    # ------------------------- web pages -------------------------
    @app.route("/")
    def index():
        return redirect(url_for("products" if "email" in session else "login"))

    @app.route("/login", methods=["GET", "POST"])
    def login():
        if request.method == "POST":
            email = request.form.get("email", "").strip()
            password = request.form.get("password", "")
            error = validate_login(email, password)
            if error:
                flash(error, "error")
            elif credentials_ok(email, password):
                session.clear()
                session["email"] = email.lower()
                return redirect(url_for("products"))
            else:
                flash("Invalid email or password.", "error")
        return render_template("login.html")

    @app.route("/logout")
    def logout():
        session.clear()
        flash("You have been logged out.", "success")
        return redirect(url_for("login"))

    @app.route("/products")
    @login_required
    def products():
        q = request.args.get("q", "").strip()
        return render_template("products.html", products=search_products(q), q=q)

    @app.post("/cart/add/<int:pid>")
    @login_required
    def add_to_cart(pid):
        product = next((p for p in PRODUCTS if p["id"] == pid), None)
        if product:
            cart = session.get("cart", {})
            cart[str(pid)] = cart.get(str(pid), 0) + 1
            session["cart"] = cart
            flash(f"Added {product['name']} to cart.", "success")
        return redirect(url_for("products", q=request.form.get("q", "")))

    @app.route("/cart")
    @login_required
    def cart():
        lines = cart_lines()
        return render_template("cart.html", lines=lines, total=sum(l["subtotal"] for l in lines))

    @app.post("/cart/remove/<int:pid>")
    @login_required
    def remove_from_cart(pid):
        cart = session.get("cart", {})
        cart.pop(str(pid), None)
        session["cart"] = cart
        return redirect(url_for("cart"))

    @app.route("/checkout", methods=["GET", "POST"])
    @login_required
    def checkout():
        lines = cart_lines()
        if not lines:
            flash("Your cart is empty.", "error")
            return redirect(url_for("products"))
        total = sum(l["subtotal"] for l in lines)
        if request.method == "POST":
            name = request.form.get("full_name", "").strip()
            address = request.form.get("address", "").strip()
            error = None
            if not name:
                error = "Full name is required."
            elif "checkout_address" not in app.config["BUGS"] and len(address) < 10:
                error = "Enter a valid delivery address (at least 10 characters)."
            if error:
                flash(error, "error")
            else:
                session["last_order"] = f"ORD-{next(order_seq)}"
                session["cart"] = {}
                return redirect(url_for("order_confirmation"))
        return render_template("checkout.html", lines=lines, total=total)

    @app.route("/order-confirmation")
    @login_required
    def order_confirmation():
        order = session.get("last_order")
        if not order:
            return redirect(url_for("products"))
        return render_template("confirmation.html", order=order)

    # --------------------------- JSON API ---------------------------
    @app.get("/api/health")
    def api_health():
        return jsonify(status="ok")

    @app.get("/api/products")
    def api_products():
        return jsonify(search_products(request.args.get("q", "")))

    @app.get("/api/products/<int:pid>")
    def api_product(pid):
        product = next((p for p in PRODUCTS if p["id"] == pid), None)
        if not product:
            return jsonify(error="Product not found"), 404
        return jsonify(product)

    @app.post("/api/login")
    def api_login():
        data = request.get_json(silent=True) or {}
        email = (data.get("email") or "").strip()
        password = data.get("password") or ""
        error = validate_login(email, password)
        if error:
            return jsonify(error=error), 400
        wrong_pw_ok = ("api_login" in app.config["BUGS"]
                       and email.lower() == TEST_EMAIL)  # deliberate defect
        if credentials_ok(email, password) or wrong_pw_ok:
            return jsonify(token=serializer.dumps({"email": email.lower()})), 200
        return jsonify(error="Invalid email or password"), 401

    return app


if __name__ == "__main__":
    create_app().run(host="0.0.0.0", port=int(os.environ.get("PORT", 5000)))
