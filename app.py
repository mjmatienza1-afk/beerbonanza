from flask import Flask, render_template, request, redirect, url_for, session, flash
from werkzeug.security import generate_password_hash, check_password_hash
from flask_sqlalchemy import SQLAlchemy

app = Flask(__name__)
app.secret_key = "beerbonanza"

app.config['SQLALCHEMY_DATABASE_URI'] = 'mysql+pymysql://root:@localhost/beerbonanza'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
db = SQLAlchemy(app)

class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    password_hash = db.Column(db.String(200), nullable=False)
    role = db.Column(db.String(20), default="user")

    def set_password(self, password):
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        return check_password_hash(self.password_hash, password)


class Item(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), unique=True, nullable=False)
    price = db.Column(db.Integer, nullable=False)
    category = db.Column(db.String(20), nullable=False)


class Order(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False)
    timestamp = db.Column(db.DateTime, default=db.func.current_timestamp())
    status = db.Column(db.String(20), default="pending") 

    user = db.relationship("User", backref=db.backref("orders", cascade="all, delete-orphan"))
    ordered_items = db.relationship("OrderedItem", backref="order", cascade="all, delete-orphan")


class OrderedItem(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    order_id = db.Column(db.Integer, db.ForeignKey("order.id"), nullable=False)
    item_id = db.Column(db.Integer, db.ForeignKey("item.id"), nullable=False)
    quantity = db.Column(db.Integer, nullable=False)

    item = db.relationship("Item")

with app.app_context():
    db.create_all()

    items_data = {
        "Malt Beer": (180, "beer"),
        "Ale": (200, "beer"),
        "Bock Beer": (180, "beer"),
        "Pilsner": (200, "beer"),
        "Pale Lager": (210, "beer"),
        "Dark Lager": (190, "beer"),
        "French Fries": (80, "side"),
        "Onion Rings": (100, "side"),
        "Beef BBQ": (140, "side"),
        "Roasted Chicken": (1000, "side"),
        "Fried Mesentary": (150, "side"),
        "Grilled Tuna": (250, "side"),
    }

    for name, (price, category) in items_data.items():
        if not Item.query.filter_by(name=name).first():
            db.session.add(Item(name=name, price=price, category=category))

    if not User.query.filter_by(username="admin").first():
        admin = User(username="admin", role="admin")
        admin.set_password("admin")
        db.session.add(admin)

    if not User.query.filter_by(username="newadmin").first():
        newadmin = User(username="newadmin", role="admin")
        newadmin.set_password("newadmin")
        db.session.add(newadmin)

    db.session.commit()

@app.route("/signup", methods=["GET", "POST"])
def signup():
    if request.method == "POST":
        username = request.form["username"]
        password = request.form["password"]
        if User.query.filter_by(username=username).first():
            flash("Username already exists", "error")
        else:
            new_user = User(username=username)
            new_user.set_password(password)
            db.session.add(new_user)
            db.session.commit()
            flash("Account created! Please login.", "success")
            return redirect(url_for("login"))
    return render_template("signup.html")


@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        username = request.form["username"]
        password = request.form["password"]

        user = User.query.filter_by(username=username).first()
        if user and user.check_password(password):
            session["user_id"] = user.id
            session["username"] = user.username
            session["role"] = user.role
            session["cart_items"] = []
            flash("Logged in successfully!", "success")

            if user.role == "admin":
                return redirect(url_for("admin_dashboard"))
            return redirect(url_for("index"))
        else:
            flash("Invalid username or password", "error")
    return render_template("login.html")


@app.route("/logout")
def logout():
    session.clear()
    flash("Logged out successfully", "success")
    return redirect(url_for("index"))

@app.route("/admin")
def admin_dashboard():
    if session.get("role") != "admin":
        flash("Access denied", "error")
        return redirect(url_for("index"))

    items = Item.query.all()
    orders = Order.query.filter_by(status="pending").order_by(Order.timestamp.desc()).all() 
    users = User.query.all()
    tab = request.args.get("tab", "users")

    return render_template(
        "admin_dashboard.html",
        items=items,
        orders=orders,
        users=users,
        tab=tab
    )


@app.route("/admin/add_item", methods=["POST"])
def add_item():
    if session.get("role") != "admin":
        return redirect(url_for("index"))

    name = request.form["name"]
    price = request.form["price"]
    category = request.form["category"]

    db.session.add(Item(name=name, price=price, category=category))
    db.session.commit()
    flash("Item added successfully", "success")
    return redirect(url_for("admin_dashboard", tab="items"))


@app.route("/admin/delete_item/<int:item_id>", methods=["POST"])
def delete_item(item_id):
    if session.get("role") != "admin":
        return redirect(url_for("index"))

    item = Item.query.get(item_id)
    db.session.delete(item)
    db.session.commit()
    flash("Item deleted", "success")
    return redirect(url_for("admin_dashboard", tab="items"))


@app.route("/admin/delete_user/<int:user_id>", methods=["POST"])
def delete_user(user_id):
    if session.get("role") != "admin":
        flash("Access denied", "error")
        return redirect(url_for("index"))

    user = User.query.get(user_id)
    if user.username == "admin":
        flash("Cannot delete admin", "error")
        return redirect(url_for("admin_dashboard", tab="users"))

    db.session.delete(user)
    db.session.commit()
    flash("User deleted", "success")
    return redirect(url_for("admin_dashboard", tab="users"))


@app.route("/admin/finish_order/<int:order_id>", methods=["POST"])
def finish_order(order_id):
    if session.get("role") != "admin":
        flash("Access denied", "error")
        return redirect(url_for("index"))

    order = Order.query.get(order_id)
    if order:
        order.status = "finished"
        db.session.commit()
        flash("Order finished!", "success")
        
    return redirect(url_for("admin_dashboard", tab="orders"))


@app.route("/cancel_order/<int:order_id>", methods=["POST"])
def cancel_order(order_id):
    user_id = session.get("user_id")
    if not user_id:
        flash("You must log in to cancel an order", "error")
        return redirect(url_for("login"))

    order = Order.query.filter_by(id=order_id, user_id=user_id).first()
    if not order:
        flash("Order not found or you do not have permission to cancel it", "error")
        return redirect(url_for("index"))

    if order.status != "pending":
        flash("Cannot cancel a completed or cancelled order", "error")
        return redirect(url_for("index"))

    order.status = "cancelled"
    db.session.commit()
    flash("Order cancelled successfully", "success")
    return redirect(url_for("index", open_orders=1))

@app.route("/delete_order/<int:order_id>", methods=["POST"])
def delete_order(order_id):

    user_id = session.get("user_id")

    if not user_id:
        flash("You must log in first", "error")
        return redirect(url_for("login"))

    order = Order.query.filter_by(id=order_id, user_id=user_id).first()

    if not order:
        flash("Order not found", "error")
        return redirect(url_for("order_history"))

    if order.status == "pending":
        flash("You cannot delete an active order", "error")
        return redirect(url_for("order_history"))

    db.session.delete(order)
    db.session.commit()

    flash("Order removed from history", "success")
    return redirect(url_for("order_history"))

@app.route("/order_history")
def order_history():

    user_id = session.get("user_id")

    if not user_id:
        flash("Please login first", "error")
        return redirect(url_for("login"))

    orders = Order.query.filter(
        Order.user_id == user_id,
        Order.status != "pending"
    ).order_by(Order.timestamp.desc()).all()

    return render_template("order_history.html", orders=orders)

@app.route("/", methods=["GET", "POST"])
def index():
    user_id = session.get("user_id")
    user = session.get("username", "guest")
    cart_items = session.get("cart_items", [])

    if request.method == "POST":
        action = request.form.get("action")

        if action in ["add", "remove"]:
            if not user_id:
                flash("You must log in to add items to cart", "error")
                return redirect(url_for("login"))

            item_name = request.form.get("item")
            quantity = int(request.form.get("quantity", 1))
            item = Item.query.filter_by(name=item_name).first()
            if not item:
                flash("Item not found", "error")
                return redirect(url_for("index"))

            if action == "add":
                found = False
                for c in cart_items:
                    if c['item_id'] == item.id:
                        c['quantity'] += quantity
                        found = True
                        break
                if not found:
                    cart_items.append({
                        "item_id": item.id,
                        "name": item.name,
                        "quantity": quantity,
                        "price": item.price
                    })
                session["cart_items"] = cart_items

            elif action == "remove":
                cart_items = [c for c in cart_items if c['item_id'] != item.id]
                session["cart_items"] = cart_items

        elif action == "order":
            if not user_id:
                flash("You must log in to place an order", "error")
                return redirect(url_for("login"))

            if not cart_items:
                flash("Your cart is empty", "error")
                return redirect(url_for("index"))

            order = Order(user_id=user_id)
            db.session.add(order)
            db.session.commit()

            for c in cart_items:
                ordered_item = OrderedItem(
                    order_id=order.id,
                    item_id=c['item_id'],
                    quantity=c['quantity']
                )
                db.session.add(ordered_item)
            db.session.commit()

            session["cart_items"] = []
            flash("Order placed successfully!", "success")
            return redirect(url_for("index", open_orders=1))

        return redirect(url_for("index", open_cart=1))

    if user_id:
        orders = Order.query.filter_by(user_id=user_id,status="pending").order_by(Order.timestamp.desc()).all()
    else:
        orders = []

    total_price = sum(c['price'] * c['quantity'] for c in cart_items)
    items = Item.query.all()
    cart_open = request.args.get("open_cart") == "1"

    return render_template(
        "index.html",
        items=items,
        cart=cart_items,
        prices={i.name: i.price for i in items},
        total=total_price,
        cart_open=cart_open,
        orders=orders,
        user=user
    )


@app.route("/order")
def order():
    return render_template("order.html")


if __name__ == "__main__":
    app.run(debug=True)