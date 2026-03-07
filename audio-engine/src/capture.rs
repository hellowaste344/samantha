// audio-engine/src/capture.rs  ─  cpal 0.15.3
//
// Mic capture → 20 ms Vec<f32> frames → VAD thread.
//
// ── cpal 0.15.3 API (confirmed by the compiler) ───────────────────────────────
//   Import : use cpal::FromSample;      ← trait must be in scope
//   Method : f32::from_sample(s)        ← no trailing underscore
//
// Three concrete per-format stream builders avoid any generic trait-bound
// ambiguity across cpal patch versions. Each callback calls from_sample()
// on its concrete input type with FromSample imported at the top of the file.

use anyhow::{bail, Context, Result};
use cpal::traits::{DeviceTrait, HostTrait, StreamTrait};
use cpal::{FromSample, SampleFormat, SampleRate, StreamConfig};
use std::sync::{Arc, Mutex};
use tokio::sync::mpsc::Sender;
use tracing::{info, warn};

/// 20 ms @ 16 kHz = 320 samples  (WebRTC VAD hard requirement)
const FRAME_SAMPLES: usize = 320;

pub fn run(target_rate: u32, tx: Sender<Vec<f32>>) -> Result<()> {
    let host   = cpal::default_host();
    let device = host
        .default_input_device()
        .context("No input device found. Connect a microphone.")?;

    info!(device = %device.name().unwrap_or_default(), "Mic opened");

    let supported = device
        .default_input_config()
        .context("Cannot query device config")?;

    info!(
        native_rate     = supported.sample_rate().0,
        native_channels = supported.channels(),
        format          = ?supported.sample_format(),
        target_rate,
        "Audio device info"
    );

    let config = StreamConfig {
        channels:    1,
        sample_rate: SampleRate(target_rate),
        buffer_size: cpal::BufferSize::Default,
    };

    let buf    = Arc::new(Mutex::new(Vec::<f32>::new()));
    let buf_cb = buf.clone();

    let stream = match supported.sample_format() {
        SampleFormat::F32 => build_f32_stream(&device, &config, buf_cb)?,
        SampleFormat::I16 => build_i16_stream(&device, &config, buf_cb)?,
        SampleFormat::U16 => build_u16_stream(&device, &config, buf_cb)?,
        fmt               => bail!("Unsupported sample format: {fmt:?}"),
    };

    stream.play().context("Cannot start audio stream")?;
    info!("Audio capture running at {} Hz mono", target_rate);

    // Drain the accumulator buffer, chunk into FRAME_SAMPLES, forward to VAD.
    // This loop runs on a dedicated OS thread via spawn_blocking in main.rs.
    loop {
        std::thread::sleep(std::time::Duration::from_millis(10));
        let mut guard = buf.lock().unwrap();
        while guard.len() >= FRAME_SAMPLES {
            let frame: Vec<f32> = guard.drain(..FRAME_SAMPLES).collect();
            if tx.blocking_send(frame).is_err() {
                return Ok(()); // VAD thread dropped — clean shutdown
            }
        }
    }
}

// ── Per-format stream builders ────────────────────────────────────────────────
// Separate concrete functions keep the trait bound simple:
//   cpal::FromSample is imported above; from_sample() resolves unambiguously.

fn build_f32_stream(
    device: &cpal::Device,
    config: &StreamConfig,
    buf:    Arc<Mutex<Vec<f32>>>,
) -> Result<cpal::Stream> {
    Ok(device.build_input_stream(
        config,
        move |data: &[f32], _: &cpal::InputCallbackInfo| {
            buf.lock().unwrap().extend_from_slice(data); // f32→f32: direct copy
        },
        move |err| warn!("Audio stream error: {err}"),
        None,
    )?)
}

fn build_i16_stream(
    device: &cpal::Device,
    config: &StreamConfig,
    buf:    Arc<Mutex<Vec<f32>>>,
) -> Result<cpal::Stream> {
    Ok(device.build_input_stream(
        config,
        move |data: &[i16], _: &cpal::InputCallbackInfo| {
            // cpal 0.15.3: trait=cpal::FromSample, method=from_sample (no underscore)
            let samples: Vec<f32> = data.iter().map(|&s| f32::from_sample(s)).collect();
            buf.lock().unwrap().extend_from_slice(&samples);
        },
        move |err| warn!("Audio stream error: {err}"),
        None,
    )?)
}

fn build_u16_stream(
    device: &cpal::Device,
    config: &StreamConfig,
    buf:    Arc<Mutex<Vec<f32>>>,
) -> Result<cpal::Stream> {
    Ok(device.build_input_stream(
        config,
        move |data: &[u16], _: &cpal::InputCallbackInfo| {
            let samples: Vec<f32> = data.iter().map(|&s| f32::from_sample(s)).collect();
            buf.lock().unwrap().extend_from_slice(&samples);
        },
        move |err| warn!("Audio stream error: {err}"),
        None,
    )?)
}
