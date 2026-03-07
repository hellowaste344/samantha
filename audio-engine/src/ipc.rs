// audio-engine/src/ipc.rs
//
// Unix domain socket server.
// Python agent connects as a client and receives newline-delimited JSON events.
//
// Protocol messages (each terminated by '\n'):
//   {"type":"speech_start","sample_rate":16000}
//   {"type":"audio_chunk","data":"<base64 f32-le samples>","n_samples":6400}
//   {"type":"speech_end","duration_ms":1250}
//   {"type":"ping"}   — keepalive every 5 s

use anyhow::Result;
use base64::{engine::general_purpose::STANDARD as B64, Engine};
use serde::Serialize;
use std::path::PathBuf;
use tokio::io::AsyncWriteExt;
use tokio::net::{UnixListener, UnixStream};
use tokio::sync::mpsc::Receiver;
use tokio::time::{interval, Duration};
use tracing::{info, warn};

/// Events produced by the VAD pipeline
#[derive(Debug, Clone)]
pub enum AudioEvent {
    SpeechStart { sample_rate: u32 },
    AudioChunk  { samples: Vec<f32> },
    SpeechEnd   { duration_ms: u64 },
}

// ── Wire types (serialised to JSON) ──────────────────────────────────────────

#[derive(Serialize)]
#[serde(tag = "type", rename_all = "snake_case")]
enum WireMsg<'a> {
    SpeechStart { sample_rate: u32 },
    AudioChunk  { data: &'a str, n_samples: usize },
    SpeechEnd   { duration_ms: u64 },
    Ping,
}

/// Run the Unix socket server.
/// Accepts one client at a time (the Python agent).
/// If the client disconnects, waits for a new connection.
pub async fn run_server(socket_path: PathBuf, mut rx: Receiver<AudioEvent>) -> Result<()> {
    // Remove stale socket file
    let _ = std::fs::remove_file(&socket_path);

    let listener = UnixListener::bind(&socket_path)?;
    info!(path = %socket_path.display(), "IPC socket listening");

    // Drain events while no client is connected (avoid backpressure)
    loop {
        info!("Waiting for Python agent to connect…");
        let (stream, _) = listener.accept().await?;
        info!("Python agent connected");

        if let Err(e) = handle_client(stream, &mut rx).await {
            warn!("Client disconnected: {e}");
        }
    }
}

async fn handle_client(mut stream: UnixStream, rx: &mut Receiver<AudioEvent>) -> Result<()> {
    let mut ping_ticker = interval(Duration::from_secs(5));

    loop {
        tokio::select! {
            // Periodic keepalive
            _ = ping_ticker.tick() => {
                let msg = serde_json::to_string(&WireMsg::Ping)? + "\n";
                stream.write_all(msg.as_bytes()).await?;
            }

            // Audio events
            evt = rx.recv() => {
                let Some(evt) = evt else { break };

                let line = match &evt {
                    AudioEvent::SpeechStart { sample_rate } => {
                        serde_json::to_string(&WireMsg::SpeechStart {
                            sample_rate: *sample_rate,
                        })?
                    }

                    AudioEvent::AudioChunk { samples } => {
                        // Encode f32-LE samples as base64
                        let bytes: Vec<u8> = samples
                            .iter()
                            .flat_map(|s| s.to_le_bytes())
                            .collect();
                        let encoded = B64.encode(&bytes);
                        serde_json::to_string(&WireMsg::AudioChunk {
                            data:     &encoded,
                            n_samples: samples.len(),
                        })?
                    }

                    AudioEvent::SpeechEnd { duration_ms } => {
                        serde_json::to_string(&WireMsg::SpeechEnd {
                            duration_ms: *duration_ms,
                        })?
                    }
                };

                stream.write_all((line + "\n").as_bytes()).await?;
            }
        }
    }

    Ok(())
}
