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
from reportlab.pdfgen import canvas
from reportlab.lib.utils import ImageReader
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


def fmt_money(value):
    return f"{money(value):,.2f}".rstrip("0").rstrip(".")


ONES = ["", "One", "Two", "Three", "Four", "Five", "Six", "Seven", "Eight", "Nine", "Ten", "Eleven", "Twelve", "Thirteen", "Fourteen", "Fifteen", "Sixteen", "Seventeen", "Eighteen", "Nineteen"]
TENS = ["", "", "Twenty", "Thirty", "Forty", "Fifty", "Sixty", "Seventy", "Eighty", "Ninety"]


def number_words(n):
    n = int(round(n or 0))
    if n == 0:
        return "Zero"
    def below_100(num):
        return ONES[num] if num < 20 else (TENS[num // 10] + (" " + ONES[num % 10] if num % 10 else ""))
    def below_1000(num):
        return (ONES[num // 100] + " Hundred " if num >= 100 else "") + (below_100(num % 100) if num % 100 else "")
    parts = []
    for value, name in [(10000000, "Crore"), (100000, "Lakh"), (1000, "Thousand")]:
        if n >= value:
            parts.append(below_1000(n // value).strip() + " " + name)
            n %= value
    if n:
        parts.append(below_1000(n).strip())
    return " ".join(parts).strip()


def wrap_text(text, max_chars):
    words = str(text or "").replace("\n", " ").split()
    lines, current = [], ""
    for word in words:
        candidate = f"{current} {word}".strip()
        if len(candidate) > max_chars and current:
            lines.append(current)
            current = word
        else:
            current = candidate
    if current:
        lines.append(current)
    return lines or [""]


def draw_wrapped(c, text, x, y, max_chars, leading=12, font="Helvetica", size=10, bold_first=False, max_lines=None):
    lines = wrap_text(text, max_chars)
    if max_lines:
        lines = lines[:max_lines]
    for index, line in enumerate(lines):
        c.setFont("Helvetica-Bold" if bold_first and index == 0 else font, size)
        c.drawString(x, y - index * leading, line)
    return y - len(lines) * leading


def draw_uploaded_image(c, path, x, y, width, height):
    if not path or not os.path.exists(path):
        return False
    try:
        c.drawImage(ImageReader(path), x, y, width=width, height=height, preserveAspectRatio=True, mask="auto")
        return True
    except Exception:
        return False


def invoice_pdf_response(inv):
    settings = current_settings()
    buffer = io.BytesIO()
    c = canvas.Canvas(buffer, pagesize=A4)
    w, h = A4
    left, right = 30, w - 30
    y = h - 22

    c.setFont("Helvetica-Bold", 12)
    c.drawString(left, y, "TAX INVOICE")
    c.setStrokeColor(colors.HexColor("#8a8798"))
    c.setFillColor(colors.white)
    c.rect(left + 106, y - 6, 158, 20, stroke=1, fill=0)
    c.setFillColor(colors.HexColor("#8a8798"))
    c.setFont("Helvetica-Bold", 11)
    c.drawString(left + 110, y, "ORIGINAL FOR RECIPIENT")
    c.setFillColor(colors.black)

    logo_drawn = draw_uploaded_image(c, settings.logo_path, left + 8, h - 138, 92, 92)
    if not logo_drawn:
        c.setFillColor(colors.HexColor("#1f3148"))
        c.rect(left + 12, h - 128, 82, 78, stroke=0, fill=1)
        c.setFillColor(colors.white)
        c.setFont("Helvetica-Bold", 42)
        c.drawCentredString(left + 53, h - 108, (settings.company_name or "J")[:1].upper())
        c.setFillColor(colors.black)

    c.setFont("Helvetica-Bold", 22)
    c.drawString(left + 112, h - 82, settings.company_name or "Company Name")
    c.setFont("Helvetica", 10)
    draw_wrapped(c, f"{settings.address}, {settings.city}, {settings.state}, {settings.pincode}".strip(", "), left + 112, h - 102, 72, leading=11)
    c.setFont("Helvetica-Bold", 10)
    c.drawString(left + 112, h - 124, "Mobile:")
    c.setFont("Helvetica", 10)
    c.drawString(left + 154, h - 124, settings.mobile or settings.phone or "-")
    c.setFont("Helvetica-Bold", 10)
    c.drawString(left + 230, h - 124, "GSTIN:")
    c.setFont("Helvetica", 10)
    c.drawString(left + 266, h - 124, settings.gstin or "-")
    c.setFont("Helvetica-Bold", 10)
    c.drawString(left + 374, h - 124, "PAN Number:")
    c.setFont("Helvetica", 10)
    c.drawString(left + 440, h - 124, settings.pan or "-")
    c.setFont("Helvetica-Bold", 10)
    c.drawString(left + 112, h - 138, "Email:")
    c.setFont("Helvetica", 10)
    c.drawString(left + 148, h - 138, settings.email or "-")

    y = h - 165
    c.setLineWidth(6)
    c.line(left, y + 15, right, y + 15)
    c.setFillColor(colors.HexColor("#e8e8e8"))
    c.rect(left, y - 26, right - left, 42, stroke=0, fill=1)
    c.setFillColor(colors.black)
    c.setFont("Helvetica-Bold", 11)
    c.drawString(left + 12, y - 7, "Invoice No.:")
    c.setFont("Helvetica", 11)
    c.drawString(left + 86, y - 7, inv.invoice_number)
    c.setFont("Helvetica-Bold", 11)
    c.drawRightString(right - 100, y - 7, "Invoice Date:")
    c.setFont("Helvetica", 11)
    c.drawRightString(right - 12, y - 7, inv.invoice_date.strftime("%d/%m/%Y"))

    y -= 44
    bill_x, ship_x, veh_x = left, left + 182, left + 362
    c.setFont("Helvetica-Bold", 11)
    c.drawString(bill_x, y, "BILL TO")
    c.drawString(ship_x, y, "SHIP TO")
    c.drawString(veh_x, y, "Vehicle No.")
    re6_vehicle = RE6Record.query.filter_by(invoice_id=inv.id).order_by(RE6Record.id.desc()).first()
    c.setFont("Helvetica", 11)
    c.drawString(veh_x + 108, y, re6_vehicle.vehicle_number if re6_vehicle else "")

    party = inv.party
    address = party.address if party else ""
    party_block = f"{party.party_name if party else ''}\n{address}"
    y_bill = draw_wrapped(c, party.party_name if party else "", bill_x, y - 22, 28, leading=12, font="Helvetica-Bold", size=10)
    y_bill = draw_wrapped(c, address, bill_x, y_bill - 2, 33, leading=11, size=10, max_lines=5)
    c.setFont("Helvetica", 10)
    c.drawString(bill_x, y_bill - 2, f"Mobile: {party.mobile if party else ''}")
    c.drawString(bill_x, y_bill - 15, f"GSTIN: {party.gstin if party else ''}")
    pan = party.gstin[2:12] if party and party.gstin and len(party.gstin) >= 12 else ""
    c.drawString(bill_x, y_bill - 28, f"PAN Number: {pan}")
    c.drawString(bill_x, y_bill - 41, f"Place of Supply: {settings.state or ''}")
    y_ship = draw_wrapped(c, party.party_name if party else "", ship_x, y - 22, 28, leading=12, font="Helvetica-Bold", size=10)
    draw_wrapped(c, address, ship_x, y_ship - 2, 33, leading=11, size=10, max_lines=6)

    y = h - 350
    c.setLineWidth(1.4)
    c.line(left, y, right, y)
    headers = [("ITEMS", left + 6), ("HSN", left + 218), ("QTY.", left + 300), ("RATE", left + 372), ("TAX", left + 448), ("AMOUNT", right - 52)]
    c.setFont("Helvetica-Bold", 11)
    for label, x in headers:
        c.drawString(x, y - 20, label)
    c.setLineWidth(1.4)
    c.line(left, y - 32, right, y - 32)
    row_y = y - 52
    for item in inv.items[:8]:
        c.setFont("Helvetica", 10)
        draw_wrapped(c, item.description, left + 6, row_y, 30, leading=10, size=10, max_lines=2)
        c.drawRightString(left + 255, row_y, item.hsn_code or "")
        c.drawRightString(left + 322, row_y, f"{fmt_money(item.quantity)} {item.unit}")
        c.drawRightString(left + 404, row_y, fmt_money(item.rate))
        tax_amount = item.cgst + item.sgst + item.igst
        c.drawRightString(left + 464, row_y, fmt_money(tax_amount))
        c.setFont("Helvetica", 8)
        c.drawRightString(left + 464, row_y - 10, f"({fmt_money(item.gst_rate)}%)")
        c.setFont("Helvetica", 10)
        c.drawRightString(right - 8, row_y, fmt_money(item.total))
        c.setStrokeColor(colors.HexColor("#d0d0d0"))
        c.line(left, row_y - 22, right, row_y - 22)
        c.setStrokeColor(colors.black)
        row_y -= 34

    subtotal_y = 344
    c.setLineWidth(1.4)
    c.line(left, subtotal_y, right, subtotal_y)
    c.setFont("Helvetica-Bold", 10)
    c.drawString(left + 6, subtotal_y - 17, "SUBTOTAL")
    c.drawRightString(left + 322, subtotal_y - 17, "-")
    c.drawRightString(left + 464, subtotal_y - 17, f"Rs. {fmt_money(inv.cgst + inv.sgst + inv.igst)}")
    c.drawRightString(right - 8, subtotal_y - 17, f"Rs. {fmt_money(inv.grand_total)}")
    c.line(left, subtotal_y - 28, right, subtotal_y - 28)

    y = subtotal_y - 48
    c.setFont("Helvetica-Bold", 10)
    c.drawString(left + 6, y, "BANK DETAILS")
    c.setFont("Helvetica", 10)
    bank_rows = [("Name:", settings.company_name), ("IFSC Code:", settings.ifsc), ("Account No:", settings.account_number), ("Bank:", f"{settings.bank_name} ,{settings.branch}".strip(" ,"))]
    for idx, (label, value) in enumerate(bank_rows):
        c.drawString(left + 6, y - 15 - idx * 14, label)
        c.drawString(left + 86, y - 15 - idx * 14, value or "-")
    c.setFont("Helvetica-Bold", 10)
    c.drawString(left + 6, y - 92, "TERMS AND CONDITIONS")
    c.setFont("Helvetica", 10)
    c.drawString(left + 6, y - 108, "1. All disputes are subject to local jurisdiction only")

    tx = left + 348
    ty = y + 3
    totals = [
        ("Taxable Amount", inv.subtotal),
        ("CGST @9%", inv.cgst),
        ("SGST @9%", inv.sgst),
        ("IGST", inv.igst),
        ("Total Amount", inv.grand_total),
        ("Received Amount", inv.paid_amount),
        ("Previous Balance", inv.previous_due),
        ("Current Balance", inv.previous_due + inv.grand_total - inv.paid_amount),
    ]
    for idx, (label, value) in enumerate(totals):
        yy = ty - idx * 14
        c.setFont("Helvetica-Bold" if label == "Total Amount" else "Helvetica", 10)
        c.drawRightString(right - 92, yy, label)
        c.drawRightString(right - 8, yy, f"Rs. {fmt_money(value)}")
        if label in {"IGST", "Total Amount", "Received Amount"}:
            c.setStrokeColor(colors.HexColor("#777777"))
            c.line(tx, yy - 6, right, yy - 6)
            c.setStrokeColor(colors.black)

    c.setFont("Helvetica-Bold", 10)
    c.drawRightString(right - 8, 154, "Total Amount (in words)")
    c.setFont("Helvetica", 10)
    c.drawRightString(right - 8, 140, f"{number_words(inv.grand_total)} Rupees")
    draw_uploaded_image(c, settings.signature_path, right - 86, 80, 76, 42)
    c.setFont("Helvetica-Bold", 10)
    c.drawRightString(right - 8, 48, "AUTHORISED SIGNATORY FOR")
    c.setFont("Helvetica", 10)
    c.drawRightString(right - 8, 34, settings.company_name or "")

    c.showPage()
    c.save()
    buffer.seek(0)
    return send_file(buffer, as_attachment=True, download_name=f"{inv.invoice_number.replace('/', '-')}.pdf", mimetype="application/pdf")


def re6_pdf_response(r):
    settings = current_settings()
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=A4, rightMargin=16*mm, leftMargin=16*mm, topMargin=12*mm, bottomMargin=12*mm)
    styles = getSampleStyleSheet()
    normal = styles["Normal"]
    normal.fontName = "Helvetica"
    normal.fontSize = 8
    normal.leading = 10
    story = [
        Paragraph("<b>FORM RE-6</b>", styles["Title"]),
        Paragraph("(See rule 61(2) of the Explosives Rules, 2008)", styles["Normal"]),
        Paragraph("<b>Form of records to be maintained by a licensee</b>", styles["Normal"]),
        Paragraph("Records of explosives transported by road van", styles["Normal"]),
        Spacer(1, 4*mm),
    ]
    small = styles["Normal"].clone("small-re6")
    small.fontName = "Helvetica"
    small.fontSize = 6.4
    small.leading = 7.2
    small_bold = styles["Normal"].clone("small-re6-bold")
    small_bold.fontName = "Helvetica-Bold"
    small_bold.fontSize = 6.4
    small_bold.leading = 7.2
    def sp(text, bold=False):
        return Paragraph(str(text or "").replace("\n", "<br/>"), small_bold if bold else small)
    items = []
    if r.invoice:
        for item in r.invoice.items:
            items.append([
                sp(item.description),
                sp(item.explosive_class or ""),
                sp(item.division or ""),
                sp(f"{item.batch_number or 'BARCODE AS PER ANNEXURE'}\n{item.manufacture_date.isoformat() if item.manufacture_date else ''}"),
                sp(f"{fmt_money(item.quantity)} {item.unit}"),
                sp(f"{item.number_of_cases or ''} {item.unit if item.number_of_cases else ''}"),
            ])
    if not items:
        items = [[sp(r.product_details), sp(""), sp(""), sp(""), sp(r.quantity), sp(str(r.number_of_cases or ""))]]
    desc_headers = [sp("Name and Description", True), sp("Class", True), sp("Division", True), sp("Batch No. and Date", True), sp("Quantity transported", True), sp("No. of Case/Packets", True)]
    desc_table = Table([desc_headers] + items, colWidths=[36*mm, 13*mm, 13*mm, 27*mm, 20*mm, 17*mm])
    desc_table.setStyle(TableStyle([
        ("GRID", (0, 0), (-1, -1), 0.6, colors.black),
        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
        ("FONTSIZE", (0, 0), (-1, -1), 6.4),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("LEFTPADDING", (0, 0), (-1, -1), 4),
        ("RIGHTPADDING", (0, 0), (-1, -1), 4),
    ]))
    licence = settings.default_loading_point or "Magazine License No."
    def p(text, bold=False):
        safe = str(text or "").replace("\n", "<br/>")
        return Paragraph(f"<b>{safe}</b>" if bold else safe, normal)
    rows = [
        [p("Note", True), p("This record should be kept up to date. Licence number in Form LE-7 of Explosives Rules, 2008")],
        [p("Explosives Road Van No.", True), p(r.vehicle_number)],
        [p("1 Date", True), p(r.re6_date.strftime("%d/%m/%Y"))],
        [p("2 Name, address and license number of the consignor", True), p(f"{r.consignor}\n{settings.address}\nDispatched from {licence}")],
        [p("3 Place of loading", True), p(r.loading_point)],
        [p("4-8 Description of explosives", True), desc_table],
        [p("9 PASS Number", True), p(r.re6_number)],
        [p("10 Signature of the consignor", True), p("")],
        [p("11 Name and address of the consignee", True), p(f"{r.consignee}\n{r.destination}")],
        [p("12 Place of unloading", True), p(r.destination)],
        [p("13 Date of unloading of explosives", True), p("")],
        [p("14 Signature of consignee", True), p("")],
        [p("15 Remarks", True), p("")],
    ]
    table = Table(rows, colWidths=[44*mm, 130*mm], repeatRows=0)
    table.setStyle(TableStyle([
        ("GRID", (0, 0), (-1, -1), 0.6, colors.black),
        ("FONTNAME", (0, 0), (0, -1), "Helvetica-Bold"),
        ("FONTNAME", (1, 0), (1, -1), "Helvetica"),
        ("FONTSIZE", (0, 0), (-1, -1), 8),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("LEFTPADDING", (0, 0), (-1, -1), 5),
        ("RIGHTPADDING", (0, 0), (-1, -1), 5),
        ("TOPPADDING", (0, 0), (-1, -1), 5),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
    ]))
    story.append(table)
    doc.build(story)
    buffer.seek(0)
    return send_file(buffer, as_attachment=True, download_name=f"{r.re6_number.replace('/', '-')}.pdf", mimetype="application/pdf")


@app.get("/api/invoices/<int:invoice_id>/pdf")
@require_auth("invoices")
def invoice_pdf(invoice_id):
    inv = Invoice.query.get_or_404(invoice_id)
    return invoice_pdf_response(inv)


@app.get("/api/re6/<int:record_id>/pdf")
@require_auth("re6")
def re6_pdf(record_id):
    r = RE6Record.query.get_or_404(record_id)
    return re6_pdf_response(r)


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
    port = int(os.environ.get("PORT", "5000"))
    app.run(host="0.0.0.0", port=port, debug=False)
