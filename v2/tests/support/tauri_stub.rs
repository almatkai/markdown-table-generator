//! Test-only Tauri surface so byte-exact CoreContext compiles without a GUI.
//! Tests only construct CoreContext::headless; emitting through a real handle
//! is deliberately unsupported. This is not an OS or full-host integration test.
#[derive(Clone)]
pub struct AppHandle;
pub trait Emitter {
    fn emit(&self, channel: &str, payload: serde_json::Value) -> Result<(), &'static str>;
}
impl Emitter for AppHandle {
    fn emit(&self, _: &str, _: serde_json::Value) -> Result<(), &'static str> {
        panic!("headless tests must never emit through Tauri")
    }
}
