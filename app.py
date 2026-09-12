
import os, json
from datetime import datetime, date, timedelta
from decimal import Decimal
from functools import wraps
from flask import Flask, render_template, request, redirect, url_for, session, flash, jsonify
from flask_sqlalchemy import SQLAlchemy
from werkzeug.security import generate_password_hash, check_password_hash
from sqlalchemy import or_, func, text, inspect

app = Flask(__name__)
app.secret_key = os.environ.get("SECRET_KEY", "CHANGE-ME-IN-RAILWAY")

db_url = os.environ.get("DATABASE_URL", "sqlite:///hardware_pos.db")
if db_url.startswith("postgres://"):
    db_url = db_url.replace("postgres://", "postgresql+psycopg://", 1)
elif db_url.startswith("postgresql://"):
    db_url = db_url.replace("postgresql://", "postgresql+psycopg://", 1)

app.config["SQLALCHEMY_DATABASE_URI"] = db_url
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False
db = SQLAlchemy(app)

def D(v): return Decimal(str(v or 0))
def M(v): return D(v).quantize(Decimal("0.01"))
def Q(v): return D(v).quantize(Decimal("0.001"))
def stamp(): return datetime.utcnow()

class User(db.Model):
    id=db.Column(db.Integer,primary_key=True); name=db.Column(db.String(120),nullable=False)
    username=db.Column(db.String(80),unique=True,nullable=False); password_hash=db.Column(db.String(255),nullable=False)
    role=db.Column(db.String(30),default="cashier"); active=db.Column(db.Boolean,default=True)

class Category(db.Model):
    id=db.Column(db.Integer,primary_key=True); name=db.Column(db.String(120),unique=True,nullable=False)
    active=db.Column(db.Boolean,default=True)

class Supplier(db.Model):
    id=db.Column(db.Integer,primary_key=True); name=db.Column(db.String(180),nullable=False)
    contact=db.Column(db.String(80)); address=db.Column(db.String(255)); balance=db.Column(db.Numeric(14,2),default=0)

class Customer(db.Model):
    id=db.Column(db.Integer,primary_key=True); name=db.Column(db.String(180),nullable=False)
    contact=db.Column(db.String(80)); address=db.Column(db.String(255))
    credit_limit=db.Column(db.Numeric(14,2),default=0); balance=db.Column(db.Numeric(14,2),default=0)

class Product(db.Model):
    id=db.Column(db.Integer,primary_key=True); sku=db.Column(db.String(80),unique=True,nullable=False)
    barcode=db.Column(db.String(100),unique=True); name=db.Column(db.String(220),nullable=False)
    brand=db.Column(db.String(120)); specification=db.Column(db.String(255)); unit=db.Column(db.String(40),default="piece")
    cost=db.Column(db.Numeric(14,2),default=0); price=db.Column(db.Numeric(14,2),default=0)
    wholesale_price=db.Column(db.Numeric(14,2),default=0); stock=db.Column(db.Numeric(14,3),default=0)
    minimum_stock=db.Column(db.Numeric(14,3),default=0); category_id=db.Column(db.Integer,db.ForeignKey("category.id"))
    supplier_id=db.Column(db.Integer,db.ForeignKey("supplier.id")); active=db.Column(db.Boolean,default=True)

class Sale(db.Model):
    id=db.Column(db.Integer,primary_key=True); invoice=db.Column(db.String(60),unique=True,nullable=False)
    cashier_id=db.Column(db.Integer,db.ForeignKey("user.id"),nullable=False); customer_id=db.Column(db.Integer,db.ForeignKey("customer.id"))
    subtotal=db.Column(db.Numeric(14,2),default=0); discount=db.Column(db.Numeric(14,2),default=0)
    total=db.Column(db.Numeric(14,2),default=0); payment=db.Column(db.Numeric(14,2),default=0)
    change=db.Column(db.Numeric(14,2),default=0); payment_type=db.Column(db.String(30),default="Cash")
    status=db.Column(db.String(30),default="Completed"); created_at=db.Column(db.DateTime,default=stamp)

class SaleItem(db.Model):
    id=db.Column(db.Integer,primary_key=True); sale_id=db.Column(db.Integer,db.ForeignKey("sale.id"),nullable=False)
    product_id=db.Column(db.Integer,db.ForeignKey("product.id"),nullable=False); qty=db.Column(db.Numeric(14,3),nullable=False)
    unit_price=db.Column(db.Numeric(14,2),nullable=False); cost=db.Column(db.Numeric(14,2),nullable=False); line_total=db.Column(db.Numeric(14,2),nullable=False)

class StockMovement(db.Model):
    id=db.Column(db.Integer,primary_key=True); product_id=db.Column(db.Integer,db.ForeignKey("product.id"),nullable=False)
    movement_type=db.Column(db.String(40),nullable=False); qty=db.Column(db.Numeric(14,3),nullable=False)
    reference=db.Column(db.String(100)); reason=db.Column(db.String(255)); user_id=db.Column(db.Integer,db.ForeignKey("user.id"))
    created_at=db.Column(db.DateTime,default=stamp)

class Purchase(db.Model):
    id=db.Column(db.Integer,primary_key=True); purchase_no=db.Column(db.String(60),unique=True,nullable=False)
    supplier_id=db.Column(db.Integer,db.ForeignKey("supplier.id"),nullable=False); total=db.Column(db.Numeric(14,2),default=0)
    paid=db.Column(db.Numeric(14,2),default=0); status=db.Column(db.String(30),default="Received"); created_at=db.Column(db.DateTime,default=stamp)

class PurchaseItem(db.Model):
    id=db.Column(db.Integer,primary_key=True); purchase_id=db.Column(db.Integer,db.ForeignKey("purchase.id"),nullable=False)
    product_id=db.Column(db.Integer,db.ForeignKey("product.id"),nullable=False); qty=db.Column(db.Numeric(14,3),nullable=False)
    unit_cost=db.Column(db.Numeric(14,2),nullable=False); line_total=db.Column(db.Numeric(14,2),nullable=False)

class CustomerPayment(db.Model):
    id=db.Column(db.Integer,primary_key=True); customer_id=db.Column(db.Integer,db.ForeignKey("customer.id"),nullable=False)
    amount=db.Column(db.Numeric(14,2),nullable=False); reference=db.Column(db.String(100))
    user_id=db.Column(db.Integer,db.ForeignKey("user.id")); created_at=db.Column(db.DateTime,default=stamp)

class SupplierPayment(db.Model):
    id=db.Column(db.Integer,primary_key=True); supplier_id=db.Column(db.Integer,db.ForeignKey("supplier.id"),nullable=False)
    amount=db.Column(db.Numeric(14,2),nullable=False); reference=db.Column(db.String(100))
    user_id=db.Column(db.Integer,db.ForeignKey("user.id")); created_at=db.Column(db.DateTime,default=stamp)

class Quotation(db.Model):
    id=db.Column(db.Integer,primary_key=True); quote_no=db.Column(db.String(60),unique=True,nullable=False)
    customer_id=db.Column(db.Integer,db.ForeignKey("customer.id")); total=db.Column(db.Numeric(14,2),default=0)
    discount=db.Column(db.Numeric(14,2),default=0); status=db.Column(db.String(30),default="Open")
    user_id=db.Column(db.Integer,db.ForeignKey("user.id")); created_at=db.Column(db.DateTime,default=stamp)

class QuotationItem(db.Model):
    id=db.Column(db.Integer,primary_key=True); quotation_id=db.Column(db.Integer,db.ForeignKey("quotation.id"),nullable=False)
    product_id=db.Column(db.Integer,db.ForeignKey("product.id"),nullable=False); qty=db.Column(db.Numeric(14,3),nullable=False)
    unit_price=db.Column(db.Numeric(14,2),nullable=False); line_total=db.Column(db.Numeric(14,2),nullable=False)

class Return(db.Model):
    id=db.Column(db.Integer,primary_key=True); return_no=db.Column(db.String(60),unique=True,nullable=False)
    sale_id=db.Column(db.Integer,db.ForeignKey("sale.id")); total=db.Column(db.Numeric(14,2),default=0)
    reason=db.Column(db.String(255)); user_id=db.Column(db.Integer,db.ForeignKey("user.id")); created_at=db.Column(db.DateTime,default=stamp)

class ReturnItem(db.Model):
    id=db.Column(db.Integer,primary_key=True); return_id=db.Column(db.Integer,db.ForeignKey("return.id"),nullable=False)
    product_id=db.Column(db.Integer,db.ForeignKey("product.id"),nullable=False); qty=db.Column(db.Numeric(14,3),nullable=False)
    amount=db.Column(db.Numeric(14,2),nullable=False)

class Shift(db.Model):
    id=db.Column(db.Integer,primary_key=True); user_id=db.Column(db.Integer,db.ForeignKey("user.id"),nullable=False)
    opening_cash=db.Column(db.Numeric(14,2),default=0); expected_cash=db.Column(db.Numeric(14,2))
    closing_cash=db.Column(db.Numeric(14,2)); difference=db.Column(db.Numeric(14,2))
    status=db.Column(db.String(20),default="Open"); opened_at=db.Column(db.DateTime,default=stamp); closed_at=db.Column(db.DateTime)

class AuditLog(db.Model):
    id=db.Column(db.Integer,primary_key=True); user_id=db.Column(db.Integer,db.ForeignKey("user.id"))
    action=db.Column(db.String(100),nullable=False); details=db.Column(db.String(600)); created_at=db.Column(db.DateTime,default=stamp)

def logged(fn):
    @wraps(fn)
    def w(*a,**kw):
        if not session.get("user_id"): return redirect(url_for("login"))
        return fn(*a,**kw)
    return w

def admin_only(fn):
    @wraps(fn)
    def w(*a,**kw):
        if session.get("role") not in ("admin", "manager"):
            flash("Administrator access required.")
            return redirect(url_for("pos"))
        return fn(*a,**kw)
    return w

# Backward-compatible alias for older deployments. New accounts only use admin/sales.
manager = admin_only

def role_label(role):
    return "Administrator" if role in ("admin", "manager") else "Sales Personnel"

def audit(action,details=""):
    db.session.add(AuditLog(user_id=session.get("user_id"),action=action,details=details))

@app.context_processor
def context():
    return {"current_user":session.get("name"),"role":session.get("role"),"role_label":role_label(session.get("role"))}

@app.route("/")
def index(): return redirect(url_for("pos") if session.get("user_id") else url_for("login"))

@app.route("/login",methods=["GET","POST"])
def login():
    if request.method=="POST":
        u=User.query.filter_by(username=request.form["username"].strip(),active=True).first()
        if u and check_password_hash(u.password_hash,request.form["password"]):
            session.update(user_id=u.id,name=u.name,role=u.role); audit("LOGIN"); db.session.commit()
            return redirect(url_for("pos"))
        flash("Invalid username or password.")
    return render_template("login.html")

@app.route("/logout")
def logout(): session.clear(); return redirect(url_for("login"))

@app.route("/account/password",methods=["GET","POST"])
@logged
def change_password():
    u=db.session.get(User,session["user_id"])
    if request.method=="POST":
        if not check_password_hash(u.password_hash,request.form.get("current_password","")):
            flash("Current password is incorrect.")
        elif len(request.form.get("new_password", "")) < 6:
            flash("New password must be at least 6 characters.")
        elif request.form.get("new_password") != request.form.get("confirm_password"):
            flash("New passwords do not match.")
        else:
            u.password_hash=generate_password_hash(request.form["new_password"])
            audit("PASSWORD_CHANGE",u.username); db.session.commit(); flash("Password changed successfully.")
            return redirect(url_for("pos"))
    return render_template("password.html")

@app.route("/pos")
@logged
def pos():
    return render_template("pos.html",customers=Customer.query.order_by(Customer.name).all(),
        shift=Shift.query.filter_by(user_id=session["user_id"],status="Open").first())

@app.route("/api/customers", methods=["GET", "POST"])
@logged
def customers_api():
    if request.method == "POST":
        try:
            name=request.form.get("name", "").strip()
            if not name:
                raise ValueError("Customer name is required.")
            contact=request.form.get("contact", "").strip() or None
            address=request.form.get("address", "").strip() or None
            c=Customer(name=name, contact=contact, address=address, credit_limit=M(request.form.get("credit_limit", 0)))
            db.session.add(c)
            db.session.flush()
            audit("CUSTOMER_CREATE", name)
            db.session.commit()
            return jsonify({"id": c.id, "name": c.name, "contact": c.contact or "", "address": c.address or "", "credit_limit": float(c.credit_limit or 0), "balance": float(c.balance or 0)}), 201
        except Exception as e:
            db.session.rollback()
            return jsonify({"error": str(e)}), 400

    q=request.args.get("q", "").strip()
    query=Customer.query
    if q:
        query=query.filter(or_(Customer.name.ilike(f"%{q}%"), Customer.contact.ilike(f"%{q}%")))
    rows=query.order_by(Customer.name).limit(50).all()
    if not q:
        recent=Sale.query.with_entities(Sale.customer_id, func.max(Sale.created_at).label("last_sale")).filter(Sale.customer_id.isnot(None)).group_by(Sale.customer_id).order_by(text("last_sale DESC")).limit(20).all()
        recent_ids=[r.customer_id for r in recent]
        rank={cid:i for i,cid in enumerate(recent_ids)}
        rows=sorted(rows, key=lambda c:(rank.get(c.id, 9999), c.name.lower()))
    return jsonify([{"id":c.id,"name":c.name,"contact":c.contact or "","address":c.address or "","credit_limit":float(c.credit_limit or 0),"balance":float(c.balance or 0)} for c in rows])

@app.route("/api/products")
@logged
def products_api():
    q=request.args.get("q","").strip()
    query=Product.query.filter_by(active=True)
    if q: query=query.filter(or_(Product.name.ilike(f"%{q}%"),Product.sku.ilike(f"%{q}%"),Product.barcode.ilike(f"%{q}%"),Product.brand.ilike(f"%{q}%")))
    return jsonify([{"id":p.id,"sku":p.sku,"barcode":p.barcode or "","name":p.name,"brand":p.brand or "",
      "specification":p.specification or "","unit":p.unit,"price":float(p.price or 0),
      "wholesale_price":float(p.wholesale_price or 0),"stock":float(p.stock or 0)} for p in query.limit(100).all()])

@app.route("/sale",methods=["POST"])
@logged
def sale():
    try:
        items=json.loads(request.form["items"]); discount=M(request.form.get("discount",0)); payment=M(request.form.get("payment",0))
        ptype=request.form.get("payment_type","Cash"); cid=request.form.get("customer_id") or None
        if not items: raise ValueError("Cart is empty.")
        subtotal=Decimal("0"); checked=[]
        for x in items:
            p=db.session.get(Product,int(x["id"])); q=Q(x["qty"])
            if not p or q<=0: raise ValueError("Invalid product.")
            if p.stock < q: raise ValueError(f"Insufficient stock: {p.name}. Available {p.stock} {p.unit}.")
            line=M(p.price*q); subtotal+=line; checked.append((p,q,line))
        total=max(Decimal("0"),M(subtotal-discount))
        if ptype=="Credit":
            if not cid: raise ValueError("Select a customer for credit.")
            c=db.session.get(Customer,int(cid))
            if c.credit_limit and M(c.balance)+total>M(c.credit_limit): raise ValueError("Customer credit limit exceeded.")
            payment=total
        elif payment<total: raise ValueError("Cash received is less than total.")
        change=M(max(Decimal("0"),payment-total))
        inv="INV-"+datetime.utcnow().strftime("%Y%m%d%H%M%S%f")
        s=Sale(invoice=inv,cashier_id=session["user_id"],customer_id=cid,subtotal=subtotal,discount=discount,total=total,payment=payment,change=change,payment_type=ptype)
        db.session.add(s); db.session.flush()
        for p,q,line in checked:
            p.stock-=q
            db.session.add(SaleItem(sale_id=s.id,product_id=p.id,qty=q,unit_price=p.price,cost=p.cost,line_total=line))
            db.session.add(StockMovement(product_id=p.id,movement_type="SALE",qty=-q,reference=inv,user_id=session["user_id"]))
        if cid and ptype=="Credit":
            c=db.session.get(Customer,int(cid)); c.balance=M(c.balance)+total
        audit("SALE",f"{inv} total={total}"); db.session.commit()
        return redirect(url_for("receipt",sale_id=s.id,autoprint=1))
    except Exception as e:
        db.session.rollback(); flash(str(e)); return redirect(url_for("pos"))

@app.route("/receipt/<int:sale_id>")
@logged
def receipt(sale_id):
    s=db.session.get(Sale,sale_id)
    if not s:
        flash("Receipt not found.")
        return redirect(url_for("reports"))

    raw_items=SaleItem.query.filter_by(sale_id=s.id).all()
    receipt_items=[]
    for item in raw_items:
        product=db.session.get(Product,item.product_id)
        receipt_items.append({
            "qty": item.qty,
            "name": product.name if product else f"Product #{item.product_id}",
            "unit": product.unit if product else "unit",
            "price": item.unit_price,
            "line_total": item.line_total,
        })

    cashier=db.session.get(User,s.cashier_id)
    customer=db.session.get(Customer,s.customer_id) if s.customer_id else None
    autoprint=request.args.get("autoprint") == "1"

    return render_template(
        "receipt.html",
        sale=s,
        items=receipt_items,
        cashier=cashier,
        customer=customer,
        store_name="HURE",
        store_description="Hardware and Construction Supply",
        store_address="Kangha-as, Hilongos, Leyte",
        paper_width="3.9in",
        paper_height="8in",
        autoprint=autoprint,
    )

@app.route("/admin")
@manager
def admin():
    start=datetime.combine(date.today(),datetime.min.time())
    sales=Sale.query.filter(Sale.created_at>=start,Sale.status=="Completed").all()
    products=Product.query.order_by(Product.name).all()
    profit=sum((M(i.line_total)-M(i.cost*i.qty) for s in sales for i in SaleItem.query.filter_by(sale_id=s.id)),Decimal("0"))
    return render_template("admin.html",sales=sales,products=products,profit=profit,
      today_total=sum((M(s.total) for s in sales),Decimal("0")),
      low_stock=[p for p in products if Q(p.stock)<=Q(p.minimum_stock)],
      categories=Category.query.order_by(Category.name).all(),suppliers=Supplier.query.order_by(Supplier.name).all(),
      customers=Customer.query.order_by(Customer.name).all(),users=User.query.order_by(User.name).all(),
      audits=AuditLog.query.order_by(AuditLog.created_at.desc()).limit(50).all())

@app.route("/admin/product",methods=["POST"])
@manager
def create_product():
    try:
        p=Product(sku=request.form["sku"].strip(),barcode=request.form.get("barcode") or None,name=request.form["name"].strip(),
          brand=request.form.get("brand"),specification=request.form.get("specification"),unit=request.form.get("unit","piece"),
          cost=M(request.form.get("cost",0)),price=M(request.form.get("price",0)),wholesale_price=M(request.form.get("wholesale_price",0)),
          stock=Q(request.form.get("stock",0)),minimum_stock=Q(request.form.get("minimum_stock",0)),
          category_id=request.form.get("category_id") or None,supplier_id=request.form.get("supplier_id") or None)
        db.session.add(p); audit("PRODUCT_CREATE",p.sku); db.session.commit(); flash("Product saved.")
    except Exception as e: db.session.rollback(); flash(f"Product error: {e}")
    return redirect(url_for("admin"))

@app.route("/admin/product/<int:product_id>/edit",methods=["GET","POST"])
@manager
def edit_product(product_id):
    p=db.session.get(Product,product_id)
    if not p:
        flash("Product not found."); return redirect(url_for("admin"))
    if request.method=="POST":
        try:
            p.sku=request.form["sku"].strip(); p.barcode=request.form.get("barcode") or None; p.name=request.form["name"].strip()
            p.brand=request.form.get("brand"); p.specification=request.form.get("specification"); p.unit=request.form.get("unit","piece")
            p.cost=M(request.form.get("cost",0)); p.price=M(request.form.get("price",0)); p.wholesale_price=M(request.form.get("wholesale_price",0))
            p.minimum_stock=Q(request.form.get("minimum_stock",0)); p.category_id=request.form.get("category_id") or None; p.supplier_id=request.form.get("supplier_id") or None
            p.active=bool(request.form.get("active"))
            audit("PRODUCT_UPDATE",p.sku); db.session.commit(); flash("Product updated."); return redirect(url_for("admin"))
        except Exception as e:
            db.session.rollback(); flash(f"Product update error: {e}")
    return render_template("product_edit.html",product=p,categories=Category.query.order_by(Category.name).all(),suppliers=Supplier.query.order_by(Supplier.name).all())

@app.route("/admin/product/<int:product_id>/toggle",methods=["POST"])
@manager
def toggle_product(product_id):
    p=db.session.get(Product,product_id)
    if not p: flash("Product not found.")
    else:
        p.active=not p.active; audit("PRODUCT_STATUS",f"{p.sku}: {'active' if p.active else 'inactive'}"); db.session.commit(); flash("Product status updated.")
    return redirect(url_for("admin"))

@app.route("/admin/product/<int:product_id>/delete",methods=["POST"])
@admin_only
def delete_product(product_id):
    p=db.session.get(Product,product_id)
    if not p:
        flash("Product not found.")
        return redirect(url_for("admin"))
    try:
        # Do not destroy products that are already referenced by business records.
        used = (
            SaleItem.query.filter_by(product_id=p.id).first() or
            PurchaseItem.query.filter_by(product_id=p.id).first() or
            QuotationItem.query.filter_by(product_id=p.id).first() or
            ReturnItem.query.filter_by(product_id=p.id).first() or
            StockMovement.query.filter_by(product_id=p.id).first()
        )
        if used:
            p.active=False
            audit("PRODUCT_DEACTIVATE",f"{p.sku}: historical records exist")
            db.session.commit()
            flash("Product has transaction history, so it was deactivated instead of permanently deleted.")
        else:
            sku=p.sku
            db.session.delete(p)
            audit("PRODUCT_DELETE",sku)
            db.session.commit()
            flash("Product permanently deleted.")
    except Exception as e:
        db.session.rollback()
        flash(f"Product delete error: {e}")
    return redirect(url_for("admin"))

@app.route("/admin/stock",methods=["POST"])
@manager
def adjust_stock():
    try:
        p=db.session.get(Product,int(request.form["product_id"])); delta=Q(request.form["qty"])
        if not p: raise ValueError("Product not found.")
        if Q(p.stock)+delta<0: raise ValueError("Stock cannot be negative.")
        p.stock=Q(p.stock)+delta
        db.session.add(StockMovement(product_id=p.id,movement_type="ADJUSTMENT",qty=delta,reason=request.form.get("reason"),user_id=session["user_id"]))
        audit("STOCK_ADJUST",f"{p.sku}: {delta}"); db.session.commit(); flash("Stock adjusted.")
    except Exception as e: db.session.rollback(); flash(str(e))
    return redirect(url_for("admin"))

@app.route("/admin/category",methods=["POST"])
@manager
def create_category():
    db.session.add(Category(name=request.form["name"].strip())); audit("CATEGORY_CREATE",request.form["name"]); db.session.commit(); return redirect(url_for("admin"))

@app.route("/admin/supplier",methods=["POST"])
@manager
def create_supplier():
    db.session.add(Supplier(name=request.form["name"],contact=request.form.get("contact"),address=request.form.get("address")))
    audit("SUPPLIER_CREATE",request.form["name"]); db.session.commit(); return redirect(url_for("admin"))

@app.route("/admin/customer",methods=["POST"])
@manager
def create_customer():
    db.session.add(Customer(name=request.form["name"],contact=request.form.get("contact"),address=request.form.get("address"),credit_limit=M(request.form.get("credit_limit",0))))
    audit("CUSTOMER_CREATE",request.form["name"]); db.session.commit(); return redirect(url_for("admin"))

@app.route("/admin/customer-payment",methods=["POST"])
@manager
def customer_payment():
    try:
        c=db.session.get(Customer,int(request.form["customer_id"])); amount=M(request.form["amount"])
        if not c or amount<=0: raise ValueError("Invalid payment.")
        c.balance=max(Decimal("0"),M(c.balance)-amount)
        db.session.add(CustomerPayment(customer_id=c.id,amount=amount,reference=request.form.get("reference"),user_id=session["user_id"]))
        audit("CUSTOMER_PAYMENT",f"{c.name}: {amount}"); db.session.commit(); flash("Customer payment recorded.")
    except Exception as e: db.session.rollback(); flash(str(e))
    return redirect(url_for("admin"))

@app.route("/admin/supplier-payment",methods=["POST"])
@manager
def supplier_payment():
    try:
        s=db.session.get(Supplier,int(request.form["supplier_id"])); amount=M(request.form["amount"])
        if not s or amount<=0: raise ValueError("Invalid payment.")
        s.balance=max(Decimal("0"),M(s.balance)-amount)
        db.session.add(SupplierPayment(supplier_id=s.id,amount=amount,reference=request.form.get("reference"),user_id=session["user_id"]))
        audit("SUPPLIER_PAYMENT",f"{s.name}: {amount}"); db.session.commit(); flash("Supplier payment recorded.")
    except Exception as e: db.session.rollback(); flash(str(e))
    return redirect(url_for("admin"))

@app.route("/admin/user",methods=["POST"])
@admin_only
def create_user():
    try:
        u=User(name=request.form["name"],username=request.form["username"].strip(),password_hash=generate_password_hash(request.form["password"]),role=request.form.get("role","sales"))
        db.session.add(u); audit("USER_CREATE",u.username); db.session.commit(); flash("User created.")
    except Exception as e: db.session.rollback(); flash(f"User error: {e}")
    return redirect(url_for("admin"))

@app.route("/admin/purchase",methods=["POST"])
@manager
def purchase():
    try:
        data=json.loads(request.form["items"]); sid=int(request.form["supplier_id"]); paid=M(request.form.get("paid",0))
        if not data: raise ValueError("Purchase is empty.")
        total=Decimal("0"); checked=[]
        for x in data:
            p=db.session.get(Product,int(x["id"])); q=Q(x["qty"]); cost=M(x["cost"])
            if not p or q<=0: raise ValueError("Invalid purchase item.")
            line=M(q*cost); total+=line; checked.append((p,q,cost,line))
        no="PUR-"+datetime.utcnow().strftime("%Y%m%d%H%M%S%f")
        pur=Purchase(purchase_no=no,supplier_id=sid,total=total,paid=min(paid,total)); db.session.add(pur); db.session.flush()
        for p,q,cost,line in checked:
            p.stock=Q(p.stock)+q; p.cost=cost
            db.session.add(PurchaseItem(purchase_id=pur.id,product_id=p.id,qty=q,unit_cost=cost,line_total=line))
            db.session.add(StockMovement(product_id=p.id,movement_type="PURCHASE",qty=q,reference=no,user_id=session["user_id"]))
        sup=db.session.get(Supplier,sid); sup.balance=M(sup.balance)+total-min(paid,total)
        audit("PURCHASE",f"{no}: {total}"); db.session.commit(); flash(f"Purchase {no} received.")
    except Exception as e: db.session.rollback(); flash(str(e))
    return redirect(url_for("admin"))

@app.route("/admin/shift/open",methods=["POST"])
@logged
def open_shift():
    if Shift.query.filter_by(user_id=session["user_id"],status="Open").first(): flash("You already have an open shift.")
    else:
        db.session.add(Shift(user_id=session["user_id"],opening_cash=M(request.form.get("opening_cash",0)))); audit("SHIFT_OPEN"); db.session.commit(); flash("Shift opened.")
    return redirect(url_for("pos"))

@app.route("/admin/shift/close",methods=["POST"])
@logged
def close_shift():
    s=Shift.query.filter_by(user_id=session["user_id"],status="Open").first()
    if not s: flash("No open shift."); return redirect(url_for("pos"))
    sales=Sale.query.filter(Sale.cashier_id==s.user_id,Sale.created_at>=s.opened_at,Sale.status=="Completed",Sale.payment_type=="Cash").all()
    expected=M(s.opening_cash)+sum((M(x.payment) for x in sales),Decimal("0"))
    actual=M(request.form["closing_cash"]); s.expected_cash=expected; s.closing_cash=actual; s.difference=actual-expected; s.status="Closed"; s.closed_at=stamp()
    audit("SHIFT_CLOSE",f"expected={expected},actual={actual},difference={actual-expected}"); db.session.commit(); flash(f"Shift closed. Difference ₱{actual-expected:.2f}")
    return redirect(url_for("pos"))

@app.route("/reports")
@manager
def reports():
    sales=Sale.query.filter_by(status="Completed").order_by(Sale.created_at.desc()).limit(1000).all()
    rows=[]
    for s in sales:
        its=SaleItem.query.filter_by(sale_id=s.id).all()
        rows.append((s,sum((M(i.line_total)-M(i.cost*i.qty) for i in its),Decimal("0"))))
    return render_template("reports.html",rows=rows)

@app.route("/admin/sale/<int:sale_id>/delete", methods=["POST"])
@admin_only
def delete_sale(sale_id):
    try:
        s=db.session.get(Sale,sale_id)
        if not s:
            flash("Sale not found.")
            return redirect(url_for("reports"))

        items=SaleItem.query.filter_by(sale_id=s.id).all()
        # Restore stock because deleting the transaction removes its inventory effect.
        for i in items:
            p=db.session.get(Product,i.product_id)
            if p:
                p.stock=Q(p.stock)+Q(i.qty)
            db.session.delete(i)

        # Remove the SALE stock-movement entries for this invoice.
        StockMovement.query.filter_by(reference=s.invoice, movement_type="SALE").delete(synchronize_session=False)

        # Reverse customer balance for a credit sale.
        if s.customer_id and s.payment_type=="Credit":
            c=db.session.get(Customer,s.customer_id)
            if c:
                c.balance=max(Decimal("0"),M(c.balance)-M(s.total))

        inv=s.invoice
        total=M(s.total)
        db.session.delete(s)
        audit("SALE_DELETE",f"{inv} total={total} (admin)")
        db.session.commit()
        flash(f"Sale {inv} deleted and stock restored.")
    except Exception as e:
        db.session.rollback()
        flash(f"Sale delete error: {e}")
    return redirect(url_for("reports"))

@app.route("/reports/inventory")
@manager
def inventory_report():
    products=Product.query.order_by(Product.name).all()
    value=sum((M(p.stock*p.cost) for p in products),Decimal("0"))
    return render_template("inventory.html",products=products,value=value)

@app.route("/quotation",methods=["GET","POST"])
@logged
def quotation():
    if request.method=="POST":
        try:
            items=json.loads(request.form["items"]); cid=request.form.get("customer_id") or None; discount=M(request.form.get("discount",0))
            if not items: raise ValueError("Quotation is empty.")
            total=Decimal("0"); checked=[]
            for x in items:
                p=db.session.get(Product,int(x["id"])); q=Q(x["qty"])
                if not p or q<=0: raise ValueError("Invalid quotation item.")
                line=M(p.price*q); total+=line; checked.append((p,q,line))
            total=max(Decimal("0"),M(total-discount)); no="Q-"+datetime.utcnow().strftime("%Y%m%d%H%M%S%f")
            q=Quotation(quote_no=no,customer_id=cid,total=total,discount=discount,user_id=session["user_id"]); db.session.add(q); db.session.flush()
            for p,n,line in checked: db.session.add(QuotationItem(quotation_id=q.id,product_id=p.id,qty=n,unit_price=p.price,line_total=line))
            audit("QUOTATION",f"{no}: {total}"); db.session.commit(); return redirect(url_for("quotation_receipt",qid=q.id))
        except Exception as e: db.session.rollback(); flash(str(e))
    return render_template("quotation.html",customers=Customer.query.order_by(Customer.name).all())

@app.route("/quotation/<int:qid>")
@logged
def quotation_receipt(qid):
    q=db.session.get(Quotation,qid); items=QuotationItem.query.filter_by(quotation_id=q.id).all()
    return render_template("quotation_receipt.html",quote=q,items=items)

def ensure_schema_compatibility():
    """Add columns missing from older Railway databases without deleting data."""
    additions = {
        "user": {"active": "BOOLEAN DEFAULT TRUE"},
        "supplier": {"balance": "NUMERIC(14,2) DEFAULT 0"},
        "customer": {"credit_limit": "NUMERIC(14,2) DEFAULT 0", "balance": "NUMERIC(14,2) DEFAULT 0"},
        "product": {
            "barcode": "VARCHAR(100)", "brand": "VARCHAR(120)", "specification": "VARCHAR(255)",
            "unit": "VARCHAR(40) DEFAULT 'piece'", "cost": "NUMERIC(14,2) DEFAULT 0",
            "price": "NUMERIC(14,2) DEFAULT 0", "wholesale_price": "NUMERIC(14,2) DEFAULT 0",
            "stock": "NUMERIC(14,3) DEFAULT 0", "minimum_stock": "NUMERIC(14,3) DEFAULT 0",
            "active": "BOOLEAN DEFAULT TRUE"
        },
        "shift": {
            "expected_cash": "NUMERIC(14,2)", "closing_cash": "NUMERIC(14,2)",
            "difference": "NUMERIC(14,2)", "closed_at": "TIMESTAMP"
        },
        "audit_log": {"details": "VARCHAR(600)"},
    }
    # Inspect each table and add only columns that are actually missing.
    for table, cols in additions.items():
        inspector=inspect(db.engine)
        if not inspector.has_table(table):
            continue
        existing={c["name"] for c in inspector.get_columns(table)}
        for col, typ in cols.items():
            if col not in existing:
                try:
                    db.session.execute(text(f'ALTER TABLE "{table}" ADD COLUMN "{col}" {typ}'))
                    db.session.commit()
                except Exception:
                    db.session.rollback()
                    # Re-check: another worker may have added the column while starting.
                    inspector=inspect(db.engine)
                    existing={c["name"] for c in inspector.get_columns(table)} if inspector.has_table(table) else set()
                    if col not in existing:
                        raise

with app.app_context():
    db.create_all()
    ensure_schema_compatibility()
    if not User.query.filter_by(username="admin").first():
        db.session.add(User(name="Administrator",username="admin",password_hash=generate_password_hash("admin123"),role="admin"))
        db.session.commit()

if __name__=="__main__":
    app.run(host="0.0.0.0",port=int(os.environ.get("PORT","8080")))
