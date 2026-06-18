const http = require("http");
const fs = require("fs");
const path = require("path");
const crypto = require("crypto");

const port = Number(process.env.PORT || 3000);
const root = __dirname;
const isRailway = Boolean(process.env.RAILWAY_ENVIRONMENT || process.env.RAILWAY_SERVICE_ID);
const railwayVolumeDir = process.env.RAILWAY_VOLUME_MOUNT_PATH || "/data";
const dataDir = process.env.DATA_DIR || (isRailway ? railwayVolumeDir : (fs.existsSync("/data") ? "/data" : path.join(root, "data")));
const usersPath = path.join(dataDir, "users.json");
const sessions = new Map();

const DEFAULT_USERS = [
  { username: "admin", password: "Admin@2026", companyName: "Admin Profile" },
  { username: "accounts", password: "Accounts@2026", companyName: "Accounts Profile" },
  { username: "dispatch", password: "Dispatch@2026", companyName: "Dispatch Profile" },
  { username: "viewer", password: "Viewer@2026", companyName: "Viewer Profile" }
];

const types = {
  ".html": "text/html; charset=utf-8",
  ".css": "text/css; charset=utf-8",
  ".js": "application/javascript; charset=utf-8",
  ".json": "application/json; charset=utf-8",
  ".png": "image/png",
  ".jpg": "image/jpeg",
  ".jpeg": "image/jpeg",
  ".svg": "image/svg+xml"
};

function ensureStore() {
  try {
    fs.mkdirSync(dataDir, { recursive: true });
    if (!fs.existsSync(usersPath)) {
      fs.writeFileSync(usersPath, JSON.stringify({ users: [] }, null, 2));
    }
  } catch (error) {
    const railwayHint = isRailway
      ? ` Railway needs a persistent Volume mounted at ${dataDir}. Add a Railway Volume, set mount path to ${dataDir}, then redeploy.`
      : "";
    throw new Error(`Cannot write data store at ${dataDir}.${railwayHint} Original error: ${error.message}`);
  }
}

function readStore() {
  ensureStore();
  return JSON.parse(fs.readFileSync(usersPath, "utf8"));
}

function writeStore(store) {
  ensureStore();
  fs.writeFileSync(usersPath, JSON.stringify(store, null, 2));
}

function hashPassword(password, salt = crypto.randomBytes(16).toString("hex")) {
  const hash = crypto.pbkdf2Sync(password, salt, 120000, 32, "sha256").toString("hex");
  return `${salt}:${hash}`;
}

function verifyPassword(password, stored) {
  const [salt, hash] = String(stored || "").split(":");
  if (!salt || !hash) return false;
  return hashPassword(password, salt) === stored;
}

function extractDefaultData() {
  const html = fs.readFileSync(path.join(root, "index.html"), "utf8");
  const start = html.indexOf("var D = ");
  const end = html.indexOf("var DEFAULT_DATA", start);
  if (start === -1 || end === -1) return null;
  const script = `${html.slice(start, end)}; D;`;
  const vm = require("vm");
  return vm.runInNewContext(script, {});
}

function seedDefaultUsers() {
  const store = readStore();
  const defaultData = extractDefaultData();
  let changed = false;
  for (const account of DEFAULT_USERS) {
    if (store.users.some(user => user.username === account.username)) continue;
    const data = defaultData ? JSON.parse(JSON.stringify(defaultData)) : null;
    if (data && data.co) data.co.name = account.companyName;
    store.users.push({
      username: account.username,
      passwordHash: hashPassword(account.password),
      createdAt: new Date().toISOString(),
      seeded: true,
      data
    });
    changed = true;
  }
  if (changed) writeStore(store);
}

function sendJson(res, status, payload) {
  res.writeHead(status, { "Content-Type": "application/json; charset=utf-8" });
  res.end(JSON.stringify(payload));
}

function readBody(req) {
  return new Promise((resolve, reject) => {
    let body = "";
    req.on("data", chunk => {
      body += chunk;
      if (body.length > 10 * 1024 * 1024) {
        req.destroy();
        reject(new Error("Request too large"));
      }
    });
    req.on("end", () => {
      if (!body) return resolve({});
      try {
        resolve(JSON.parse(body));
      } catch {
        reject(new Error("Invalid JSON"));
      }
    });
  });
}

function getSessionUser(req) {
  const header = req.headers.authorization || "";
  const token = header.startsWith("Bearer ") ? header.slice(7) : "";
  if (!token) return null;
  const username = sessions.get(token);
  if (!username) return null;
  const store = readStore();
  return store.users.find(u => u.username === username) || null;
}

function publicUser(user) {
  return {
    username: user.username,
    companyName: user.data && user.data.co ? user.data.co.name : user.username
  };
}

async function handleApi(req, res, pathname) {
  try {
    if (pathname === "/api/register" && req.method === "POST") {
      const body = await readBody(req);
      const username = String(body.username || "").trim().toLowerCase();
      const password = String(body.password || "");
      if (!/^[a-z0-9._-]{3,40}$/.test(username)) {
        return sendJson(res, 400, { error: "Username must be 3-40 letters, numbers, dot, dash, or underscore." });
      }
      if (password.length < 6) {
        return sendJson(res, 400, { error: "Password must be at least 6 characters." });
      }
      const store = readStore();
      if (store.users.some(u => u.username === username)) {
        return sendJson(res, 409, { error: "Username already exists." });
      }
      store.users.push({
        username,
        passwordHash: hashPassword(password),
        createdAt: new Date().toISOString(),
        data: body.data || null
      });
      writeStore(store);
      const token = crypto.randomBytes(32).toString("hex");
      sessions.set(token, username);
      return sendJson(res, 201, { token, user: { username } });
    }

    if (pathname === "/api/login" && req.method === "POST") {
      const body = await readBody(req);
      const username = String(body.username || "").trim().toLowerCase();
      const password = String(body.password || "");
      const store = readStore();
      const user = store.users.find(u => u.username === username);
      if (!user || !verifyPassword(password, user.passwordHash)) {
        return sendJson(res, 401, { error: "Invalid username or password." });
      }
      const token = crypto.randomBytes(32).toString("hex");
      sessions.set(token, username);
      return sendJson(res, 200, { token, user: publicUser(user) });
    }

    if (pathname === "/api/logout" && req.method === "POST") {
      const header = req.headers.authorization || "";
      const token = header.startsWith("Bearer ") ? header.slice(7) : "";
      if (token) sessions.delete(token);
      return sendJson(res, 200, { ok: true });
    }

    if (pathname === "/api/me" && req.method === "GET") {
      const user = getSessionUser(req);
      if (!user) return sendJson(res, 401, { error: "Login required." });
      return sendJson(res, 200, { user: publicUser(user) });
    }

    if (pathname === "/api/me/data" && req.method === "GET") {
      const user = getSessionUser(req);
      if (!user) return sendJson(res, 401, { error: "Login required." });
      return sendJson(res, 200, { data: user.data || null });
    }

    if (pathname === "/api/me/data" && req.method === "POST") {
      const user = getSessionUser(req);
      if (!user) return sendJson(res, 401, { error: "Login required." });
      const body = await readBody(req);
      const store = readStore();
      const target = store.users.find(u => u.username === user.username);
      target.data = body.data;
      target.updatedAt = new Date().toISOString();
      writeStore(store);
      return sendJson(res, 200, { ok: true });
    }

    return sendJson(res, 404, { error: "API route not found." });
  } catch (error) {
    return sendJson(res, 500, { error: error.message || "Server error." });
  }
}

const server = http.createServer((req, res) => {
  const pathname = decodeURIComponent((req.url || "/").split("?")[0]);

  if (pathname === "/health") {
    sendJson(res, 200, {
      ok: true,
      service: "jagdish-trading-manager",
      dataDir,
      persistentStorageRequired: isRailway,
      storageMode: isRailway ? "railway-volume" : "local-file"
    });
    return;
  }

  if (pathname.startsWith("/api/")) {
    handleApi(req, res, pathname);
    return;
  }

  const relative = pathname === "/" ? "index.html" : pathname.replace(/^\/+/, "");
  const target = path.resolve(root, relative);

  if (!target.startsWith(root)) {
    res.writeHead(403);
    res.end("Forbidden");
    return;
  }

  fs.readFile(target, (err, data) => {
    if (err) {
      fs.readFile(path.join(root, "index.html"), (fallbackErr, fallback) => {
        if (fallbackErr) {
          res.writeHead(404);
          res.end("Not found");
          return;
        }
        res.writeHead(200, { "Content-Type": types[".html"] });
        res.end(fallback);
      });
      return;
    }
    const ext = path.extname(target).toLowerCase();
    res.writeHead(200, { "Content-Type": types[ext] || "application/octet-stream" });
    res.end(data);
  });
});

ensureStore();
seedDefaultUsers();
server.listen(port, "0.0.0.0", () => {
  console.log(`Jagdish Trading Manager running on port ${port}`);
  console.log(`Data store: ${usersPath}`);
});
