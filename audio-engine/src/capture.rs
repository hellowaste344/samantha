// audio-engine/src/capture.rs  —  cpal mic capture → 20 ms f32 frames
//
// Conversion uses plain arithmetic instead of cpal sample-conversion traits,
// which changed API between cpal minor versions and caused build failures.
//   i16 → f32:  s / i16::MAX          range [-1.0, 1.0]
//   u16 → f32:  (s / u16::MAX)*2 - 1  range [-1.0, 1.0]
//   f32 → f32:  direct copy

use anyhow::{bail, Context, Result};
use cpal::traits::{DeviceTrait, HostTrait, StreamTrait};
use cpal::{SampleFormat, SampleRate, StreamConfig};
use std::sync::{Arc, Mutex};
use tokio::sync::mpsc::Sender;
use tracing::{info, warn};

#[inline]
fn i16_to_f32(s: i16) -> f32 { s as f32 / i16::MAX as f32 }
#[inline]
fn u16_to_f32(s: u16) -> f32 { (s as f32 / u16::MAX as f32) * 2.0 - 1.0 }

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

fn build_f32_stream(
    device: &cpal::Device,
    config: &StreamConfig,
    buf:    Arc<Mutex<Vec<f32>>>,
) -> Result<cpal::Stream> {
    Ok(device.build_input_stream(
        config,
        move |data: &[f32], _: &cpal::InputCallbackInfo| {
            buf.lock().unwrap().extend_from_slice(data);
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
            let samples: Vec<f32> = data.iter().map(|&s| i16_to_f32(s)).collect();
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
            let samples: Vec<f32> = data.iter().map(|&s| u16_to_f32(s)).collect();
            buf.lock().unwrap().extend_from_slice(&samples);
        },
        move |err| warn!("Audio stream error: {err}"),
        None,
    )?)
}
