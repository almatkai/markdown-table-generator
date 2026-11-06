//! Standalone protocol adapter. The original pure v2 engine stays unchanged.
use serde_json::{json, Value};
use tezbar_extension_sdk::{BoxFuture, CoreResult, Extension, ExtensionContext};
use tezbar_markdown_table_generator::{generate, SUCCESS_MESSAGE, VALIDATION_MESSAGE};

struct MarkdownTable;

fn failure(message: &str) -> Value {
    // Domain failures still open a session: the host immediately disposes all
    // no-view results, including failures. Err would remove the SDK session first.
    json!({"ok": false, "mode": "no-view", "message": message})
}

impl Extension for MarkdownTable {
    fn id(&self) -> &'static str {
        "com.tezbar.native.markdown-table-generator"
    }
    fn version(&self) -> &'static str {
        env!("CARGO_PKG_VERSION")
    }
    fn commands(&self) -> &'static [&'static str] {
        &["generate-markdown-table"]
    }
    fn handle<'a>(
        &'a self,
        ctx: &'a ExtensionContext,
        command: &'a str,
        operation: &'a str,
        payload: &'a Value,
        _state: &'a mut Value,
    ) -> BoxFuture<'a, CoreResult> {
        Box::pin(async move {
            if !self.commands().contains(&command) {
                return Err("Unknown Markdown Table Generator command".into());
            }
            match operation {
                "extension:dispose-session" => return Ok(tezbar_extension_sdk::unchanged()),
                "extension:run-command" => {}
                _ => return Err("Unsupported Markdown Table Generator operation".into()),
            }
            let arguments = &payload["argumentValues"];
            let (Some(rows), Some(columns)) =
                (arguments["rows"].as_str(), arguments["columns"].as_str())
            else {
                return Ok(failure(VALIDATION_MESSAGE));
            };
            let table = match generate(rows, columns) {
                Ok(table) => table,
                Err(error) => return Ok(failure(&error.to_string())),
            };
            // The only granted service. Never copy supplied action/payload text.
            // SDK owns cancellation, operation serialization and staged state.
            let acknowledgement = match ctx
                .host("host.clipboard.write", json!({"text": table}))
                .await
            {
                Ok(value) => value,
                Err(error) => return Ok(failure(&error)),
            };
            // Actual native clipboard shape is {ok:true}, after set_text succeeds.
            if acknowledgement.get("ok").and_then(Value::as_bool) != Some(true)
                || acknowledgement.get("success").and_then(Value::as_bool) == Some(false)
                || acknowledgement.get("error").is_some_and(|e| !e.is_null())
            {
                let message = acknowledgement
                    .get("error")
                    .and_then(Value::as_str)
                    .or_else(|| acknowledgement.get("message").and_then(Value::as_str))
                    .filter(|message| !message.trim().is_empty())
                    .unwrap_or("Clipboard write was not acknowledged");
                return Ok(failure(message));
            }
            // Single feedback channel: no notification RPC or initial effects.
            Ok(tezbar_extension_sdk::no_view(SUCCESS_MESSAGE))
        })
    }
}

fn main() {
    let runtime = tokio::runtime::Builder::new_multi_thread()
        .worker_threads(2)
        .enable_all()
        .build()
        .expect("extension runtime");
    let result = runtime.block_on(tezbar_extension_sdk::serve(MarkdownTable));
    runtime.shutdown_timeout(std::time::Duration::from_millis(500));
    if let Err(error) = result {
        eprintln!("{error}");
        std::process::exit(1);
    }
}
