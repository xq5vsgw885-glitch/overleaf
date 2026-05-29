const express = require("express");
const cors = require("cors");
const { execFile } = require("child_process");
const fs = require("fs");
const path = require("path");
const os = require("os");
const sqlite3 = require("sqlite3").verbose();

const app = express();
const PORT = process.env.PORT || 3000;

app.use(cors());
app.use(express.json({ limit: "50mb" }));
app.use(express.static(__dirname));

const dbPath = path.join(__dirname, "database", "botanik_v4_0_production_ready.db");
const botanikDb = new sqlite3.Database(dbPath);

app.get("/api/botanik/health", (_, res) => {
  botanikDb.get("SELECT version, release_stage FROM botanik_release_manifest", [], (err, row) => {
    if (err) return res.status(500).json({ ok: false, error: err.message });
    res.json({ ok: true, database: "botanik_v4_0_production_ready.db", release: row });
  });
});



app.get("/api/botanik/features/photo", (req, res) => {
  const visibility = String(req.query.visibility || "high").trim();
  const weight = String(req.query.weight || "high").trim();

  const sql = `
    SELECT f.*, t.scientific_name, t.german_name, t.rank
    FROM botanik_features f
    LEFT JOIN botanik_taxa t ON t.taxon_id = f.taxon_id
    WHERE f.visibility_in_photo = ?
      AND f.diagnostic_weight = ?
    ORDER BY t.scientific_name, f.organ, f.character
    LIMIT 100
  `;

  botanikDb.all(sql, [visibility, weight], (err, rows) => {
    if (err) return res.status(500).json({ error: err.message });
    res.json({ count: rows.length, filters: { visibility, weight }, rows });
  });
});

app.get("/api/botanik/taxon/:id", (req, res) => {
  const taxonId = String(req.params.id || "").trim();

  botanikDb.get("SELECT * FROM botanik_taxa WHERE taxon_id = ?", [taxonId], (err, taxon) => {
    if (err) return res.status(500).json({ error: err.message });
    if (!taxon) return res.status(404).json({ error: "Taxon not found" });

    botanikDb.all("SELECT * FROM botanik_features WHERE taxon_id = ? ORDER BY organ, feature_group, character", [taxonId], (err2, features) => {
      if (err2) return res.status(500).json({ error: err2.message });
      res.json({ taxon, features_count: features.length, features });
    });
  });
});

app.get("/api/botanik/taxa", (req, res) => {
  const q = String(req.query.q || "").trim();
  const includeStubs = String(req.query.include_stubs || "") === "1";

  const statusFilter = includeStubs
    ? `COALESCE(status, "") NOT IN (?, ?, ?)`
    : `COALESCE(status, "") NOT IN (?, ?, ?, ?)`;

  const baseFilter = `
    ${statusFilter}
    AND COALESCE(app_scope, "") != ?
  `;

  const sql = q
    ? `SELECT * FROM botanik_taxa
       WHERE (${baseFilter})
         AND (scientific_name LIKE ? OR german_name LIKE ? OR taxon_id LIKE ?)
       LIMIT 50`
    : `SELECT * FROM botanik_taxa
       WHERE (${baseFilter})
       LIMIT 50`;

  const statusParams = includeStubs
    ? ["deprecated", "reference_only", "critical"]
    : ["deprecated", "reference_only", "critical", "stub"];

  const params = q
    ? [...statusParams, "exclude_from_identification", `%${q}%`, `%${q}%`, `%${q}%`]
    : [...statusParams, "exclude_from_identification"];

  botanikDb.all(sql, params, (err, rows) => {
    if (err) return res.status(500).json({ error: err.message });
    res.json({ count: rows.length, limit: 50, maybe_truncated: rows.length === 50, include_stubs: includeStubs, rows });
  });
});




// ── Health ───────────────────────────────────────────────────────────────────
app.get("/health", (_, res) => res.json({ ok: true, python: true }));

// ── Anthropic Proxy ──────────────────────────────────────────────────────────
app.post("/api/generate", async (req, res) => {
  const apiKey = process.env.ANTHROPIC_API_KEY;
  if (!apiKey) return res.status(500).json({ error: "ANTHROPIC_API_KEY not set" });
  try {
    const response = await fetch("https://api.anthropic.com/v1/messages", {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        "x-api-key": apiKey,
        "anthropic-version": "2023-06-01",
      },
      body: JSON.stringify(req.body),
    });
    // Strip markdown fences
    const data = await response.json();
    if (data.content) {
      data.content = data.content.map(b => {
        if (b.type === "text") {
          b.text = b.text.replace(/^```(?:latex|tex)?\s*/i, "").replace(/\s*```\s*$/, "").trim();
          const dc = b.text.indexOf("\\documentclass");
          if (dc > 0) b.text = b.text.slice(dc);
        }
        return b;
      });
    }
    res.status(response.status).json(data);
  } catch (err) {
    res.status(500).json({ error: err.message });
  }
});

// ── Python Notebook Runner ───────────────────────────────────────────────────
app.post("/api/run-notebook", async (req, res) => {
  const { csv, filename, versuch, n_segmente } = req.body;
  if (!csv) return res.status(400).json({ error: "Keine CSV-Daten" });

  // Temporäres Verzeichnis anlegen
  const tmpDir = fs.mkdtempSync(path.join(os.tmpdir(), "pl-nb-"));
  const csvPath = path.join(tmpDir, filename || "messdaten.csv");
  const pyPath  = path.join(tmpDir, "auswertung.py");
  const outPath = path.join(tmpDir, "ergebnisse.json");

  // CSV schreiben
  fs.writeFileSync(csvPath, csv, "utf8");

  // Python-Skript schreiben
  const pyScript = buildPythonScript(csvPath, outPath, versuch || "Versuch", n_segmente || 30);
  fs.writeFileSync(pyPath, pyScript, "utf8");

  // Python ausführen
  execFile("python3", [pyPath], { timeout: 60000 }, (err, stdout, stderr) => {
    let result;
    try {
      result = JSON.parse(fs.readFileSync(outPath, "utf8"));
    } catch {
      result = null;
    }
    // Cleanup
    try { fs.rmSync(tmpDir, { recursive: true }); } catch {}

    if (err && !result) {
      return res.status(500).json({
        error: "Python-Auswertung fehlgeschlagen",
        details: stderr?.slice(0, 500) || err.message
      });
    }
    res.json(result || { error: "Keine Ergebnisse" });
  });
});

// ── Python-Skript Generator ───────────────────────────────────────────────────
function buildPythonScript(csvPath, outPath, versuch, nSeg) {
  return `
import numpy as np
import pandas as pd
from scipy import stats
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import json, warnings, base64, io, sys
warnings.filterwarnings('ignore')

plt.rcParams.update({'figure.dpi':120,'font.size':10,
  'axes.grid':True,'grid.alpha':0.3,
  'axes.spines.top':False,'axes.spines.right':False})

out = {"versuch": ${JSON.stringify(versuch)}, "plots": {}, "ergebnisse": {}, "tabellen": {}, "pgfplots": {}}

def fig_to_b64(fig):
    buf = io.BytesIO()
    fig.savefig(buf, format='png', bbox_inches='tight', dpi=120)
    buf.seek(0)
    return base64.b64encode(buf.read()).decode()

# ── 1. Daten laden ─────────────────────────────────────────────────────────
df_raw = pd.read_csv(${JSON.stringify(csvPath)}, comment='#')
cols = [c.strip().lower() for c in df_raw.columns]
df_raw.columns = cols

# Valid-Filter
if 'valid' in cols:
    df = df_raw[df_raw['valid'] == 1].copy()
else:
    df = df_raw.copy()

N = len(df)
out['ergebnisse']['N'] = N
out['ergebnisse']['spalten'] = list(df.columns)

# Zeitachse
t_col = next((c for c in cols if c in ['t','time','zeit']), None)
x_col = next((c for c in cols if c in ['x','x_pos','px_x','xpos']), None)
y_col = next((c for c in cols if c in ['y','y_pos','px_y','ypos']), None)
a_col = next((c for c in cols if c in ['area','flaeche','size']), None)

if not t_col:
    out['error'] = 'Keine Zeitspalte (t/time/zeit) gefunden'
    with open(${JSON.stringify(outPath)}, 'w') as f: json.dump(out, f)
    sys.exit(0)

t = df[t_col].values
dt = float(np.median(np.diff(t)))
fs = 1.0 / dt
T_ges = float(t[-1] - t[0])

out['ergebnisse']['dt_s']   = round(dt, 4)
out['ergebnisse']['fs_hz']  = round(fs, 3)
out['ergebnisse']['T_ges_s'] = round(T_ges, 2)
out['ergebnisse']['T_ges_min'] = round(T_ges/60, 2)

# ── 2. Statistik [Mallick Gl. 6-9] ─────────────────────────────────────────
stat = {}
for name, arr in [(t_col,t)] + ([(x_col, df[x_col].values)] if x_col else []) + ([(y_col, df[y_col].values)] if y_col else []) + ([(a_col, df[a_col].values)] if a_col else []):
    mu  = float(np.mean(arr))            # Gl. 6
    s   = float(np.std(arr, ddof=1))     # Gl. 7
    sem = float(s / np.sqrt(N))          # Gl. 9
    stat[name] = {'mu': round(mu,4), 's': round(s,4), 'sem': round(sem,6),
                  'min': round(float(arr.min()),4), 'max': round(float(arr.max()),4)}
out['tabellen']['statistik'] = stat

if not x_col or not y_col:
    out['ergebnisse']['hinweis'] = 'Nur Statistik verfuegbar (x/y-Spalten fehlen)'
    with open(${JSON.stringify(outPath)}, 'w') as f: json.dump(out, f)
    sys.exit(0)

x = df[x_col].values
y = df[y_col].values

# ── 3. Trajektorie ──────────────────────────────────────────────────────────
x0, y0 = float(np.mean(x)), float(np.mean(y))
Ax = float((x.max()-x.min())/2)
Ay = float((y.max()-y.min())/2)
out['ergebnisse']['x_mean'] = round(x0,2)
out['ergebnisse']['y_mean'] = round(y0,2)
out['ergebnisse']['Ax_px']  = round(Ax,2)
out['ergebnisse']['Ay_px']  = round(Ay,2)
out['ergebnisse']['elliptizitaet'] = round(Ay/Ax,3) if Ax>0 else None

fig, axes = plt.subplots(1,2,figsize=(11,4.5))
ax=axes[0]
sc=ax.scatter(x,y,c=t,cmap='viridis',s=0.8,alpha=0.5)
plt.colorbar(sc,ax=ax,label='t / s',shrink=0.9)
ax.set_xlabel('x / px'); ax.set_ylabel('y / px')
ax.set_title('Trajektorie'); ax.set_aspect('equal')

ax2=axes[1]
ax2.plot(t,x-x0,'b-',lw=0.3,alpha=0.7,label='x − x̄')
ax2.plot(t,y-y0,'r-',lw=0.3,alpha=0.7,label='y − ȳ')
ax2.set_xlabel('t / s'); ax2.set_ylabel('Auslenkung / px')
ax2.set_title('Zeitreihe'); ax2.legend(fontsize=8)
plt.tight_layout()
out['plots']['trajektorie'] = fig_to_b64(fig)
plt.close()

# ── 4. Schwingungsdauer [Mallick Gl. 6-9] ──────────────────────────────────
xc = x - x0
cidx = np.where((xc[:-1]<0) & (xc[1:]>=0))[0]
t_cross = []
for i in cidx:
    frac = -xc[i]/(xc[i+1]-xc[i]) if (xc[i+1]-xc[i])!=0 else 0
    t_cross.append(t[i] + frac*(t[i+1]-t[i]))
t_cross = np.array(t_cross)
T_arr = np.diff(t_cross)

if len(T_arr) >= 3:
    T_mean = float(np.mean(T_arr))
    s_T    = float(np.std(T_arr, ddof=1))
    sem_T  = float(s_T/np.sqrt(len(T_arr)))
    f_mean = 1.0/T_mean
    Df     = sem_T/T_mean**2          # Gl.14: |df/dT|·ΔT
    om0    = 2*np.pi/T_mean
    Dom0   = 2*np.pi*sem_T/T_mean**2

    out['ergebnisse']['T_s']      = round(T_mean,5)
    out['ergebnisse']['Delta_T_s']= round(sem_T,5)
    out['ergebnisse']['s_T_s']    = round(s_T,5)
    out['ergebnisse']['N_per']    = int(len(T_arr))
    out['ergebnisse']['f_hz']     = round(f_mean,6)
    out['ergebnisse']['Delta_f']  = round(Df,6)
    out['ergebnisse']['omega0']   = round(om0,6)
    out['ergebnisse']['Delta_om'] = round(Dom0,6)

    # Pendellänge aus T
    g = 9.810
    L_exp   = g*T_mean**2/(4*np.pi**2)
    Delta_L = 2*g*T_mean*sem_T/(4*np.pi**2)
    out['ergebnisse']['L_exp_m']   = round(L_exp,4)
    out['ergebnisse']['Delta_L_m'] = round(Delta_L,4)

    fig,axes=plt.subplots(1,2,figsize=(11,4))
    axes[0].plot(T_arr,'ko',ms=2,alpha=0.6)
    axes[0].axhline(T_mean,color='r',lw=1.5,label=f'T̄={T_mean:.4f} s')
    axes[0].fill_between(range(len(T_arr)),T_mean-sem_T,T_mean+sem_T,alpha=0.2,color='r')
    axes[0].set_xlabel('Perioden-Index'); axes[0].set_ylabel('T / s')
    axes[0].set_title('Einzelperioden'); axes[0].legend(fontsize=8)
    axes[1].hist(T_arr,bins=20,color='steelblue',edgecolor='white')
    axes[1].axvline(T_mean,color='r',lw=2)
    axes[1].set_xlabel('T / s'); axes[1].set_ylabel('Häufigkeit')
    axes[1].set_title('Verteilung der Perioden')
    plt.tight_layout()
    out['plots']['perioden'] = fig_to_b64(fig)
    plt.close()

# ── 5. Foucault-Drehrate [papula2018, Mallick Gl.22-28] ─────────────────────
N_SEG = ${nSeg}
seg_sz = N//N_SEG
seg_t, seg_phi = [], []

for s in range(N_SEG):
    i0=s*seg_sz; i1=i0+seg_sz
    xs=x[i0:i1]-np.mean(x[i0:i1]); ys=y[i0:i1]-np.mean(y[i0:i1])
    Sxx=float(np.var(xs,ddof=1)); Syy=float(np.var(ys,ddof=1))
    Sxy=float(np.mean(xs*ys))
    phi_s=0.5*np.arctan2(2*Sxy,Sxx-Syy)*180/np.pi
    seg_t.append(float(t[i0+seg_sz//2]))
    seg_phi.append(float(phi_s))

seg_t=np.array(seg_t); seg_phi=np.array(seg_phi)
for i in range(1,len(seg_phi)):
    while seg_phi[i]-seg_phi[i-1]>90:  seg_phi[i]-=180
    while seg_phi[i]-seg_phi[i-1]<-90: seg_phi[i]+=180

# Segmenttabelle
out['tabellen']['segmente'] = [
    {'t_mid': round(float(st),2), 'phi': round(float(sp),4)}
    for st,sp in zip(seg_t,seg_phi)
]

# Lineare Regression [Mallick Gl.22-28]
reg=stats.linregress(seg_t,seg_phi)
b=float(reg.slope); a_int=float(reg.intercept)
se_b=float(reg.stderr); se_a=float(reg.intercept_stderr)
r2=float(reg.rvalue**2)
res=seg_phi-(a_int+b*seg_t)
s_y=float(np.sqrt(np.sum(res**2)/max(N_SEG-2,1)))

b_h=b*3600; se_b_h=se_b*3600  # °/h

out['ergebnisse']['phi0_deg']   = round(a_int,4)
out['ergebnisse']['b_deg_s']    = round(b,7)
out['ergebnisse']['Delta_b']    = round(se_b,7)
out['ergebnisse']['b_h']        = round(b_h,4)
out['ergebnisse']['Delta_b_h']  = round(se_b_h,4)
out['ergebnisse']['s_y']        = round(s_y,4)
out['ergebnisse']['R2']         = round(r2,6)
out['ergebnisse']['N_seg']      = N_SEG
out['ergebnisse']['seg_sz_s']   = round(seg_sz*dt,1)

# Breitengrad [Mallick Gl.14]
OMEGA_E=15.041; PHI_LIT=52.52
sin_phi=abs(b_h)/OMEGA_E
out['ergebnisse']['sin_phi']=round(sin_phi,5)
if sin_phi<=1.0:
    phi_exp=float(np.degrees(np.arcsin(sin_phi)))
    Delta_phi=se_b_h/(OMEGA_E*np.sqrt(max(1-sin_phi**2,1e-10)))
    abw=abs(phi_exp-PHI_LIT)
    sigma=abw/Delta_phi if Delta_phi>0 else float('inf')
    out['ergebnisse']['phi_exp']     = round(phi_exp,2)
    out['ergebnisse']['Delta_phi']   = round(Delta_phi,2)
    out['ergebnisse']['phi_lit']     = PHI_LIT
    out['ergebnisse']['abw_deg']     = round(abw,2)
    out['ergebnisse']['abw_sigma']   = round(sigma,1)
else:
    out['ergebnisse']['phi_exp'] = None
    out['ergebnisse']['hinweis_phi'] = f'sin(phi)={sin_phi:.4f}>1 — Messzeit zu kurz oder starke Stoerungen'

# pgfplots-Koordinaten
coords=' '.join(f'({st:.1f},{sp:.4f})' for st,sp in zip(seg_t,seg_phi))
out['pgfplots']['winkel_coords'] = coords
out['pgfplots']['fit_a'] = round(a_int,4)
out['pgfplots']['fit_b'] = round(b,7)
out['pgfplots']['fit_formel'] = f'{a_int:.4f} + {b:.7f}*x'

# Winkel-Plot
t_fit=np.linspace(seg_t[0],seg_t[-1],300)
fig,axes=plt.subplots(1,2,figsize=(12,5))
ax1=axes[0]
ax1.errorbar(seg_t,seg_phi,yerr=s_y,fmt='o',ms=4,color='steelblue',
             capsize=3,label='Segmentwinkel $\\\\varphi_i$',zorder=3)
ax1.plot(t_fit,a_int+b*t_fit,'r-',lw=2,
         label=f'Fit: $b=({b_h:.3f}\\\\pm{se_b_h:.3f})$ °/h\\n$R^2={r2:.4f}$')
ax1.set_xlabel('$t$ / s'); ax1.set_ylabel('$\\\\varphi$ / °')
ax1.set_title('Schwingungsebene'); ax1.legend(fontsize=8)
ax2=axes[1]
ax2.plot(seg_t,res,'ko',ms=3,alpha=0.7)
ax2.axhline(0,color='r',lw=1)
ax2.fill_between(seg_t,-s_y,s_y,alpha=0.15,color='r',label=f'$s_y={s_y:.3f}°$')
ax2.set_xlabel('$t$ / s'); ax2.set_ylabel('Residuum / °')
ax2.set_title('Residuen'); ax2.legend(fontsize=8)
plt.tight_layout()
out['plots']['winkel'] = fig_to_b64(fig)
plt.close()

# Tracking-Qualität
if a_col:
    area=df[a_col].values
    mu_a=float(np.mean(area)); s_a=float(np.std(area,ddof=1))
    cv=s_a/mu_a*100
    out['ergebnisse']['area_mean']=round(mu_a,2)
    out['ergebnisse']['area_s']=round(s_a,2)
    out['ergebnisse']['area_cv']=round(cv,2)
    fig,ax=plt.subplots(figsize=(10,3))
    ax.plot(t,area,'k-',lw=0.3,alpha=0.5)
    ax.axhline(mu_a,color='r',lw=1.5,label=f'Ā={mu_a:.2f} px²')
    ax.fill_between(t,mu_a-s_a,mu_a+s_a,alpha=0.15,color='r')
    ax.set_xlabel('t / s'); ax.set_ylabel('Fläche / px²')
    ax.set_title(f'Tracking-Qualität  (CV={cv:.1f}%)'); ax.legend(fontsize=8)
    plt.tight_layout()
    out['plots']['tracking'] = fig_to_b64(fig)
    plt.close()

# Ausgabe
with open(${JSON.stringify(outPath)}, 'w', encoding='utf-8') as f:
    json.dump(out, f, ensure_ascii=False)
print("OK")
`;
}

app.listen(PORT, () => console.log(`PL Server on port ${PORT}`));
