// audio-engine/src/vad.rs  —  WebRTC VAD utterance segmentation
//
// ── Why this is a plain blocking fn, not async ───────────────────────────────
// webrtc_vad::Vad wraps a raw C pointer (*mut Fvad) which is !Send.
// tokio::spawn requires the future to be Send; holding Vad across .await
// makes the entire future !Send → compile error E0277.
//
// Solution: plain blocking fn launched via tokio::task::spawn_blocking
// (see main.rs). It uses blocking_recv() / blocking_send() — no .await,
// no Send requirement. Vad lives and dies on a single OS thread.
//
// State machine:
//   IDLE ──(speech detected)──► SPEAKING ──(silence ≥ threshold)──► IDLE
//                                                    └─ emit SpeechEnd

use crate::ipc::AudioEvent;
use anyhow::Result;
use tokio::sync::mpsc::{Receiver, Sender};
use tracing::{debug, info};
use webrtc_vad::{SampleRate, Vad, VadMode};

pub struct VadConfig {
    pub sample_rate:   u32,
    pub level:         u8,   // 0=quality … 3=very_aggressive
    pub silence_ms:    u64,
    pub min_speech_ms: u64,
}

#[derive(PartialEq)]
enum State { Idle, Speaking }

/// Blocking VAD loop.  MUST be called from spawn_blocking, NOT tokio::spawn.
pub fn run(
    mut pcm_rx: Receiver<Vec<f32>>,
    evt_tx:     Sender<AudioEvent>,
    cfg:        VadConfig,
) -> Result<()> {
    let mode = match cfg.level {
        0 => VadMode::Quality,
        1 => VadMode::LowBitrate,
        2 => VadMode::Aggressive,
        _ => VadMode::VeryAggressive,
    };

    let sr = match cfg.sample_rate {
        8000  => SampleRate::Rate8kHz,
        16000 => SampleRate::Rate16kHz,
        32000 => SampleRate::Rate32kHz,
        48000 => SampleRate::Rate48kHz,
        r     => {
            tracing::warn!("VAD: unsupported rate {r}, defaulting to 16 kHz");
            SampleRate::Rate16kHz
        }
    };

    // Vad stays on this thread — !Send is fine here
    let mut vad = Vad::new_with_rate_and_mode(sr, mode);

    let frame_ms       = 20u64; // 320 samples @ 16 kHz = 20 ms
    let silence_frames = cfg.silence_ms    / frame_ms;
    let min_frames     = cfg.min_speech_ms / frame_ms;

    let mut state:         State    = State::Idle;
    let mut silence_count: u64      = 0;
    let mut speech_frames: u64      = 0;
    let mut utterance_buf: Vec<f32> = Vec::with_capacity(16000 * 10);

    info!(vad_level = cfg.level, silence_ms = cfg.silence_ms, "VAD ready");

    // blocking_recv() blocks the OS thread — zero async overhead
    while let Some(frame) = pcm_rx.blocking_recv() {
        let i16_frame: Vec<i16> = frame
            .iter()
            .map(|&s| (s.clamp(-1.0, 1.0) * i16::MAX as f32) as i16)
            .collect();

        let is_speech = vad.is_voice_segment(&i16_frame).unwrap_or(false);
        debug!(is_speech, "VAD frame");

        match state {
            State::Idle => {
                if is_speech {
                    state         = State::Speaking;
                    silence_count = 0;
                    speech_frames = 1;
                    utterance_buf.clear();
                    utterance_buf.extend_from_slice(&frame);
                    let _ = evt_tx.blocking_send(AudioEvent::SpeechStart {
                        sample_rate: cfg.sample_rate,
                    });
                }
            }

            State::Speaking => {
                utterance_buf.extend_from_slice(&frame);
                if is_speech { silence_count  = 0; speech_frames += 1; }
                else         { silence_count += 1; }

                // Flush ~400 ms chunk so Python gets audio while we're still speaking
                let flush_samples = cfg.sample_rate as usize / 1000 * 400;
                if utterance_buf.len() >= flush_samples {
                    let chunk = utterance_buf.clone();
                    utterance_buf.clear();
                    let _ = evt_tx.blocking_send(AudioEvent::AudioChunk { samples: chunk });
                }

                if silence_count >= silence_frames {
                    if speech_frames >= min_frames {
                        // Flush remaining buffer
                        if !utterance_buf.is_empty() {
                            let _ = evt_tx.blocking_send(AudioEvent::AudioChunk {
                                samples: utterance_buf.clone(),
                            });
                        }
                        let duration_ms = speech_frames * frame_ms;
                        let _ = evt_tx.blocking_send(AudioEvent::SpeechEnd { duration_ms });
                        info!(duration_ms, "Utterance complete");
                    } else {
                        debug!(speech_frames, "Utterance too short — discarded");
                    }
                    state         = State::Idle;
                    silence_count = 0;
                    speech_frames = 0;
                    utterance_buf.clear();
                }
            }
        }
    }
    Ok(())
}
