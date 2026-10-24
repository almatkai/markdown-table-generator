//! Production adapter; compiled unchanged alongside the beta host SDK.
//! Pure generation lives in the path dependency tezbar-markdown-table-generator.
use super::v2_sdk;
use crate::native_core::common::{CoreContext, CoreResult};
use serde_json::Value;
use tezbar_markdown_table_generator::{generate, SUCCESS_MESSAGE, VALIDATION_MESSAGE};

pub fn commands() -> &'static [&'static str] {
    &["generate-markdown-table"]
}

pub async fn handle(
    ctx: &CoreContext,
    command: &str,
    operation: &str,
    payload: &Value,
    _state: &mut Value,
) -> CoreResult {
    if !commands().contains(&command) {
        return Err("Unknown Markdown Table Generator command".into());
    }
    match operation {
        "extension:dispose-session" => return Ok(v2_sdk::unchanged()),
        "extension:run-command" => {}
        _ => return Err("Unsupported Markdown Table Generator operation".into()),
    }
    let args = payload
        .get("argumentValues")
        .and_then(Value::as_object)
        .ok_or(VALIDATION_MESSAGE)?;
    let rows = args
        .get("rows")
        .and_then(Value::as_str)
        .ok_or(VALIDATION_MESSAGE)?;
    let columns = args
        .get("columns")
        .and_then(Value::as_str)
        .ok_or(VALIDATION_MESSAGE)?;
    let table = generate(rows, columns).map_err(|e| e.to_string())?;
    let acknowledgement = v2_sdk::copy(ctx, &table).await?;
    // Beta clipboard:write returns {"ok":true} only after set_text succeeds.
    // Transport Ok containing an error/malformed envelope is not acknowledgement.
    if acknowledgement.get("ok").and_then(Value::as_bool) != Some(true)
        || acknowledgement.get("success").and_then(Value::as_bool) == Some(false)
        || acknowledgement.get("error").is_some_and(|e| !e.is_null())
    {
        return Err(acknowledgement
            .get("error")
            .and_then(Value::as_str)
            .or_else(|| acknowledgement.get("message").and_then(Value::as_str))
            .unwrap_or("Clipboard write was not acknowledged")
            .to_owned());
    }
    Ok(v2_sdk::no_view(SUCCESS_MESSAGE))
}
