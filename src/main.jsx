import React, { useEffect, useMemo, useState } from "react";
import { createRoot } from "react-dom/client";
import "bootstrap/dist/css/bootstrap.min.css";
import {
  BarChart3, Building2, Car, FileText, Gauge, IndianRupee, Landmark, LogOut,
  Moon, Package, ReceiptText, Settings, ShieldCheck, Sun, Truck, Users, WalletCards
} from "lucide-react";
import { Bar } from "react-chartjs-2";
import { Chart as ChartJS, CategoryScale, LinearScale, BarElement, Tooltip, Legend } from "chart.js";
import "./styles.css";

ChartJS.register(CategoryScale, LinearScale, BarElement, Tooltip, Legend);

const API = "";
const blankItem = {
  description: "", hsn_code: "", quantity: 1, unit: "Nos", rate: 0, gst_rate: 18,
  batch_number: "", manufacture_date: "", explosive_class: "Class 2", division: "1.1D", number_of_cases: 0
};
const reports = ["sales-register", "gst-summary", "party-outstanding", "vehicle-expiry", "product-sales", "re6-register"];

function useApi(token) {
  return useMemo(() => async (path, options = {}) => {
    const headers = { ...(options.headers || {}) };
    if (!(options.body instanceof FormData)) headers["Content-Type"] = "application/json";
    if (token) headers.Authorization = `Bearer ${token}`;
    const res = await fetch(API + path, { ...options, headers }).catch(() => {
      throw new Error("Server is not reachable. Please wait for deployment to finish and refresh.");
    });
    if (!res.ok) {
      const err = await res.json().catch(() => ({ error: res.statusText }));
      if (res.status === 401) {
        localStorage.removeItem("jatayu-session");
        window.location.reload();
        return;
      }
      throw new Error(err.error || "Request failed");
    }
    const type = res.headers.get("content-type") || "";
    return type.includes("application/json") ? res.json() : res.blob();
  }, [token]);
}

class ErrorBoundary extends React.Component {
  constructor(props) {
    super(props);
    this.state = { error: null };
  }
  static getDerivedStateFromError(error) {
    return { error };
  }
  render() {
    if (this.state.error) {
      return <div className="surface error-panel">
        <h2>Something went wrong</h2>
        <p>{this.state.error.message || "The screen could not be loaded."}</p>
        <button className="btn btn-warning" onClick={() => { localStorage.removeItem("jatayu-session"); window.location.reload(); }}>Reload App</button>
      </div>;
    }
    return this.props.children;
  }
}

function Login({ onLogin }) {
  const [username, setUsername] = useState("admin");
  const [password, setPassword] = useState("admin123");
  const [error, setError] = useState("");
  async function submit(e) {
    e.preventDefault();
    setError("");
    try {
      const res = await fetch("/api/auth/login", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ username, password })
      });
      const data = await res.json();
      if (!res.ok) throw new Error(data.error);
      onLogin(data);
    } catch (err) {
      setError(err.message);
    }
  }
  return <div className="login-shell">
    <form className="login-panel" onSubmit={submit}>
      <div className="brand-mark"><ShieldCheck size={42} /></div>
      <h1>Jatayu RE6 Manager</h1>
      <p>Offline explosives invoice, ledger, vehicle, and PESO RE6 control desk.</p>
      {error && <div className="alert alert-danger py-2">{error}</div>}
      <input className="form-control" value={username} onChange={e => setUsername(e.target.value)} placeholder="Username" />
      <input className="form-control" type="password" value={password} onChange={e => setPassword(e.target.value)} placeholder="Password" />
      <button className="btn btn-warning w-100 fw-semibold">Login</button>
    </form>
  </div>;
}

function Layout({ user, theme, setTheme, active, setActive, onLogout, children }) {
  const nav = [
    ["dashboard", "Dashboard", Gauge], ["invoices", "Invoices", ReceiptText], ["re6", "RE6 Forms", FileText],
    ["parties", "Parties", Users], ["vehicles", "Vehicles", Truck], ["products", "Products", Package],
    ["payments", "Payments", WalletCards], ["ledger", "Ledger", Landmark], ["reports", "Reports", BarChart3],
    ["settings", "Settings", Settings]
  ];
  return <div className="app-frame">
    <aside className="sidebar">
      <div className="sidebar-brand"><ShieldCheck /><span>Jatayu RE6</span></div>
      <nav>{nav.map(([key, label, Icon]) =>
        <button key={key} className={active === key ? "active" : ""} onClick={() => setActive(key)}><Icon size={18} />{label}</button>
      )}</nav>
    </aside>
    <main className="content">
      <header className="topbar">
        <div><strong>{user.username}</strong><span>{user.role}</span></div>
        <div className="d-flex gap-2">
          <button className="icon-btn" onClick={() => setTheme(theme === "dark" ? "light" : "dark")} title="Theme">
            {theme === "dark" ? <Sun size={18} /> : <Moon size={18} />}
          </button>
          <button className="icon-btn" onClick={onLogout} title="Logout"><LogOut size={18} /></button>
        </div>
      </header>
      {children}
    </main>
  </div>;
}

function Card({ icon: Icon, label, value }) {
  return <div className="metric"><Icon size={22} /><span>{label}</span><strong>{value}</strong></div>;
}

function Dashboard({ api }) {
  const [data, setData] = useState(null);
  const [error, setError] = useState("");
  useEffect(() => { api("/api/dashboard").then(setData).catch(err => setError(err.message)); }, [api]);
  if (error) return <div className="surface error-panel"><h2>Dashboard unavailable</h2><p>{error}</p></div>;
  if (!data) return <Loader />;
  const chart = {
    labels: data.monthly_sales.map(x => x.month),
    datasets: [{ label: "Monthly Sales", data: data.monthly_sales.map(x => x.total), backgroundColor: "#d4a72c" }]
  };
  return <section>
    <div className="page-title"><h2>Dashboard</h2><span>Operational snapshot</span></div>
    <div className="metric-grid">
      <Card icon={IndianRupee} label="Total Revenue" value={`Rs. ${data.total_revenue}`} />
      <Card icon={ReceiptText} label="Total Invoices" value={data.total_invoices} />
      <Card icon={WalletCards} label="Outstanding Payments" value={`Rs. ${data.outstanding_payments}`} />
      <Card icon={FileText} label="Total RE6 Forms" value={data.total_re6_forms} />
      <Card icon={Truck} label="Total Vehicles" value={data.total_vehicles} />
      <Card icon={Car} label="Expiring Fitness" value={data.expiring_vehicle_licenses} />
      <Card icon={ShieldCheck} label="Expiring Insurance" value={data.expiring_insurance} />
    </div>
    <div className="surface"><Bar data={chart} options={{ responsive: true, plugins: { legend: { display: false } } }} /></div>
    <DataTable title="Recent Invoices" rows={data.recent_invoices} columns={["invoice_number", "invoice_date", "grand_total", "status"]} />
  </section>;
}

function EntityPage({ title, endpoint, fields, api, dateFields = [] }) {
  const empty = Object.fromEntries(fields.map(f => [f.name, f.default ?? ""]));
  const [rows, setRows] = useState([]);
  const [form, setForm] = useState(empty);
  const [editing, setEditing] = useState(null);
  const [error, setError] = useState("");
  const load = () => api(endpoint).then(setRows);
  useEffect(load, [endpoint, api]);
  async function save(e) {
    e.preventDefault();
    setError("");
    try {
      await api(editing ? `${endpoint}/${editing}` : endpoint, { method: editing ? "PUT" : "POST", body: JSON.stringify(form) });
      setForm(empty); setEditing(null); load();
    } catch (err) { setError(err.message); }
  }
  async function remove(id) {
    if (confirm("Delete this record?")) { await api(`${endpoint}/${id}`, { method: "DELETE" }); load(); }
  }
  return <section>
    <div className="page-title"><h2>{title}</h2><span>Create, edit, and audit records</span></div>
    <form className="surface form-grid" onSubmit={save}>
      {error && <div className="alert alert-danger grid-full py-2">{error}</div>}
      {fields.map(f => <label key={f.name}>{f.label}
        <input className="form-control" type={dateFields.includes(f.name) ? "date" : "text"} value={form[f.name] ?? ""} onChange={e => setForm({ ...form, [f.name]: e.target.value })} required={f.required} />
      </label>)}
      <div className="grid-full d-flex gap-2">
        <button className="btn btn-warning fw-semibold">{editing ? "Update" : "Save"}</button>
        {editing && <button type="button" className="btn btn-outline-secondary" onClick={() => { setEditing(null); setForm(empty); }}>Cancel</button>}
      </div>
    </form>
    <DataTable title={`${title} List`} rows={rows} columns={fields.slice(0, 7).map(f => f.name)} onEdit={row => { setEditing(row.id); setForm({ ...empty, ...row }); }} onDelete={remove} />
  </section>;
}

function InvoicePage({ api }) {
  const [invoices, setInvoices] = useState([]);
  const [parties, setParties] = useState([]);
  const [products, setProducts] = useState([]);
  const [form, setForm] = useState({ party_id: "", invoice_date: new Date().toISOString().slice(0, 10), discount: 0, freight: 0, round_off: 0, paid_amount: 0, status: "Unpaid", items: [{ ...blankItem }] });
  const load = () => Promise.all([api("/api/invoices"), api("/api/parties"), api("/api/products")]).then(([i, p, pr]) => { setInvoices(i); setParties(p); setProducts(pr); });
  useEffect(load, [api]);
  const totals = calcTotals(form.items, form.discount, form.freight, form.round_off);
  function chooseProduct(index, id) {
    const product = products.find(p => String(p.id) === String(id));
    const items = [...form.items];
    items[index] = { ...items[index], product_id: id, description: product.product_name, hsn_code: product.hsn_code, unit: product.unit, gst_rate: product.gst_rate, rate: product.default_rate };
    setForm({ ...form, items });
  }
  async function save(e) {
    e.preventDefault();
    await api("/api/invoices", { method: "POST", body: JSON.stringify(form) });
    setForm({ ...form, party_id: "", items: [{ ...blankItem }] });
    load();
  }
  return <section>
    <div className="page-title"><h2>Invoices</h2><span>GST invoice with explosive item details</span></div>
    <form className="surface" onSubmit={save}>
      <div className="row g-3">
        <div className="col-md-4"><label>Party<select className="form-select" value={form.party_id} onChange={e => setForm({ ...form, party_id: e.target.value })} required><option value="">Select Party</option>{parties.map(p => <option key={p.id} value={p.id}>{p.party_name}</option>)}</select></label></div>
        <div className="col-md-2"><label>Date<input className="form-control" type="date" value={form.invoice_date} onChange={e => setForm({ ...form, invoice_date: e.target.value })} /></label></div>
        <div className="col-md-2"><label>Status<select className="form-select" value={form.status} onChange={e => setForm({ ...form, status: e.target.value })}><option>Unpaid</option><option>Partial</option><option>Paid</option></select></label></div>
        <div className="col-md-2"><label>Discount<input className="form-control" value={form.discount} onChange={e => setForm({ ...form, discount: e.target.value })} /></label></div>
        <div className="col-md-2"><label>Freight<input className="form-control" value={form.freight} onChange={e => setForm({ ...form, freight: e.target.value })} /></label></div>
      </div>
      <div className="table-responsive mt-3"><table className="table table-sm align-middle">
        <thead><tr><th>Product</th><th>Description</th><th>HSN</th><th>Qty</th><th>Unit</th><th>Rate</th><th>GST%</th><th>Batch</th><th>Mfg</th><th>Class</th><th>Cases</th><th></th></tr></thead>
        <tbody>{form.items.map((item, i) => <tr key={i}>
          <td><select className="form-select form-select-sm" onChange={e => chooseProduct(i, e.target.value)}><option value="">Select</option>{products.map(p => <option key={p.id} value={p.id}>{p.product_name}</option>)}</select></td>
          {["description", "hsn_code", "quantity", "unit", "rate", "gst_rate", "batch_number", "manufacture_date", "explosive_class", "number_of_cases"].map(k =>
            <td key={k}><input className="form-control form-control-sm item-input" type={k.includes("date") ? "date" : "text"} value={item[k] ?? ""} onChange={e => { const items = [...form.items]; items[i] = { ...item, [k]: e.target.value }; setForm({ ...form, items }); }} /></td>
          )}
          <td><button type="button" className="btn btn-sm btn-outline-danger" onClick={() => setForm({ ...form, items: form.items.filter((_, x) => x !== i) })}>×</button></td>
        </tr>)}</tbody>
      </table></div>
      <div className="d-flex justify-content-between align-items-center">
        <button type="button" className="btn btn-outline-secondary" onClick={() => setForm({ ...form, items: [...form.items, { ...blankItem }] })}>Add Item</button>
        <div className="invoice-total">Taxable Rs. {totals.subtotal} | GST Rs. {totals.tax} | Total Rs. {totals.grand}</div>
        <button className="btn btn-warning fw-semibold">Create Invoice</button>
      </div>
    </form>
    <DataTable title="Invoice Register" rows={invoices} columns={["invoice_number", "invoice_date", "party.party_name", "grand_total", "paid_amount", "status"]} pdfPath={row => `/api/invoices/${row.id}/pdf`} api={api} />
  </section>;
}

function RE6Page({ api }) {
  const [records, setRecords] = useState([]);
  const [invoices, setInvoices] = useState([]);
  const [vehicles, setVehicles] = useState([]);
  const [form, setForm] = useState({ invoice_id: "", vehicle_id: "", re6_date: new Date().toISOString().slice(0, 10), destination: "" });
  const load = () => Promise.all([api("/api/re6"), api("/api/invoices"), api("/api/vehicles")]).then(([r, i, v]) => { setRecords(r); setInvoices(i); setVehicles(v); });
  useEffect(load, [api]);
  async function save(e) {
    e.preventDefault();
    await api("/api/re6", { method: "POST", body: JSON.stringify(form) });
    setForm({ ...form, invoice_id: "", vehicle_id: "", destination: "" });
    load();
  }
  return <section>
    <div className="page-title"><h2>RE6 Forms</h2><span>Generate PESO movement documents from invoices</span></div>
    <form className="surface form-grid" onSubmit={save}>
      <label>Invoice<select className="form-select" value={form.invoice_id} onChange={e => setForm({ ...form, invoice_id: e.target.value })}><option value="">Select Invoice</option>{invoices.map(i => <option key={i.id} value={i.id}>{i.invoice_number} - {i.party?.party_name}</option>)}</select></label>
      <label>Vehicle<select className="form-select" value={form.vehicle_id} onChange={e => setForm({ ...form, vehicle_id: e.target.value })}><option value="">Select Vehicle</option>{vehicles.map(v => <option key={v.id} value={v.id}>{v.vehicle_number}</option>)}</select></label>
      <label>Date<input className="form-control" type="date" value={form.re6_date} onChange={e => setForm({ ...form, re6_date: e.target.value })} /></label>
      <label>Destination<input className="form-control" value={form.destination} onChange={e => setForm({ ...form, destination: e.target.value })} /></label>
      <div className="grid-full"><button className="btn btn-warning fw-semibold">Generate RE6</button></div>
    </form>
    <DataTable title="RE6 Register" rows={records} columns={["re6_number", "re6_date", "consignee", "vehicle_number", "number_of_cases", "destination"]} pdfPath={row => `/api/re6/${row.id}/pdf`} api={api} />
  </section>;
}

function Payments({ api }) {
  const [rows, setRows] = useState([]);
  const [parties, setParties] = useState([]);
  const [form, setForm] = useState({ party_id: "", payment_date: new Date().toISOString().slice(0, 10), amount: "", payment_mode: "Cash", reference_number: "", notes: "" });
  const load = () => Promise.all([api("/api/payments"), api("/api/parties")]).then(([p, parties]) => { setRows(p); setParties(parties); });
  useEffect(load, [api]);
  async function save(e) {
    e.preventDefault();
    await api("/api/payments", { method: "POST", body: JSON.stringify(form) });
    setForm({ ...form, amount: "", reference_number: "", notes: "" });
    load();
  }
  return <section>
    <div className="page-title"><h2>Payments</h2><span>Receipts auto-adjust outstanding invoices</span></div>
    <form className="surface form-grid" onSubmit={save}>
      <label>Party<select className="form-select" value={form.party_id} onChange={e => setForm({ ...form, party_id: e.target.value })} required><option value="">Select Party</option>{parties.map(p => <option value={p.id} key={p.id}>{p.party_name}</option>)}</select></label>
      {["payment_date", "amount", "payment_mode", "reference_number", "notes"].map(k => <label key={k}>{labelize(k)}<input className="form-control" type={k.includes("date") ? "date" : "text"} value={form[k]} onChange={e => setForm({ ...form, [k]: e.target.value })} required={k === "amount"} /></label>)}
      <div className="grid-full"><button className="btn btn-warning fw-semibold">Record Payment</button></div>
    </form>
    <DataTable title="Payment Register" rows={rows} columns={["payment_date", "party.party_name", "amount", "payment_mode", "reference_number"]} />
  </section>;
}

function Ledger({ api }) {
  const [rows, setRows] = useState([]);
  const [parties, setParties] = useState([]);
  const [party, setParty] = useState("");
  useEffect(() => { api("/api/parties").then(setParties); }, [api]);
  useEffect(() => { api(`/api/ledger${party ? `?party_id=${party}` : ""}`).then(setRows); }, [api, party]);
  return <section>
    <div className="page-title"><h2>Ledger</h2><span>Opening balance, invoices, payments, and outstanding</span></div>
    <div className="surface d-flex gap-2 align-items-end">
      <label className="flex-grow-1">Party<select className="form-select" value={party} onChange={e => setParty(e.target.value)}><option value="">All Parties</option>{parties.map(p => <option value={p.id} key={p.id}>{p.party_name}</option>)}</select></label>
      <a className="btn btn-outline-warning" href={`/api/ledger/pdf${party ? `?party_id=${party}` : ""}`} target="_blank">PDF</a>
    </div>
    <DataTable title="Ledger Entries" rows={rows} columns={["entry_date", "party.party_name", "entry_type", "reference", "debit", "credit", "balance"]} />
  </section>;
}

function Reports({ api }) {
  const [kind, setKind] = useState(reports[0]);
  const [data, setData] = useState({ headers: [], rows: [] });
  useEffect(() => { api(`/api/reports/${kind}`).then(setData); }, [api, kind]);
  return <section>
    <div className="page-title"><h2>Reports</h2><span>PDF and Excel exports</span></div>
    <div className="surface d-flex gap-2 align-items-end flex-wrap">
      <label className="flex-grow-1">Report<select className="form-select" value={kind} onChange={e => setKind(e.target.value)}>{reports.map(r => <option key={r} value={r}>{labelize(r)}</option>)}</select></label>
      <a className="btn btn-outline-warning" href={`/api/reports/${kind}/pdf`} target="_blank">PDF</a>
      <a className="btn btn-outline-success" href={`/api/reports/${kind}/excel`} target="_blank">Excel</a>
    </div>
    <div className="surface table-responsive"><table className="table"><thead><tr>{data.headers.map(h => <th key={h}>{h}</th>)}</tr></thead><tbody>{data.rows.map((r, i) => <tr key={i}>{r.map((c, j) => <td key={j}>{String(c ?? "")}</td>)}</tr>)}</tbody></table></div>
  </section>;
}

function SettingsPage({ api }) {
  const fields = ["company_name", "gstin", "pan", "address", "city", "state", "pincode", "phone", "mobile", "email", "website", "bank_name", "account_number", "ifsc", "branch", "invoice_prefix", "re6_prefix", "default_loading_point"];
  const [form, setForm] = useState({});
  useEffect(() => { api("/api/settings/company").then(setForm); }, [api]);
  async function save(e) {
    e.preventDefault();
    setForm(await api("/api/settings/company", { method: "PUT", body: JSON.stringify(form) }));
  }
  async function upload(kind, file) {
    const fd = new FormData();
    fd.append("file", file);
    setForm(await api(`/api/settings/upload/${kind}`, { method: "POST", body: fd }));
  }
  return <section>
    <div className="page-title"><h2>Settings</h2><span>Company, bank, invoice, and RE6 defaults</span></div>
    <form className="surface form-grid" onSubmit={save}>
      {fields.map(k => <label key={k}>{labelize(k)}<input className="form-control" value={form[k] ?? ""} onChange={e => setForm({ ...form, [k]: e.target.value })} /></label>)}
      <label>Logo Upload<input className="form-control" type="file" onChange={e => upload("logo", e.target.files[0])} /></label>
      <label>Signature Upload<input className="form-control" type="file" onChange={e => upload("signature", e.target.files[0])} /></label>
      <div className="grid-full"><button className="btn btn-warning fw-semibold">Save Settings</button></div>
    </form>
  </section>;
}

function DataTable({ title, rows, columns, onEdit, onDelete, pdfPath, api }) {
  async function download(path) {
    const blob = await api(path);
    const url = URL.createObjectURL(blob);
    window.open(url, "_blank");
  }
  return <div className="surface table-responsive">
    <h3>{title}</h3>
    <table className="table table-hover align-middle"><thead><tr>{columns.map(c => <th key={c}>{labelize(c.split(".").pop())}</th>)}{(onEdit || onDelete || pdfPath) && <th>Actions</th>}</tr></thead>
      <tbody>{rows.map(row => <tr key={row.id}>
        {columns.map(c => <td key={c}>{String(deep(row, c) ?? "")}</td>)}
        {(onEdit || onDelete || pdfPath) && <td className="actions">
          {pdfPath && <button className="btn btn-sm btn-outline-warning" onClick={() => download(pdfPath(row))}>PDF</button>}
          {onEdit && <button className="btn btn-sm btn-outline-secondary" onClick={() => onEdit(row)}>Edit</button>}
          {onDelete && <button className="btn btn-sm btn-outline-danger" onClick={() => onDelete(row.id)}>Delete</button>}
        </td>}
      </tr>)}</tbody></table>
  </div>;
}

function Loader() { return <div className="surface">Loading...</div>; }
function deep(obj, path) { return path.split(".").reduce((a, k) => a?.[k], obj); }
function labelize(s) { return s.replaceAll("_", " ").replaceAll("-", " ").replace(/\b\w/g, m => m.toUpperCase()); }
function calcTotals(items, discount = 0, freight = 0, roundOff = 0) {
  const subtotal = items.reduce((sum, i) => sum + Number(i.quantity || 0) * Number(i.rate || 0), 0);
  const tax = items.reduce((sum, i) => sum + Number(i.quantity || 0) * Number(i.rate || 0) * Number(i.gst_rate || 0) / 100, 0);
  return { subtotal: subtotal.toFixed(2), tax: tax.toFixed(2), grand: (subtotal + tax - Number(discount || 0) + Number(freight || 0) + Number(roundOff || 0)).toFixed(2) };
}

function App() {
  const [session, setSession] = useState(() => {
    try {
      return JSON.parse(localStorage.getItem("jatayu-session") || "null");
    } catch {
      localStorage.removeItem("jatayu-session");
      return null;
    }
  });
  const [active, setActive] = useState("dashboard");
  const [theme, setTheme] = useState(localStorage.getItem("jatayu-theme") || "dark");
  const api = useApi(session?.token);
  useEffect(() => { document.documentElement.dataset.theme = theme; localStorage.setItem("jatayu-theme", theme); }, [theme]);
  if (!session) return <Login onLogin={data => { localStorage.setItem("jatayu-session", JSON.stringify(data)); setSession(data); }} />;
  const common = { api };
  const pages = {
    dashboard: <Dashboard {...common} />,
    parties: <EntityPage title="Parties" endpoint="/api/parties" api={api} fields={[
      { name: "party_name", label: "Party Name", required: true }, { name: "gstin", label: "GSTIN" }, { name: "address", label: "Address" }, { name: "contact_person", label: "Contact Person" }, { name: "mobile", label: "Mobile" }, { name: "email", label: "Email" }, { name: "license_number", label: "License Number" }, { name: "opening_balance", label: "Opening Balance", default: 0 }, { name: "credit_limit", label: "Credit Limit", default: 0 }
    ]} />,
    vehicles: <EntityPage title="Vehicles" endpoint="/api/vehicles" api={api} dateFields={["insurance_expiry", "fitness_expiry", "puc_expiry"]} fields={[
      { name: "vehicle_number", label: "Vehicle Number", required: true }, { name: "driver_name", label: "Driver Name" }, { name: "driver_license_number", label: "Driver License Number" }, { name: "le7_license_number", label: "LE7 License Number" }, { name: "insurance_expiry", label: "Insurance Expiry" }, { name: "fitness_expiry", label: "Fitness Expiry" }, { name: "puc_expiry", label: "PUC Expiry" }
    ]} />,
    products: <EntityPage title="Products" endpoint="/api/products" api={api} fields={[
      { name: "product_name", label: "Product Name", required: true }, { name: "hsn_code", label: "HSN Code" }, { name: "unit", label: "Unit", default: "Nos" }, { name: "gst_rate", label: "GST Rate", default: 18 }, { name: "default_rate", label: "Default Rate", default: 0 }
    ]} />,
    invoices: <InvoicePage {...common} />,
    re6: <RE6Page {...common} />,
    payments: <Payments {...common} />,
    ledger: <Ledger {...common} />,
    reports: <Reports {...common} />,
    settings: <SettingsPage {...common} />
  };
  return <Layout user={session.user} active={active} setActive={setActive} theme={theme} setTheme={setTheme} onLogout={() => { localStorage.removeItem("jatayu-session"); setSession(null); }}>
    <ErrorBoundary key={active}>
      {pages[active]}
    </ErrorBoundary>
  </Layout>;
}

createRoot(document.getElementById("root")).render(<App />);
