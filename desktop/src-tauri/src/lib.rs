//! lib.rs — Samantha Desktop · Tauri backend
//!
//! Three windows:
//!   "launch"  — 420×300 centered popup (first-run / re-open)
//!   "overlay" — full-height right-edge transparent bar (always-on-top)
//!   "main"    — 920×640 full chat/settings window

use std::sync::{Arc, Mutex};

use tauri::{
    menu::{Menu, MenuItem},
    tray::{MouseButton, MouseButtonState, TrayIconBuilder, TrayIconEvent},
    AppHandle, Emitter, Manager, PhysicalPosition, PhysicalSize, Runtime,
};
use tauri_plugin_shell::ShellExt;

// ── Backend process state ─────────────────────────────────────────────────────

#[derive(Default)]
struct BackendState {
    child: Option<tauri_plugin_shell::process::CommandChild>,
}
type SharedBackend = Arc<Mutex<BackendState>>;

// ── Core helper: snap overlay to right edge of the screen ────────────────────
//
// CRITICAL ORDER: set_size → set_position → set_always_on_top → show → focus
// Positioning BEFORE show() prevents the 1-frame flash at position 0,0.
// Prefer primary_monitor first (most reliable when overlay is hidden/off-screen).

fn snap_overlay_right(app: &AppHandle) {
    let Some(win) = app.get_webview_window("overlay") else {
        eprintln!("[snap] overlay window not found");
        return;
    };

    let overlay_w: u32 = 550;
    // primary_monitor first → current_monitor → first available → hard fallback
    let monitor = win
        .primary_monitor()
        .ok()
        .flatten()
        .or_else(|| win.current_monitor().ok().flatten())
        .or_else(|| {
            win.available_monitors()
                .ok()
                .and_then(|v| v.into_iter().next())
        });

    let (new_x, new_y, screen_h) = match monitor {
        Some(m) => {
            let sw = m.size().width as i32;
            let sh = m.size().height as u32;
            let ox = m.position().x;
            let oy = m.position().y;
            let nx = ox + sw - overlay_w as i32;
            eprintln!(
                "[snap] monitor {}×{} @({},{}) → overlay x={} y={} w={} h={}",
                sw, sh, ox, oy, nx, oy, overlay_w, sh
            );
            (nx, oy, sh)
        }
        None => {
            eprintln!("[snap] WARNING: no monitor found, using fallback");
            (1630, 0, 1080_u32)
        }
    };

    // Position & size BEFORE show (no flash at 0,0)
    let _ = win.set_size(PhysicalSize::new(overlay_w, screen_h));
    let _ = win.set_position(PhysicalPosition::new(new_x, new_y));
    let _ = win.set_always_on_top(true);
    let _ = win.show();
    let _ = win.set_focus();
}

// ── Tauri commands ────────────────────────────────────────────────────────────

/// Called when user clicks "Launch".
/// Shows overlay FIRST (positioned correctly), then hides launch popup.
/// This order prevents any visible gap between the two windows.
#[tauri::command]
fn launch_overlay(app: AppHandle) {
    snap_overlay_right(&app);

    if let Some(w) = app.get_webview_window("launch") {
        let _ = w.hide();
    }
}
/// Called by close button on the launch popup.
#[tauri::command]
fn close_launch(app: AppHandle) {
    if let Some(w) = app.get_webview_window("launch") {
        let _ = w.hide();
    }
}

/// Re-snaps the overlay to the right edge (e.g. after monitor change).
#[tauri::command]
fn reposition_overlay(app: AppHandle) {
    snap_overlay_right(&app);
}

/// Shows or re-snaps the overlay bar.
#[tauri::command]
fn show_overlay(app: AppHandle) {
    if let Some(w) = app.get_webview_window("overlay") {
        if !w.is_visible().unwrap_or(false) {
            snap_overlay_right(&app);
        } else {
            let _ = w.set_focus();
        }
    } else {
        snap_overlay_right(&app);
    }
}

/// Opens / focuses the full main window.
#[tauri::command]
fn show_main_window(app: AppHandle) {
    if let Some(w) = app.get_webview_window("main") {
        let _ = w.show();
        let _ = w.set_focus();
    }
}

/// Opens main window and emits an event to navigate to settings view.
#[tauri::command]
fn open_settings(app: AppHandle) {
    if let Some(w) = app.get_webview_window("main") {
        let _ = w.show();
        let _ = w.set_focus();
    }
    let _ = app.emit("navigate", "settings");
}

/// Start the Python sidecar backend.
#[tauri::command]
async fn start_backend(
    app:          AppHandle,
    state:        tauri::State<'_, SharedBackend>,
    stt_mode:     String,
    ollama_model: String,
    tts_voice:    String,
    tts_engine:   String,
    api_port:     u16,
) -> Result<String, String> {
    let mut s = state.lock().map_err(|e| e.to_string())?;
    if s.child.is_some() {
        return Ok("already running".into());
    }
    let (_, child) = app
        .shell()
        .sidecar("samantha-backend")
        .map_err(|e| format!("sidecar not found: {e}"))?
        .args(["--daemon"])
        .env("STT_MODE",       &stt_mode)
        .env("OLLAMA_MODEL",   &ollama_model)
        .env("TTS_EDGE_VOICE", &tts_voice)
        .env("TTS_ENGINE",     &tts_engine)
        .env("API_PORT",       api_port.to_string())
        .env("API_ENABLED",    "true")
        .spawn()
        .map_err(|e| format!("spawn failed: {e}"))?;
    s.child = Some(child);
    let _ = app.emit("backend-started", ());
    Ok("started".into())
}

/// Stop the sidecar backend.
#[tauri::command]
async fn stop_backend(
    app:   AppHandle,
    state: tauri::State<'_, SharedBackend>,
) -> Result<String, String> {
    let mut s = state.lock().map_err(|e| e.to_string())?;
    if let Some(child) = s.child.take() {
        child.kill().map_err(|e| format!("kill failed: {e}"))?;
        let _ = app.emit("backend-stopped", ());
        return Ok("stopped".into());
    }
    Ok("not running".into())
}

/// Open the app config directory in the OS file manager.
#[tauri::command]
fn open_config_folder(app: AppHandle) -> Result<(), String> {
    let dir = app.path().app_config_dir().map_err(|e| e.to_string())?;
    std::fs::create_dir_all(&dir).ok();
    #[cfg(target_os = "windows")]
    let _ = std::process::Command::new("explorer").arg(&dir).spawn();
    #[cfg(target_os = "macos")]
    let _ = std::process::Command::new("open").arg(&dir).spawn();
    #[cfg(target_os = "linux")]
    let _ = std::process::Command::new("xdg-open").arg(&dir).spawn();
    Ok(())
}

/// Lightweight health check — returns true if backend HTTP port responds.
#[tauri::command]
async fn check_backend_health(port: u16) -> bool {
    let url = format!("http://127.0.0.1:{port}/health");
    reqwest::get(&url)
        .await
        .map(|r| r.status().is_success())
        .unwrap_or(false)
}

#[tauri::command]
fn set_overlay_width(app: AppHandle, width: u32) {
    if let Some(win) = app.get_webview_window("overlay") {
        let monitor = win.primary_monitor().ok().flatten()
            .or_else(|| win.current_monitor().ok().flatten());
        
        let (new_x, screen_h) = match monitor {
            Some(m) => {
                let sw = m.size().width as i32;
                let ox = m.position().x;
                let sh = m.size().height as u32;
                (ox + sw - width as i32, sh)
            }
            None => (1580, 1080),
        };

        let _ = win.set_size(PhysicalSize::new(width, screen_h));
        let _ = win.set_position(PhysicalPosition::new(new_x, 0));
    }
}

// ── System tray ───────────────────────────────────────────────────────────────

fn setup_tray<R: Runtime>(app: &tauri::App<R>) -> tauri::Result<()> {
    let show = MenuItem::with_id(app, "show", "Show Samantha",    true, None::<&str>)?;
    let main = MenuItem::with_id(app, "main", "Open Main Window", true, None::<&str>)?;
    let sep  = tauri::menu::PredefinedMenuItem::separator(app)?;
    let quit = MenuItem::with_id(app, "quit", "Quit Samantha",    true, None::<&str>)?;
    let menu = Menu::with_items(app, &[&show, &main, &sep, &quit])?;

    TrayIconBuilder::new()
        .menu(&menu)
        .icon(app.default_window_icon().unwrap().clone())
        .tooltip("Samantha — ZenonAI")
        .on_tray_icon_event(|tray, event| {
            if let TrayIconEvent::Click {
                button: MouseButton::Left,
                button_state: MouseButtonState::Up, ..
            } = event {
                let app = tray.app_handle();
                if let Some(ov) = app.get_webview_window("overlay") {
                    if ov.is_visible().unwrap_or(false) {
                        let _ = ov.set_focus();
                        return;
                    }
                }
                if let Some(lw) = app.get_webview_window("launch") {
                    let _ = lw.show();
                    let _ = lw.set_focus();
                }
            }
        })
        .on_menu_event(|app, event| match event.id.as_ref() {
            "show" => {
                if let Some(ov) = app.get_webview_window("overlay") {
                    if ov.is_visible().unwrap_or(false) {
                        let _ = ov.set_focus();
                        return;
                    }
                }
                if let Some(lw) = app.get_webview_window("launch") {
                    let _ = lw.show();
                    let _ = lw.set_focus();
                }
            }
            "main" => {
                if let Some(w) = app.get_webview_window("main") {
                    let _ = w.show();
                    let _ = w.set_focus();
                }
            }
            "quit" => app.exit(0),
            _ => {}
        })
        .build(app)?;
    Ok(())
}

// ── App entry point ───────────────────────────────────────────────────────────

#[cfg_attr(mobile, tauri::mobile_entry_point)]
pub fn run() {
    let backend: SharedBackend = Arc::new(Mutex::new(BackendState::default()));

    tauri::Builder::default()
        .plugin(tauri_plugin_shell::init())
        .plugin(tauri_plugin_notification::init())
        .plugin(tauri_plugin_autostart::init(
            tauri_plugin_autostart::MacosLauncher::LaunchAgent,
            Some(vec!["--autostarted"]),
        ))
        .plugin(tauri_plugin_store::Builder::default().build())
        .manage(backend)
        .setup(|app| {
            setup_tray(app)?;
            #[cfg(target_os = "macos")]
            app.set_activation_policy(tauri::ActivationPolicy::Regular);
            Ok(())
        })
        .on_window_event(|window, event| {
            if let tauri::WindowEvent::CloseRequested { api, .. } = event {
                api.prevent_close();
                let _ = window.hide();
            }
        })
        .invoke_handler(tauri::generate_handler![
            launch_overlay,
            close_launch,
            reposition_overlay,
            set_overlay_width,
            show_overlay,
            show_main_window,
            open_settings,
            start_backend,
            stop_backend,
            open_config_folder,
            check_backend_health,
        ])
        .run(tauri::generate_context!())
        .expect("error while running Samantha");
}
