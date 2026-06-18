import os
import csv
import io
import json
from datetime import datetime, date, timedelta
from functools import wraps
from decimal import Decimal, ROUND_HALF_UP

import jwt
from flask import Flask, jsonify, request, send_file, send_from_directory
from flask_cors import CORS
from flask_sqlalchemy import SQLAlchemy
from werkzeug.security import generate_password_hash, check_password_hash
from werkzeug.utils import secure_filename
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4, landscape
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer
from openpyxl import Workbook

BASE_DIR = os.path.abspath(os.path.dirname(__file__))
DATA_DIR = os.path.join(BASE_DIR, "data")
UPLOAD_DIR = os.path.join(BASE_DIR, "uploads")
DIST_DIR = os.path.join(BASE_DIR, "dist")
os.makedirs(DATA_DIR, exist_ok=True)
os.makedirs(UPLOAD_DIR, exist_ok=True)

app = Flask(__name__, static_folder=DIST_DIR, static_url_path="")
app.config["SQLALCHEMY_DATABASE_URI"] = "sqlite:///" + os.path.join(DATA_DIR, "jatayu_re6.db")
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False
app.config["SECRET_KEY"] = os.environ.get("JATAYU_SECRET", "offline-jatayu-re6-secret")
CORS(app)
db = SQLAlchemy(app)

ROLE_PERMISSIONS = {
    "Admin": {"*"},
    "Accountant": {"invoices", "re6", "payments", "reports", "ledger", "parties", "products", "vehicles", "dashboard"},
    "Viewer": {"dashboard", "invoices:read", "re6:read", "payments:read", "reports", "ledger", "parties:read", "products:read", "vehicles:read", "settings:read"},
}


class Serializer:
    def to_dict(self):
        result = {}
        for column in self.__table__.columns:
            value = getattr(self, column.name)
            if isinstance(value, (date, datetime)):
                value = value.isoformat()
            result[column.name] = value
        return result


class User(db.Model, Serializer):
    __tablename__ = "users"
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    password_hash = db.Column(db.String(255), nullable=False)
    role = db.Column(db.String(30), default="Viewer")
    active = db.Column(db.Boolean, default=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)


class CompanySettings(db.Model, Serializer):
    __tablename__ = "company_settings"
    id = db.Column(db.Integer, primary_key=True)
    company_name = db.Column(db.String(180), default="Jatayu Explosives")
    gstin = db.Column(db.String(30), default="")
    pan = db.Column(db.String(20), default="")
    address = db.Column(db.Text, default="")
    city = db.Column(db.String(80), default="")
    state = db.Column(db.String(80), default="Karnataka")
    pincode = db.Column(db.String(12), default="")
    phone = db.Column(db.String(30), default="")
    mobile = db.Column(db.String(30), default="")
    email = db.Column(db.String(120), default="")
    website = db.Column(db.String(120), default="")
    logo_path = db.Column(db.String(255), default="")
    signature_path = db.Column(db.String(255), default="")
    bank_name = db.Column(db.String(120), default="")
    account_number = db.Column(db.String(60), default="")
    ifsc = db.Column(db.String(30), default="")
    branch = db.Column(db.String(120), default="")
    invoice_prefix = db.Column(db.String(20), default="INV")
    re6_prefix = db.Column(db.String(20), default="RE6")
    default_loading_point = db.Column(db.String(180), default="")


class Party(db.Model, Serializer):
    __tablename__ = "parties"
    id = db.Column(db.Integer, primary_key=True)
    party_name = db.Column(db.String(180), nullable=False)
    gstin = db.Column(db.String(30), default="")
    address = db.Column(db.Text, default="")
    contact_person = db.Column(db.String(120), default="")
    mobile = db.Column(db.String(30), default="")
    email = db.Column(db.String(120), default="")
    license_number = db.Column(db.String(80), default="")
    opening_balance = db.Column(db.Float, default=0)
    credit_limit = db.Column(db.Float, default=0)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)


class Product(db.Model, Serializer):
    __tablename__ = "products"
    id = db.Column(db.Integer, primary_key=True)
    product_name = db.Column(db.String(160), nullable=False)
    hsn_code = db.Column(db.String(30), default="")
    unit = db.Column(db.String(30), default="Nos")
    gst_rate = db.Column(db.Float, default=18)
    default_rate = db.Column(db.Float, default=0)


class Vehicle(db.Model, Serializer):
    __tablename__ = "vehicles"
    id = db.Column(db.Integer, primary_key=True)
    vehicle_number = db.Column(db.String(40), unique=True, nullable=False)
    driver_name = db.Column(db.String(120), default="")
    driver_license_number = db.Column(db.String(80), default="")
    le7_license_number = db.Column(db.String(80), default="")
    insurance_expiry = db.Column(db.Date, nullable=True)
    fitness_expiry = db.Column(db.Date, nullable=True)
    puc_expiry = db.Column(db.Date, nullable=True)


class Invoice(db.Model, Serializer):
    __tablename__ = "invoices"
    id = db.Column(db.Integer, primary_key=True)
    invoice_number = db.Column(db.String(40), unique=True, nullable=False)
    invoice_date = db.Column(db.Date, default=date.today)
    party_id = db.Column(db.Integer, db.ForeignKey("parties.id"), nullable=False)
    previous_due = db.Column(db.Float, default=0)
    discount = db.Column(db.Float, default=0)
    freight = db.Column(db.Float, default=0)
    round_off = db.Column(db.Float, default=0)
    subtotal = db.Column(db.Float, default=0)
    cgst = db.Column(db.Float, default=0)
    sgst = db.Column(db.Float, default=0)
    igst = db.Column(db.Float, default=0)
    grand_total = db.Column(db.Float, default=0)
    paid_amount = db.Column(db.Float, default=0)
    status = db.Column(db.String(20), default="Unpaid")
    notes = db.Column(db.Text, default="")
    party = db.relationship("Party")
    items = db.relationship("InvoiceItem", cascade="all, delete-orphan", backref="invoice")


class InvoiceItem(db.Model, Serializer):
    __tablename__ = "invoice_items"
    id = db.Column(db.Integer, primary_key=True)
    invoice_id = db.Column(db.Integer, db.ForeignKey("invoices.id"), nullable=False)
    product_id = db.Column(db.Integer, db.ForeignKey("products.id"), nullable=True)
    description = db.Column(db.String(180), nullable=False)
    hsn_code = db.Column(db.String(30), default="")
    quantity = db.Column(db.Float, default=0)
    unit = db.Column(db.String(30), default="")
    rate = db.Column(db.Float, default=0)
    taxable_value = db.Column(db.Float, default=0)
    gst_rate = db.Column(db.Float, default=0)
    cgst = db.Column(db.Float, default=0)
    sgst = db.Column(db.Float, default=0)
    igst = db.Column(db.Float, default=0)
    total = db.Column(db.Float, default=0)
    batch_number = db.Column(db.String(80), default="")
    manufacture_date = db.Column(db.Date, nullable=True)
    explosive_class = db.Column(db.String(40), default="")
    division = db.Column(db.String(40), default="")
    number_of_cases = db.Column(db.Integer, default=0)


class Payment(db.Model, Serializer):
    __tablename__ = "payments"
    id = db.Column(db.Integer, primary_key=True)
    payment_date = db.Column(db.Date, default=date.today)
    party_id = db.Column(db.Integer, db.ForeignKey("parties.id"), nullable=False)
    amount = db.Column(db.Float, nullable=False)
    payment_mode = db.Column(db.String(40), default="Cash")
    reference_number = db.Column(db.String(80), default="")
    notes = db.Column(db.Text, default="")
    party = db.relationship("Party")


class PartyLedger(db.Model, Serializer):
    __tablename__ = "party_ledger"
    id = db.Column(db.Integer, primary_key=True)
    entry_date = db.Column(db.Date, default=date.today)
    party_id = db.Column(db.Integer, db.ForeignKey("parties.id"), nullable=False)
    entry_type = db.Column(db.String(40), nullable=False)
    reference = db.Column(db.String(80), default="")
    debit = db.Column(db.Float, default=0)
    credit = db.Column(db.Float, default=0)
    balance = db.Column(db.Float, default=0)
    notes = db.Column(db.Text, default="")
    party = db.relationship("Party")


class RE6Record(db.Model, Serializer):
    __tablename__ = "re6_records"
    id = db.Column(db.Integer, primary_key=True)
    re6_number = db.Column(db.String(40), unique=True, nullable=False)
    re6_date = db.Column(db.Date, default=date.today)
    invoice_id = db.Column(db.Integer, db.ForeignKey("invoices.id"), nullable=True)
    consignor = db.Column(db.String(180), default="")
    consignee = db.Column(db.String(180), default="")
    vehicle_id = db.Column(db.Integer, db.ForeignKey("vehicles.id"), nullable=True)
    vehicle_number = db.Column(db.String(40), default="")
    driver_details = db.Column(db.String(180), default="")
    le7_number = db.Column(db.String(80), default="")
    product_details = db.Column(db.Text, default="")
    quantity = db.Column(db.String(80), default="")
    number_of_cases = db.Column(db.Integer, default=0)
    loading_point = db.Column(db.String(180), default="")
    destination = db.Column(db.String(180), default="")
    invoice = db.relationship("Invoice")
    vehicle = db.relationship("Vehicle")


class Setting(db.Model, Serializer):
    __tablename__ = "settings"
    id = db.Column(db.Integer, primary_key=True)
    key = db.Column(db.String(80), unique=True, nullable=False)
    value = db.Column(db.Text, default="")


class AuditLog(db.Model, Serializer):
    __tablename__ = "audit_logs"
    id = db.Column(db.Integer, primary_key=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    user_id = db.Column(db.Integer, nullable=True)
    action = db.Column(db.String(120), nullable=False)
    entity = db.Column(db.String(80), default="")
    entity_id = db.Column(db.Integer, nullable=True)
    details = db.Column(db.Text, default="")


def parse_date(value):
    if not value:
        return None
    if isinstance(value, date):
        return value
    return datetime.strptime(value[:10], "%Y-%m-%d").date()


def money(value):
    return float(Decimal(str(value or 0)).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP))


def current_settings():
    settings = CompanySettings.query.first()
    if not settings:
        settings = CompanySettings()
        db.session.add(settings)
        db.session.commit()
    return settings


def next_number(prefix, model, field):
    year = date.today().year
    pattern = f"{prefix}/{year}/"
    last = model.query.filter(getattr(model, field).like(pattern + "%")).order_by(model.id.desc()).first()
    next_id = 1
    if last:
        try:
            next_id = int(getattr(last, field).split("/")[-1]) + 1
        except ValueError:
            next_id = last.id + 1
    return f"{pattern}{next_id:04d}"


def audit(action, entity="", entity_id=None, details=""):
    user = getattr(request, "user", None)
    db.session.add(AuditLog(user_id=user.id if user else None, action=action, entity=entity, entity_id=entity_id, details=details[:1000]))


def token_for(user):
    payload = {"id": user.id, "username": user.username, "role": user.role, "exp": datetime.utcnow() + timedelta(hours=12)}
    return jwt.encode(payload, app.config["SECRET_KEY"], algorithm="HS256")


def require_auth(module=None, write=False):
    def decorator(fn):
        @wraps(fn)
        def wrapper(*args, **kwargs):
            header = request.headers.get("Authorization", "")
            if not header.startswith("Bearer "):
                return jsonify({"error": "Authentication required"}), 401
            try:
                payload = jwt.decode(header.split(" ", 1)[1], app.config["SECRET_KEY"], algorithms=["HS256"])
            except jwt.PyJWTError:
                return jsonify({"error": "Invalid or expired token"}), 401
            user = User.query.get(payload["id"])
            if not user or not user.active:
                return jsonify({"error": "User disabled"}), 403
            request.user = user
            perms = ROLE_PERMISSIONS.get(user.role, set())
            effective_write = write and request.method not in {"GET", "HEAD", "OPTIONS"}
            if module and "*" not in perms:
                allowed = module in perms or (not effective_write and f"{module}:read" in perms)
                if not allowed:
                    return jsonify({"error": "Permission denied"}), 403
            return fn(*args, **kwargs)
        return wrapper
    return decorator


def upsert_model(model, payload, obj=None, date_fields=None, skip=None):
    obj = obj or model()
    date_fields = set(date_fields or [])
    skip = set(skip or [])
    for column in model.__table__.columns:
        name = column.name
        if name in {"id", "created_at"} or name in skip or name not in payload:
            continue
        value = parse_date(payload.get(name)) if name in date_fields else payload.get(name)
        setattr(obj, name, value)
    return obj


def ledger_balance(party_id):
    party = Party.query.get(party_id)
    total = party.opening_balance if party else 0
    entries = PartyLedger.query.filter_by(party_id=party_id).order_by(PartyLedger.entry_date, PartyLedger.id).all()
    for entry in entries:
        total += (entry.debit or 0) - (entry.credit or 0)
        entry.balance = money(total)
    return money(total)


def rebuild_party_ledger(party_id):
    PartyLedger.query.filter_by(party_id=party_id).delete()
    party = Party.query.get(party_id)
    if not party:
        return
    balance = party.opening_balance or 0
    for invoice in Invoice.query.filter_by(party_id=party_id).order_by(Invoice.invoice_date, Invoice.id):
        balance += invoice.grand_total
        db.session.add(PartyLedger(entry_date=invoice.invoice_date, party_id=party_id, entry_type="Invoice", reference=invoice.invoice_number, debit=invoice.grand_total, credit=0, balance=money(balance), notes=invoice.notes))
    for payment in Payment.query.filter_by(party_id=party_id).order_by(Payment.payment_date, Payment.id):
        balance -= payment.amount
        db.session.add(PartyLedger(entry_date=payment.payment_date, party_id=party_id, entry_type="Payment", reference=payment.reference_number, debit=0, credit=payment.amount, balance=money(balance), notes=payment.notes))


def invoice_to_dict(invoice):
    data = invoice.to_dict()
    data["party"] = invoice.party.to_dict() if invoice.party else None
    data["items"] = [item.to_dict() for item in invoice.items]
    data["outstanding"] = money(invoice.grand_total - invoice.paid_amount)
    return data


def re6_to_dict(record):
    data = record.to_dict()
    data["invoice"] = invoice_to_dict(record.invoice) if record.invoice else None
    data["vehicle"] = record.vehicle.to_dict() if record.vehicle else None
    return data


def compute_invoice(payload):
    party = Party.query.get(payload.get("party_id"))
    company = current_settings()
    same_state = bool(party and party.gstin and company.gstin and party.gstin[:2] == company.gstin[:2])
    items = []
    subtotal = cgst = sgst = igst = 0
    for raw in payload.get("items", []):
        qty = float(raw.get("quantity") or 0)
        rate = float(raw.get("rate") or 0)
        gst_rate = float(raw.get("gst_rate") or 0)
        taxable = money(qty * rate)
        tax = money(taxable * gst_rate / 100)
        item_cgst = money(tax / 2) if same_state else 0
        item_sgst = money(tax / 2) if same_state else 0
        item_igst = 0 if same_state else tax
        total = money(taxable + item_cgst + item_sgst + item_igst)
        subtotal += taxable
        cgst += item_cgst
        sgst += item_sgst
        igst += item_igst
        raw.update({"taxable_value": taxable, "cgst": item_cgst, "sgst": item_sgst, "igst": item_igst, "total": total})
        items.append(raw)
    discount = float(payload.get("discount") or 0)
    freight = float(payload.get("freight") or 0)
    round_off = float(payload.get("round_off") or 0)
    grand = money(subtotal + cgst + sgst + igst - discount + freight + round_off)
    return {"items": items, "subtotal": money(subtotal), "cgst": money(cgst), "sgst": money(sgst), "igst": money(igst), "grand_total": grand}


@app.post("/api/auth/login")
def login():
    payload = request.get_json(force=True)
    user = User.query.filter_by(username=payload.get("username", "")).first()
    if not user or not check_password_hash(user.password_hash, payload.get("password", "")):
        return jsonify({"error": "Invalid username or password"}), 401
    return jsonify({"token": token_for(user), "user": user.to_dict()})


@app.get("/api/auth/me")
@require_auth()
def me():
    return jsonify(request.user.to_dict())


@app.get("/api/dashboard")
@require_auth("dashboard")
def dashboard():
    today = date.today()
    soon = today + timedelta(days=30)
    invoices = Invoice.query.all()
    revenue = sum(i.grand_total for i in invoices)
    outstanding = sum(max(i.grand_total - i.paid_amount, 0) for i in invoices)
    monthly = {}
    for inv in invoices:
        key = inv.invoice_date.strftime("%Y-%m")
        monthly[key] = monthly.get(key, 0) + inv.grand_total
    return jsonify({
        "total_revenue": money(revenue),
        "total_invoices": len(invoices),
        "outstanding_payments": money(outstanding),
        "total_re6_forms": RE6Record.query.count(),
        "total_vehicles": Vehicle.query.count(),
        "expiring_vehicle_licenses": Vehicle.query.filter(Vehicle.fitness_expiry.between(today, soon)).count(),
        "expiring_insurance": Vehicle.query.filter(Vehicle.insurance_expiry.between(today, soon)).count(),
        "monthly_sales": [{"month": k, "total": money(v)} for k, v in sorted(monthly.items())[-12:]],
        "recent_invoices": [invoice_to_dict(i) for i in Invoice.query.order_by(Invoice.id.desc()).limit(5)],
    })


@app.route("/api/settings/company", methods=["GET", "PUT"])
@require_auth("settings", write=True)
def company_settings():
    settings = current_settings()
    if request.method == "GET":
        return jsonify(settings.to_dict())
    payload = request.get_json(force=True)
    upsert_model(CompanySettings, payload, settings)
    audit("Updated company settings", "company_settings", settings.id)
    db.session.commit()
    return jsonify(settings.to_dict())


@app.post("/api/settings/upload/<kind>")
@require_auth("settings", write=True)
def upload_asset(kind):
    if kind not in {"logo", "signature"}:
        return jsonify({"error": "Invalid upload type"}), 400
    file = request.files.get("file")
    if not file:
        return jsonify({"error": "No file uploaded"}), 400
    filename = secure_filename(file.filename)
    path = os.path.join(UPLOAD_DIR, f"{kind}_{filename}")
    file.save(path)
    settings = current_settings()
    setattr(settings, f"{kind}_path", path)
    audit(f"Uploaded {kind}", "company_settings", settings.id)
    db.session.commit()
    return jsonify(settings.to_dict())


def crud_routes(name, model, module, date_fields=None):
    endpoint = f"/api/{name}"

    @app.get(endpoint, endpoint=f"list_{name}")
    @require_auth(module)
    def list_records(model=model):
        return jsonify([row.to_dict() for row in model.query.order_by(model.id.desc()).all()])

    @app.post(endpoint, endpoint=f"create_{name}")
    @require_auth(module, write=True)
    def create_record(model=model, date_fields=date_fields, name=name):
        obj = upsert_model(model, request.get_json(force=True), date_fields=date_fields)
        db.session.add(obj)
        db.session.flush()
        if model is Party:
            rebuild_party_ledger(obj.id)
        audit(f"Created {name}", name, obj.id)
        db.session.commit()
        return jsonify(obj.to_dict()), 201

    @app.put(f"{endpoint}/<int:record_id>", endpoint=f"update_{name}")
    @require_auth(module, write=True)
    def update_record(record_id, model=model, date_fields=date_fields, name=name):
        obj = model.query.get_or_404(record_id)
        upsert_model(model, request.get_json(force=True), obj, date_fields=date_fields)
        if model is Party:
            rebuild_party_ledger(obj.id)
        audit(f"Updated {name}", name, obj.id)
        db.session.commit()
        return jsonify(obj.to_dict())

    @app.delete(f"{endpoint}/<int:record_id>", endpoint=f"delete_{name}")
    @require_auth(module, write=True)
    def delete_record(record_id, model=model, name=name):
        obj = model.query.get_or_404(record_id)
        db.session.delete(obj)
        audit(f"Deleted {name}", name, record_id)
        db.session.commit()
        return jsonify({"ok": True})


crud_routes("parties", Party, "parties")
crud_routes("products", Product, "products")
crud_routes("vehicles", Vehicle, "vehicles", date_fields=["insurance_expiry", "fitness_expiry", "puc_expiry"])


@app.route("/api/invoices", methods=["GET", "POST"])
@require_auth("invoices", write=True)
def invoices():
    if request.method == "GET":
        return jsonify([invoice_to_dict(i) for i in Invoice.query.order_by(Invoice.id.desc()).all()])
    payload = request.get_json(force=True)
    calc = compute_invoice(payload)
    settings = current_settings()
    invoice = Invoice(
        invoice_number=payload.get("invoice_number") or next_number(settings.invoice_prefix, Invoice, "invoice_number"),
        invoice_date=parse_date(payload.get("invoice_date")) or date.today(),
        party_id=payload["party_id"],
        previous_due=float(payload.get("previous_due") or 0),
        discount=float(payload.get("discount") or 0),
        freight=float(payload.get("freight") or 0),
        round_off=float(payload.get("round_off") or 0),
        subtotal=calc["subtotal"], cgst=calc["cgst"], sgst=calc["sgst"], igst=calc["igst"], grand_total=calc["grand_total"],
        paid_amount=float(payload.get("paid_amount") or 0),
        status=payload.get("status") or "Unpaid",
        notes=payload.get("notes", ""),
    )
    for raw in calc["items"]:
        invoice.items.append(upsert_model(InvoiceItem, raw, date_fields=["manufacture_date"], skip=["invoice_id"]))
    db.session.add(invoice)
    db.session.flush()
    rebuild_party_ledger(invoice.party_id)
    audit("Created invoice", "invoices", invoice.id, invoice.invoice_number)
    db.session.commit()
    return jsonify(invoice_to_dict(invoice)), 201


@app.route("/api/invoices/<int:invoice_id>", methods=["GET", "PUT", "DELETE"])
@require_auth("invoices", write=True)
def invoice_detail(invoice_id):
    invoice = Invoice.query.get_or_404(invoice_id)
    if request.method == "GET":
        return jsonify(invoice_to_dict(invoice))
    if request.method == "DELETE":
        party_id = invoice.party_id
        db.session.delete(invoice)
        rebuild_party_ledger(party_id)
        audit("Deleted invoice", "invoices", invoice_id)
        db.session.commit()
        return jsonify({"ok": True})
    payload = request.get_json(force=True)
    calc = compute_invoice(payload)
    invoice.invoice_date = parse_date(payload.get("invoice_date")) or invoice.invoice_date
    invoice.party_id = payload.get("party_id", invoice.party_id)
    invoice.previous_due = float(payload.get("previous_due") or 0)
    invoice.discount = float(payload.get("discount") or 0)
    invoice.freight = float(payload.get("freight") or 0)
    invoice.round_off = float(payload.get("round_off") or 0)
    invoice.subtotal = calc["subtotal"]
    invoice.cgst = calc["cgst"]
    invoice.sgst = calc["sgst"]
    invoice.igst = calc["igst"]
    invoice.grand_total = calc["grand_total"]
    invoice.paid_amount = float(payload.get("paid_amount") or 0)
    invoice.status = payload.get("status") or invoice.status
    invoice.notes = payload.get("notes", "")
    invoice.items.clear()
    for raw in calc["items"]:
        invoice.items.append(upsert_model(InvoiceItem, raw, date_fields=["manufacture_date"], skip=["invoice_id"]))
    rebuild_party_ledger(invoice.party_id)
    audit("Updated invoice", "invoices", invoice.id)
    db.session.commit()
    return jsonify(invoice_to_dict(invoice))


@app.route("/api/payments", methods=["GET", "POST"])
@require_auth("payments", write=True)
def payments():
    if request.method == "GET":
        return jsonify([p.to_dict() | {"party": p.party.to_dict() if p.party else None} for p in Payment.query.order_by(Payment.id.desc()).all()])
    payload = request.get_json(force=True)
    payment = upsert_model(Payment, payload, date_fields=["payment_date"])
    db.session.add(payment)
    db.session.flush()
    remaining = payment.amount
    for inv in Invoice.query.filter_by(party_id=payment.party_id).filter(Invoice.grand_total > Invoice.paid_amount).order_by(Invoice.invoice_date, Invoice.id):
        use = min(remaining, inv.grand_total - inv.paid_amount)
        inv.paid_amount = money(inv.paid_amount + use)
        inv.status = "Paid" if inv.paid_amount >= inv.grand_total else "Partial"
        remaining -= use
        if remaining <= 0:
            break
    rebuild_party_ledger(payment.party_id)
    audit("Created payment", "payments", payment.id)
    db.session.commit()
    return jsonify(payment.to_dict()), 201


@app.route("/api/payments/<int:payment_id>", methods=["PUT", "DELETE"])
@require_auth("payments", write=True)
def payment_detail(payment_id):
    payment = Payment.query.get_or_404(payment_id)
    party_id = payment.party_id
    if request.method == "DELETE":
        db.session.delete(payment)
        rebuild_party_ledger(party_id)
        audit("Deleted payment", "payments", payment_id)
        db.session.commit()
        return jsonify({"ok": True})
    upsert_model(Payment, request.get_json(force=True), payment, date_fields=["payment_date"])
    rebuild_party_ledger(payment.party_id)
    audit("Updated payment", "payments", payment.id)
    db.session.commit()
    return jsonify(payment.to_dict())


@app.get("/api/ledger")
@require_auth("ledger")
def ledger():
    party_id = request.args.get("party_id", type=int)
    query = PartyLedger.query
    if party_id:
        rebuild_party_ledger(party_id)
        query = query.filter_by(party_id=party_id)
    rows = query.order_by(PartyLedger.entry_date, PartyLedger.id).all()
    return jsonify([r.to_dict() | {"party": r.party.to_dict() if r.party else None} for r in rows])


@app.route("/api/re6", methods=["GET", "POST"])
@require_auth("re6", write=True)
def re6_records():
    if request.method == "GET":
        return jsonify([re6_to_dict(r) for r in RE6Record.query.order_by(RE6Record.id.desc()).all()])
    payload = request.get_json(force=True)
    settings = current_settings()
    invoice = Invoice.query.get(payload.get("invoice_id")) if payload.get("invoice_id") else None
    vehicle = Vehicle.query.get(payload.get("vehicle_id")) if payload.get("vehicle_id") else None
    product_lines = []
    cases = 0
    qty = 0
    if invoice:
        for item in invoice.items:
            product_lines.append(f"{item.description} - {item.quantity} {item.unit}, Batch {item.batch_number}, Cases {item.number_of_cases}")
            cases += item.number_of_cases or 0
            qty += item.quantity or 0
    record = RE6Record(
        re6_number=payload.get("re6_number") or next_number(settings.re6_prefix, RE6Record, "re6_number"),
        re6_date=parse_date(payload.get("re6_date")) or date.today(),
        invoice_id=payload.get("invoice_id"),
        consignor=payload.get("consignor") or settings.company_name,
        consignee=payload.get("consignee") or (invoice.party.party_name if invoice and invoice.party else ""),
        vehicle_id=payload.get("vehicle_id"),
        vehicle_number=payload.get("vehicle_number") or (vehicle.vehicle_number if vehicle else ""),
        driver_details=payload.get("driver_details") or (f"{vehicle.driver_name} / {vehicle.driver_license_number}" if vehicle else ""),
        le7_number=payload.get("le7_number") or (vehicle.le7_license_number if vehicle else ""),
        product_details=payload.get("product_details") or "\n".join(product_lines),
        quantity=str(payload.get("quantity") or qty),
        number_of_cases=int(payload.get("number_of_cases") or cases),
        loading_point=payload.get("loading_point") or settings.default_loading_point,
        destination=payload.get("destination") or (invoice.party.address if invoice and invoice.party else ""),
    )
    db.session.add(record)
    db.session.flush()
    audit("Created RE6", "re6", record.id, record.re6_number)
    db.session.commit()
    return jsonify(re6_to_dict(record)), 201


@app.delete("/api/re6/<int:record_id>")
@require_auth("re6", write=True)
def delete_re6(record_id):
    record = RE6Record.query.get_or_404(record_id)
    db.session.delete(record)
    audit("Deleted RE6", "re6", record_id)
    db.session.commit()
    return jsonify({"ok": True})


def pdf_response(title, rows, headers, filename, extra=None, landscape_page=False):
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=landscape(A4) if landscape_page else A4, rightMargin=12*mm, leftMargin=12*mm, topMargin=12*mm, bottomMargin=12*mm)
    styles = getSampleStyleSheet()
    story = [Paragraph(title, styles["Title"]), Spacer(1, 5*mm)]
    company = current_settings()
    story.insert(1, Paragraph(f"{company.company_name} | GSTIN: {company.gstin or '-'}", styles["Normal"]))
    if extra:
        story.append(Paragraph(extra, styles["Normal"]))
        story.append(Spacer(1, 4*mm))
    data = [headers] + rows
    table = Table(data, repeatRows=1)
    table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#263238")),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("GRID", (0, 0), (-1, -1), 0.25, colors.grey),
        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
        ("FONTSIZE", (0, 0), (-1, -1), 8),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
    ]))
    story.append(table)
    doc.build(story)
    buffer.seek(0)
    return send_file(buffer, as_attachment=True, download_name=filename, mimetype="application/pdf")


@app.get("/api/invoices/<int:invoice_id>/pdf")
@require_auth("invoices")
def invoice_pdf(invoice_id):
    inv = Invoice.query.get_or_404(invoice_id)
    rows = [[i.description, i.hsn_code, i.quantity, i.unit, i.rate, i.taxable_value, i.gst_rate, i.cgst, i.sgst, i.igst, i.total] for i in inv.items]
    extra = f"Invoice: {inv.invoice_number} | Date: {inv.invoice_date.isoformat()} | Party: {inv.party.party_name} | Status: {inv.status} | Total: Rs. {inv.grand_total}"
    return pdf_response("Tax Invoice", rows, ["Description", "HSN", "Qty", "Unit", "Rate", "Taxable", "GST%", "CGST", "SGST", "IGST", "Total"], f"{inv.invoice_number.replace('/', '-')}.pdf", extra, True)


@app.get("/api/re6/<int:record_id>/pdf")
@require_auth("re6")
def re6_pdf(record_id):
    r = RE6Record.query.get_or_404(record_id)
    rows = [
        ["RE6 Number", r.re6_number], ["Date", r.re6_date.isoformat()], ["Consignor", r.consignor],
        ["Consignee", r.consignee], ["Vehicle", r.vehicle_number], ["Driver / License", r.driver_details],
        ["LE7 Number", r.le7_number], ["Product Details", r.product_details], ["Quantity", r.quantity],
        ["Number Of Cases", r.number_of_cases], ["Loading Point", r.loading_point], ["Destination", r.destination],
    ]
    return pdf_response("PESO Form RE6", rows, ["Field", "Details"], f"{r.re6_number.replace('/', '-')}.pdf")


@app.get("/api/ledger/pdf")
@require_auth("ledger")
def ledger_pdf():
    party_id = request.args.get("party_id", type=int)
    rows = PartyLedger.query.filter_by(party_id=party_id).order_by(PartyLedger.entry_date, PartyLedger.id).all() if party_id else PartyLedger.query.order_by(PartyLedger.entry_date, PartyLedger.id).all()
    table_rows = [[r.entry_date.isoformat(), r.party.party_name if r.party else "", r.entry_type, r.reference, r.debit, r.credit, r.balance] for r in rows]
    return pdf_response("Party Ledger", table_rows, ["Date", "Party", "Type", "Reference", "Debit", "Credit", "Balance"], "party-ledger.pdf", landscape_page=True)


def report_data(kind):
    if kind == "sales-register":
        rows = Invoice.query.order_by(Invoice.invoice_date.desc()).all()
        return ["Date", "Invoice", "Party", "Taxable", "CGST", "SGST", "IGST", "Total", "Status"], [[r.invoice_date.isoformat(), r.invoice_number, r.party.party_name, r.subtotal, r.cgst, r.sgst, r.igst, r.grand_total, r.status] for r in rows]
    if kind == "gst-summary":
        rows = Invoice.query.order_by(Invoice.invoice_date.desc()).all()
        return ["Invoice", "Taxable", "CGST", "SGST", "IGST", "Total"], [[r.invoice_number, r.subtotal, r.cgst, r.sgst, r.igst, r.grand_total] for r in rows]
    if kind == "party-outstanding":
        rows = Party.query.order_by(Party.party_name).all()
        return ["Party", "Mobile", "Credit Limit", "Outstanding"], [[p.party_name, p.mobile, p.credit_limit, ledger_balance(p.id)] for p in rows]
    if kind == "vehicle-expiry":
        rows = Vehicle.query.order_by(Vehicle.vehicle_number).all()
        return ["Vehicle", "Driver", "Insurance", "Fitness", "PUC"], [[v.vehicle_number, v.driver_name, v.insurance_expiry, v.fitness_expiry, v.puc_expiry] for v in rows]
    if kind == "product-sales":
        totals = {}
        for item in InvoiceItem.query.all():
            totals.setdefault(item.description, {"qty": 0, "total": 0})
            totals[item.description]["qty"] += item.quantity
            totals[item.description]["total"] += item.total
        return ["Product", "Quantity", "Sales"], [[k, money(v["qty"]), money(v["total"])] for k, v in totals.items()]
    if kind == "re6-register":
        rows = RE6Record.query.order_by(RE6Record.re6_date.desc()).all()
        return ["Date", "RE6", "Consignee", "Vehicle", "Cases", "Destination"], [[r.re6_date.isoformat(), r.re6_number, r.consignee, r.vehicle_number, r.number_of_cases, r.destination] for r in rows]
    raise ValueError("Unknown report")


@app.get("/api/reports/<kind>")
@require_auth("reports")
def report(kind):
    headers, rows = report_data(kind)
    return jsonify({"headers": headers, "rows": rows})


@app.get("/api/reports/<kind>/pdf")
@require_auth("reports")
def report_pdf(kind):
    headers, rows = report_data(kind)
    return pdf_response(kind.replace("-", " ").title(), rows, headers, f"{kind}.pdf", landscape_page=True)


@app.get("/api/reports/<kind>/excel")
@require_auth("reports")
def report_excel(kind):
    headers, rows = report_data(kind)
    wb = Workbook()
    ws = wb.active
    ws.title = kind[:31]
    ws.append(headers)
    for row in rows:
        ws.append(row)
    buffer = io.BytesIO()
    wb.save(buffer)
    buffer.seek(0)
    return send_file(buffer, as_attachment=True, download_name=f"{kind}.xlsx", mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")


@app.get("/api/audit-logs")
@require_auth("settings")
def audit_logs():
    return jsonify([r.to_dict() for r in AuditLog.query.order_by(AuditLog.id.desc()).limit(200)])


@app.route("/", defaults={"path": ""})
@app.route("/<path:path>")
def serve_frontend(path):
    if path and os.path.exists(os.path.join(DIST_DIR, path)):
        return send_from_directory(DIST_DIR, path)
    if os.path.exists(os.path.join(DIST_DIR, "index.html")):
        return send_from_directory(DIST_DIR, "index.html")
    return jsonify({"message": "Jatayu RE6 Manager API is running", "frontend": "Run npm install && npm run build to generate dist/."})


def seed_database():
    db.create_all()
    if not User.query.filter_by(username="admin").first():
        db.session.add(User(username="admin", password_hash=generate_password_hash("admin123"), role="Admin"))
    if not CompanySettings.query.first():
        db.session.add(CompanySettings(company_name="Jatayu RE6 Manager", gstin="29ABCDE1234F1Z5", pan="ABCDE1234F", address="Mining Supply Yard", city="Bengaluru", state="Karnataka", pincode="560001", mobile="9999999999", email="accounts@example.com", bank_name="State Bank of India", account_number="00000000000", ifsc="SBIN0000001", branch="Main Branch", default_loading_point="Main Magazine"))
    if Product.query.count() == 0:
        defaults = [
            ("Explosive Box", "360200", "Box", 18, 2500), ("XL Wire", "8544", "Mtr", 18, 12),
            ("Connector Wire", "8544", "Mtr", 18, 10), ("DF Bundle", "360300", "Bundle", 18, 850),
            ("ED Detonator", "360300", "Nos", 18, 45),
        ]
        for name, hsn, unit, gst, rate in defaults:
            db.session.add(Product(product_name=name, hsn_code=hsn, unit=unit, gst_rate=gst, default_rate=rate))
    if Party.query.count() == 0:
        db.session.add(Party(party_name="Sample Quarry Works", gstin="29XYZAB1234C1Z2", address="Tumakuru Road, Karnataka", contact_person="Operations Manager", mobile="9000000000", license_number="EXP/KAR/001", opening_balance=15000, credit_limit=200000))
    if Vehicle.query.count() == 0:
        db.session.add(Vehicle(vehicle_number="KA01AB1234", driver_name="Ravi Kumar", driver_license_number="DL-KA-123456", le7_license_number="LE7/KAR/2026/001", insurance_expiry=date.today() + timedelta(days=20), fitness_expiry=date.today() + timedelta(days=45), puc_expiry=date.today() + timedelta(days=15)))
    db.session.commit()


with app.app_context():
    seed_database()


if __name__ == "__main__":
    app.run(host="127.0.0.1", port=5000, debug=False)
