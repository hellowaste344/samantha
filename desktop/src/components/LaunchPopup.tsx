import { useState, useEffect, useRef } from "react";
import { Eye, MousePointer, Settings, X, Zap, FolderOpen } from "lucide-react";
import { invoke } from "@tauri-apps/api/core";

/**
 * LaunchPopup — 420×300 centered dark window.
 *
 * Sketch layout:
 *   [Z actions btn]   [ Hi! I'm Samantha  ]
 *                     [    ○ waveform ○    ]
 *                     [     [launch]       ]
 *
 * Click Launch → card slides right → overlay bar snaps to right edge → popup hides.
 * The key fix: invoke("launch_overlay") is called immediately; CSS animation is
 * purely cosmetic and runs in parallel — no 380ms blocking delay.
 */
export function LaunchPopup() {
  const [phase, setPhase] = useState<"idle" | "animating" | "done">("idle");
  const [showActions, setShowActions] = useState(false);
  const [actionStatus, setActionStatus] = useState<string | null>(null);
  const [pulse, setPulse] = useState(false);
  const canvasRef = useRef<HTMLCanvasElement>(null);

  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas) return;
    const ctx = canvas.getContext('2d')!;
    const W = canvas.width, H = canvas.height, CY = H / 2;
    const NODES = 28, SPACING =8, AMP = 12, SPEED = 0.015;
    let t = 0, raf: number;

    const drawStrand = (points: any[], cf: string, cb: string) => {
      for (let i = 0; i < points.length - 1; i++) {
        const p0 = points[i], p1 = points[i + 1];
        const z = (p0.z + p1.z) / 2;
        const t01 = (z + 1) / 2;
        ctx.beginPath();
        ctx.moveTo(p0.x, p0.y);
        ctx.lineTo(p1.x, p1.y);
        ctx.strokeStyle = `rgba(${cf},${0.2 + 0.8 * t01})`;
        ctx.lineWidth = 1.2 + 2.8 * t01;
        ctx.lineCap = 'round';
        ctx.stroke();
      }
    };

    const frame = () => {
      ctx.clearRect(0, 0, W, H);
      const pA = [], pB = [];
      for (let i = 0; i < NODES; i++) {
        const x = i * SPACING;
        const a = (i / (NODES - 1)) * Math.PI * 4 - t;
        pA.push({ x, y: CY + Math.sin(a) * AMP, z: Math.cos(a) });
        pB.push({ x, y: CY + Math.sin(a + Math.PI) * AMP, z: Math.cos(a + Math.PI) });
      }
      
      // strands
      const azA = pA.reduce((s, p) => s + p.z, 0) / NODES;
      const azB = pB.reduce((s, p) => s + p.z, 0) / NODES;
      if (azA < azB) { drawStrand(pA, '59,130,246', '59,130,246'); drawStrand(pB, '96,165,250', '96,165,250'); }
      else { drawStrand(pB, '96,165,250', '96,165,250'); drawStrand(pA, '59,130,246', '59,130,246'); }
     
      t += SPEED;
      raf = requestAnimationFrame(frame);
    };
    frame();
    return () => cancelAnimationFrame(raf);
  }, []);

  // In JSX:
  <div className="lp-wave-ring" aria-hidden>
    <canvas ref={canvasRef} width={100} height={100} style={{display:'block', borderRadius:'50%'}}/>
  </div>

  // Heartbeat pulse for wave ring
  useEffect(() => {
    const id = setInterval(() => setPulse(v => !v), 1800);
    return () => clearInterval(id);
  }, []);

  // Close actions panel when clicking outside
  useEffect(() => {
    if (!showActions) return;
    const handler = () => setShowActions(false);
    window.addEventListener("click", handler, { capture: true, once: true });
    return () => window.removeEventListener("click", handler, { capture: true });
  }, [showActions]);

  // ── Launch handler ─────────────────────────────────────────────────────────
  const handleLaunch = async () => {
    if (phase !== "idle") return;
    setShowActions(false);
    setPhase("animating");

    // Invoke Rust immediately — it shows the overlay AND hides the launch window.
    // The CSS animation is purely cosmetic (runs in parallel).
    try {
      await invoke("launch_overlay");
      // If we're still mounted (edge case: invoke resolved but window not hidden yet)
      setPhase("done");
    } catch (err) {
      console.error("[LaunchPopup] launch_overlay failed:", err);
      setPhase("idle");
    }
  };

  // ── Action helpers ─────────────────────────────────────────────────────────
  const showHint = (msg: string) => {
    setShowActions(false);
    setActionStatus(msg);
    setTimeout(() => setActionStatus(null), 2500);
  };

  const openSettings = async () => {
    setShowActions(false);
    setActionStatus("Opening settings…");
    try {
      await invoke("open_settings");
      setTimeout(() => setActionStatus(null), 1200);
    } catch {
      setActionStatus("Start the agent first");
      setTimeout(() => setActionStatus(null), 2000);
    }
  };

  const openConfigFolder = async () => {
    setShowActions(false);
    try {
      await invoke("open_config_folder");
    } catch {
      showHint("Could not open config folder");
    }
  };

  const isLaunching = phase === "animating" || phase === "done";

  return (
    <div className="lp-root" data-tauri-drag-region>

      {/* ── Close button ─────────────────────────────────────────────── */}
      <button
        className="lp-close"
        onClick={() => invoke("close_launch")}
        aria-label="Close"
      >
        <X size={11} />
      </button>

      {/* ── Actions "Z" button ───────────────────────────────────────── */}
      <div className="lp-actions-wrap">
        <button
          className={`lp-z-btn${showActions ? " lp-z-btn--open" : ""}`}
          onClick={(e) => { e.stopPropagation(); setShowActions(v => !v); }}
          aria-label="Actions"
          aria-expanded={showActions}
          disabled={isLaunching}
        >
          <span className="lp-z-letter">Z</span>
        </button>
        <span className="lp-z-label">actions</span>

        {/* Actions flyout */}
        {showActions && (
          <div className="lp-actions-panel" role="menu" onClick={e => e.stopPropagation()}>
            <p className="lp-actions-heading">Actions</p>

            <button className="lp-action-row" role="menuitem"
              onClick={() => showHint("Vision available after agent starts")}>
              <Eye size={13} />
              Screen Vision
            </button>

            <button className="lp-action-row" role="menuitem"
              onClick={() => showHint("Type/Click available after agent starts")}>
              <MousePointer size={13} />
              Type / Click
            </button>

            <button className="lp-action-row" role="menuitem"
              onClick={() => showHint("Automations available after agent starts")}>
              <Zap size={13} />
              Automations
            </button>

            <button className="lp-action-row" role="menuitem" onClick={openSettings}>
              <Settings size={13} />
              Settings
            </button>

            <button className="lp-action-row" role="menuitem" onClick={openConfigFolder}>
              <FolderOpen size={13} />
              Config Folder
            </button>
          </div>
        )}
      </div>

      {/* ── Center card ──────────────────────────────────────────────── */}
      <div className={`lp-card${isLaunching ? " lp-card--launch" : ""}`}>

        <p className="lp-greeting">Hi! I'm Samantha</p>

        {/* Waveform ring */}
        <div className="lp-wave-ring" aria-hidden>
          <canvas ref={canvasRef} width={150} height={60} style={{ display: 'block' }} />
        </div>

        {/* Status hint */}
        {actionStatus && (
          <p className="lp-status-hint">{actionStatus}</p>
        )}

        {/* Launch pill */}
        <button
          className={`lp-launch-btn${isLaunching ? " lp-launch-btn--busy" : ""}`}
          onClick={handleLaunch}
          disabled={isLaunching}
        >
          {isLaunching
            ? <><span className="lp-spinner" /> Launching…</>
            : "launch"}
        </button>
      </div>

      {/* Watermark */}
      <p className="lp-watermark">ZenonAI · Samantha</p>
    </div>
  );
}
