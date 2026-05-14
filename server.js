const express = require("express");
const cors = require("cors");

const app = express();
const PORT = process.env.PORT || 3000;

app.use(cors());
app.use(express.json({ limit: "50mb" }));

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
    const data = await response.json();
    res.status(response.status).json(data);
  } catch (err) {
    res.status(500).json({ error: err.message });
  }
});

// ── CSV Physics Analysis ─────────────────────────────────────────────────────
app.post("/api/analyze", (req, res) => {
  try {
    const { csv, filename } = req.body;
    if (!csv) return res.status(400).json({ error: "No CSV data" });

    const lines = csv.split("\n").filter(l => l.trim());
    if (lines.length < 2) return res.status(400).json({ error: "CSV too short" });

    const header = lines[0];
    const cols = header.split(",").map(c => c.trim().toLowerCase());
    const nRows = lines.length - 1;

    // Parse all rows into column arrays
    const data = {};
    cols.forEach(c => (data[c] = []));
    for (let i = 1; i < lines.length; i++) {
      const vals = lines[i].split(",");
      if (vals.length !== cols.length) continue;
      cols.forEach((c, j) => data[c].push(parseFloat(vals[j])));
    }

    // Apply valid mask if present
    const validMask = data["valid"]
      ? data["valid"].map(v => v === 1)
      : Array(data[cols[0]].length).fill(true);
    const validN = validMask.filter(Boolean).length;

    const filt = {};
    cols.forEach(c => (filt[c] = data[c].filter((_, i) => validMask[i])));

    // ── Math helpers ──────────────────────────────────────────────────────────
    const mean = a => a.reduce((s, v) => s + v, 0) / a.length;
    const variance = a => { const m = mean(a); return a.map(v => (v - m) ** 2).reduce((s, v) => s + v, 0) / (a.length - 1); };
    const std = a => Math.sqrt(variance(a));
    const linReg = (x, y) => {
      const n = x.length, mx = mean(x), my = mean(y);
      let sxx = 0, sxy = 0;
      for (let i = 0; i < n; i++) { sxx += (x[i] - mx) ** 2; sxy += (x[i] - mx) * (y[i] - my); }
      const slope = sxy / sxx;
      const ic = my - slope * mx;
      const res2 = y.map((yi, i) => (yi - (slope * x[i] + ic)) ** 2).reduce((s, v) => s + v, 0);
      const tot2 = y.map(yi => (yi - my) ** 2).reduce((s, v) => s + v, 0);
      return { slope, intercept: ic, r2: 1 - res2 / tot2, se: Math.sqrt(res2 / (n - 2) / sxx) };
    };

    const out = [];
    out.push(`=== Rohdaten-Auswertung: ${filename} ===`);
    out.push(`Spalten: ${header}`);
    out.push(`Zeilen gesamt: ${nRows} | gültig: ${validN}`);

    // ── Time axis ─────────────────────────────────────────────────────────────
    const tKey = cols.find(c => ["t", "time", "zeit"].includes(c));
    const t = tKey ? filt[tKey] : null;

    if (!t || t.length < 10) {
      out.push("Keine auswertbare Zeitspalte gefunden.");
      return res.json({ summary: out.join("\n") });
    }

    const dt = (t[t.length - 1] - t[0]) / (t.length - 1);
    const fs = 1 / dt;
    const T_ges = t[t.length - 1] - t[0];
    out.push(`\nZEIT: fs = ${fs.toFixed(3)} Hz | Δt = ${dt.toFixed(4)} s | T_ges = ${T_ges.toFixed(2)} s`);

    // ── X / Y columns ─────────────────────────────────────────────────────────
    const xKey = cols.find(c => ["x", "x_pos", "px_x", "x_pixel", "xpos"].includes(c));
    const yKey = cols.find(c => ["y", "y_pos", "px_y", "y_pixel", "ypos"].includes(c));

    if (!xKey || !yKey) {
      out.push("Keine x/y-Spalten erkannt.");
      return res.json({ summary: out.join("\n") });
    }

    const x = filt[xKey], y = filt[yKey];
    const xm = mean(x), ym = mean(y);

    out.push(`\nPOSITION (px):`);
    out.push(`  x: μ=${xm.toFixed(2)}, σ=${std(x).toFixed(2)}, [${Math.min(...x).toFixed(1)}, ${Math.max(...x).toFixed(1)}]`);
    out.push(`  y: μ=${ym.toFixed(2)}, σ=${std(y).toFixed(2)}, [${Math.min(...y).toFixed(1)}, ${Math.max(...y).toFixed(1)}]`);
    out.push(`  Amplitude: Ax=${((Math.max(...x) - Math.min(...x)) / 2).toFixed(2)} px, Ay=${((Math.max(...y) - Math.min(...y)) / 2).toFixed(2)} px`);

    // ── Period via zero crossings ─────────────────────────────────────────────
    const xc = x.map(v => v - xm);
    const crossings = [];
    for (let i = 1; i < xc.length; i++) {
      if (xc[i - 1] < 0 && xc[i] >= 0) {
        const tc = t[i - 1] + (-xc[i - 1] / (xc[i] - xc[i - 1])) * (t[i] - t[i - 1]);
        crossings.push(tc);
      }
    }

    if (crossings.length >= 3) {
      const periods = crossings.slice(1).map((c, i) => c - crossings[i]);
      const T = mean(periods);
      const sT = std(periods);
      const semT = sT / Math.sqrt(periods.length);
      out.push(`\nSCHWINGUNG:`);
      out.push(`  Nulldurchgänge: ${crossings.length}`);
      out.push(`  T = (${T.toFixed(4)} ± ${semT.toFixed(4)}) s  (s_T = ${sT.toFixed(4)} s, N=${periods.length})`);
      out.push(`  f = (${(1/T).toFixed(5)} ± ${(semT/T**2).toFixed(5)}) Hz`);
      out.push(`  ω = (${(2*Math.PI/T).toFixed(5)} ± ${(2*Math.PI*semT/T**2).toFixed(5)}) rad/s`);
    }

    // ── Foucault rotation: principal axis angle per time segment ──────────────
    const N_seg = 30;
    const segSize = Math.floor(x.length / N_seg);
    const seg_t = [], seg_phi = [];

    for (let s = 0; s < N_seg; s++) {
      const i0 = s * segSize;
      const sx = x.slice(i0, i0 + segSize);
      const sy = y.slice(i0, i0 + segSize);
      const msx = mean(sx), msy = mean(sy);
      let sxx = 0, sxy = 0, syy = 0;
      for (let i = 0; i < sx.length; i++) {
        const dx = sx[i] - msx, dy = sy[i] - msy;
        sxx += dx * dx; sxy += dx * dy; syy += dy * dy;
      }
      seg_t.push(t[i0 + Math.floor(segSize / 2)]);
      seg_phi.push(Math.atan2(2 * sxy, sxx - syy) / 2 * (180 / Math.PI));
    }

    // Unwrap ±90° jumps
    for (let i = 1; i < seg_phi.length; i++) {
      while (seg_phi[i] - seg_phi[i - 1] > 90) seg_phi[i] -= 180;
      while (seg_phi[i] - seg_phi[i - 1] < -90) seg_phi[i] += 180;
    }

    const rot = linReg(seg_t, seg_phi);
    const omega_h = rot.slope * 3600;
    const omega_h_err = rot.se * 3600;
    const delta_phi_total = seg_phi[seg_phi.length - 1] - seg_phi[0];

    out.push(`\nFOUCAULT-ROTATION (${N_seg} Segmente):`);
    out.push(`  φ_0 = ${seg_phi[0].toFixed(3)}° | φ_end = ${seg_phi[seg_phi.length-1].toFixed(3)}°`);
    out.push(`  Δφ_ges = ${delta_phi_total.toFixed(3)}° in ${T_ges.toFixed(1)} s`);
    out.push(`  Drehrate: ω_exp = (${omega_h.toFixed(4)} ± ${omega_h_err.toFixed(4)}) °/h`);
    out.push(`  R² = ${rot.r2.toFixed(4)}`);

    // Latitude
    const omega_earth = 15.041; // °/h (siderische Erdrotation)
    const sin_phi = Math.abs(omega_h) / omega_earth;
    out.push(`\nBREITENGRAD (φ_exp aus ω_Foucault = ω_Erde · sin φ):`);
    out.push(`  ω_Erde = ${omega_earth} °/h (siderisch)`);
    out.push(`  sin(φ) = ${sin_phi.toFixed(5)}`);
    if (sin_phi <= 1) {
      const phi = Math.asin(sin_phi) * 180 / Math.PI;
      const dphi = (omega_h_err / (omega_earth * Math.sqrt(Math.max(1 - sin_phi ** 2, 1e-10)))) * 180 / Math.PI;
      const lit = 52.52;
      const abw = Math.abs(phi - lit);
      const sigma = dphi > 0 ? abw / dphi : 999;
      out.push(`  φ_exp = (${phi.toFixed(2)} ± ${dphi.toFixed(2)})°`);
      out.push(`  φ_lit (Berlin) = ${lit}°`);
      out.push(`  Abweichung: |φ_exp - φ_lit| = ${abw.toFixed(2)}° = ${sigma.toFixed(1)}σ`);
    } else {
      out.push(`  sin(φ) > 1 — Messung unplausibel (zu kurze Messzeit oder Störungen)`);
    }

    // Segment table for protocol
    out.push(`\nSEGMENTTABELLE (für Protokoll):`);
    out.push(`t_mid [s], φ [°]`);
    seg_t.forEach((st, i) => out.push(`${st.toFixed(2)}, ${seg_phi[i].toFixed(4)}`));

    // Tracking quality
    const aKey = cols.find(c => ["area", "fläche", "size"].includes(c));
    if (aKey) {
      const ar = filt[aKey];
      out.push(`\nTRACKING (Objektfläche): μ=${mean(ar).toFixed(1)} px², σ=${std(ar).toFixed(1)} px², [${Math.min(...ar).toFixed(0)}, ${Math.max(...ar).toFixed(0)}]`);
    }

    out.push(`\nSTICHPROBE (erste 3 Zeilen): ${header}`);
    lines.slice(1, 4).forEach(l => out.push(l));

    res.json({ summary: out.join("\n") });
  } catch (err) {
    res.status(500).json({ error: err.message });
  }
});

app.get("/health", (_, res) => res.json({ ok: true }));
app.listen(PORT, () => console.log(`PL Proxy on port ${PORT}`));
