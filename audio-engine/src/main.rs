// audio-engine/src/main.rs  —  Samantha Audio Daemon
//
// Spawns three concurrent workers:
//
//   1. capture::run   (blocking thread)
//      cpal ALSA/WASAPI/CoreAudio mic capture → pcm_tx channel
//
//   2. vad::run       (blocking thread  ←  MUST NOT use tokio::spawn)
//      webrtc_vad::Vad wraps *mut Fvad (raw C pointer) → !Send.
//      tokio::spawn requires Send. Holding Vad across .await = compile error.
//      Fix: spawn_blocking → dedicated OS thread → blocking_recv/send, no .await.
//
//   3. ipc::run_server (async task)
//      Unix socket server → sends AudioEvents as newline-delimited JSON
//      to the Python agent.
//
// Speed tuning vs previous defaults:
//   silence_ms   800 → 600  — cuts end-of-speech dead-time by 200 ms.
//   min_speech_ms 300 → 200  — discards noise bursts faster.

mod capture;
mod ipc;
mod vad;

use anyhow::Result;
use clap::Parser;
use std::path::PathBuf;
use tokio::sync::mpsc;
use tracing::{error, info};
use tracing_subscriber::EnvFilter;

#[derive(Parser, Debug)]
#[command(name = "samantha-audio", version)]
struct Args {
    #[arg(long, default_value = "/tmp/samantha_audio.sock")]
    socket: PathBuf,

    #[arg(long, default_value_t = 16000)]
    sample_rate: u32,

    /// 0 = least aggressive  …  3 = most aggressive noise rejection
    #[arg(long, default_value_t = 2)]
    vad_level: u8,

    /// Milliseconds of consecutive silence that ends an utterance (lower = faster response)
    #[arg(long, default_value_t = 600)]
    silence_ms: u64,

    /// Minimum speech length to accept; shorter bursts are discarded as noise
    #[arg(long, default_value_t = 200)]
    min_speech_ms: u64,
}

#[tokio::main]
async fn main() -> Result<()> {
    tracing_subscriber::fmt()
        .with_env_filter(
            EnvFilter::try_from_env("RUST_LOG")
                .unwrap_or_else(|_| EnvFilter::new("samantha_audio=info")),
        )
        .init();

    let args = Args::parse();
    info!(
        socket  = %args.socket.display(),
        rate    = args.sample_rate,
        silence_ms = args.silence_ms,
        min_speech_ms = args.min_speech_ms,
        "Samantha Audio Engine starting"
    );

    let (pcm_tx, pcm_rx) = mpsc::channel::<Vec<f32>>(256);
    let (evt_tx, evt_rx) = mpsc::channel::<ipc::AudioEvent>(32);

    // 1. Mic capture — blocking thread (cpal callback-driven)
    let sr       = args.sample_rate;
    let pcm_tx_c = pcm_tx.clone();
    tokio::task::spawn_blocking(move || {
        if let Err(e) = capture::run(sr, pcm_tx_c) {
            error!("Capture exited: {e}");
        }
    });

    // 2. VAD — spawn_blocking because Vad is !Send (raw C pointer)
    //    Do NOT change this to tokio::spawn — it will not compile.
    let vad_cfg = vad::VadConfig {
        sample_rate:   args.sample_rate,
        level:         args.vad_level,
        silence_ms:    args.silence_ms,
        min_speech_ms: args.min_speech_ms,
    };
    tokio::task::spawn_blocking(move || {
        if let Err(e) = vad::run(pcm_rx, evt_tx, vad_cfg) {
            error!("VAD exited: {e}");
        }
    });

    // 3. IPC server — async, waits for Python agent to connect
    ipc::run_server(args.socket, evt_rx).await?;
    Ok(())
}
