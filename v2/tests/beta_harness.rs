//! Production adapter + byte-exact beta common.rs/v2_sdk.rs, headless only.
extern crate self as tauri;
#[path = "support/tauri_stub.rs"]
mod tauri_stub;
pub use tauri_stub::{AppHandle, Emitter};
mod native_core;
use native_core::common::{CoreContext, CorePaths, CoreResult};
use native_core::extensions::v2_markdown_table_generator::{commands, handle};
use serde_json::{json, Value};
use std::sync::{Arc, Mutex};
use tezbar_markdown_table_generator::{SUCCESS_MESSAGE, VALIDATION_MESSAGE};

type Calls = Arc<Mutex<Vec<(String, Vec<Value>)>>>;
fn fixture(reply: CoreResult) -> (tempfile::TempDir, CoreContext, Calls) {
    let dir = tempfile::tempdir().unwrap();
    let ctx = CoreContext::headless(CorePaths {
        data_dir: dir.path().join("data"),
        config_dir: dir.path().join("config"),
        resource_dir: dir.path().join("resources"),
        temp_dir: dir.path().join("tmp"),
        home_dir: dir.path().join("home"),
    })
    .with_event_sink(Arc::new(|_, _| panic!("no UI events allowed")));
    let calls: Calls = Arc::default();
    let record = calls.clone();
    ctx.set_router(Arc::new(move |channel, args| {
        assert_eq!(channel, "clipboard:write", "no other effect is permitted");
        record.lock().unwrap().push((channel, args));
        let reply = reply.clone();
        Box::pin(async move { reply })
    }))
    .unwrap();
    (dir, ctx, calls)
}
fn payload() -> Value {
    json!({"argumentValues":{"rows":"1.9junk","columns":"+2e9"},"text":"NEVER COPY THIS","clipboard":"NEVER COPY THIS"})
}
const COMMAND: &str = "generate-markdown-table";
const RUN: &str = "extension:run-command";

#[tokio::test]
async fn actual_argument_values_one_copy_per_invocation_and_no_state() {
    assert_eq!(commands(), &[COMMAND]);
    let (dir, ctx, calls) = fixture(Ok(json!({"ok":true})));
    let mut state = json!({"unrelated":"preserve"});
    for _ in 0..2 {
        assert_eq!(
            handle(&ctx, COMMAND, RUN, &payload(), &mut state)
                .await
                .unwrap(),
            json!({"ok":true,"mode":"no-view","message":SUCCESS_MESSAGE})
        );
    }
    let calls = calls.lock().unwrap();
    assert_eq!(calls.len(), 2);
    for (channel, args) in calls.iter() {
        assert_eq!(channel, "clipboard:write");
        assert_eq!(
            args,
            &vec![json!(
                "| Column 1 | Column 2 |\n| --- | --- |\n| Cell 1-1 | Cell 1-2 |\n"
            )]
        );
    }
    assert_eq!(state, json!({"unrelated":"preserve"}));
    assert_eq!(std::fs::read_dir(dir.path()).unwrap().count(), 0);
}

#[tokio::test]
async fn invalid_payloads_commands_operations_and_disposal_have_no_effects() {
    let (_dir, ctx, calls) = fixture(Ok(json!({"ok":true})));
    let mut state = json!(null);
    for payload in [
        json!(null),
        json!([]),
        json!({}),
        json!({"arguments":{"rows":"1","columns":"1"}}),
        json!({"argumentValues":null}),
        json!({"argumentValues":[]}),
        json!({"argumentValues":{}}),
        json!({"argumentValues":{"rows":"1"}}),
        json!({"argumentValues":{"columns":"1"}}),
        json!({"argumentValues":{"rows":1,"columns":"1"}}),
        json!({"argumentValues":{"rows":"1","columns":true}}),
        json!({"argumentValues":{"rows":"","columns":"1"},"text":"arbitrary"}),
        json!({"argumentValues":{"rows":"0x10","columns":"1"}}),
        json!({"argumentValues":{"rows":"-2","columns":"1"}}),
    ] {
        assert_eq!(
            handle(&ctx, COMMAND, RUN, &payload, &mut state)
                .await
                .unwrap_err(),
            VALIDATION_MESSAGE
        );
    }
    for operation in [
        "",
        "clipboard:write",
        "extension:invoke-action",
        "extension:refresh-session",
        "extension:search-text-changed",
    ] {
        assert!(handle(&ctx, COMMAND, operation, &payload(), &mut state)
            .await
            .is_err());
    }
    for command in ["", "other-command"] {
        for operation in [RUN, "extension:dispose-session"] {
            assert!(handle(&ctx, command, operation, &payload(), &mut state)
                .await
                .is_err());
        }
    }
    assert_eq!(
        handle(
            &ctx,
            COMMAND,
            "extension:dispose-session",
            &json!({}),
            &mut state
        )
        .await
        .unwrap(),
        json!({"ok":true,"mode":"unchanged"})
    );
    assert!(handle(
        &ctx,
        COMMAND,
        RUN,
        &json!({"argumentValues":{"rows":"9007199254740993","columns":"1"}}),
        &mut state
    )
    .await
    .is_err());
    assert!(calls.lock().unwrap().is_empty());
    assert_eq!(state, Value::Null);
}

#[tokio::test]
async fn transport_and_error_envelopes_never_report_success() {
    for (reply, expected) in [
        (Err("transport failed".into()), "transport failed"),
        (
            Ok(json!({"ok":true,"error":"clipboard denied"})),
            "clipboard denied",
        ),
        (
            Ok(json!({"ok":true,"success":false,"message":"clipboard unavailable"})),
            "clipboard unavailable",
        ),
        (
            Ok(json!({"ok":true,"error":{"message":"denied"}})),
            "Clipboard write was not acknowledged",
        ),
        (
            Ok(json!({"ok":false,"message":"clipboard unavailable"})),
            "clipboard unavailable",
        ),
        (
            Ok(json!({"ok":false})),
            "Clipboard write was not acknowledged",
        ),
        (Ok(json!({})), "Clipboard write was not acknowledged"),
        (Ok(json!(true)), "Clipboard write was not acknowledged"),
        (Ok(json!(null)), "Clipboard write was not acknowledged"),
        (
            Ok(json!({"ok":"true"})),
            "Clipboard write was not acknowledged",
        ),
    ] {
        let (_dir, ctx, calls) = fixture(reply);
        assert_eq!(
            handle(&ctx, COMMAND, RUN, &payload(), &mut json!({}))
                .await
                .unwrap_err(),
            expected
        );
        assert_eq!(calls.lock().unwrap().len(), 1);
    }
}

#[tokio::test]
async fn completion_waits_for_clipboard_acknowledgement() {
    let (_dir, ctx, _calls) = fixture(Ok(json!({"ok":true})));
    // New context because the real CoreContext correctly forbids replacing routers.
    let ctx = CoreContext::headless(ctx.paths.clone());
    let entered = Arc::new(tokio::sync::Notify::new());
    let release = Arc::new(tokio::sync::Notify::new());
    let (entry, gate) = (entered.clone(), release.clone());
    ctx.set_router(Arc::new(move |channel, _| {
        assert_eq!(channel, "clipboard:write");
        let (entry, gate) = (entry.clone(), gate.clone());
        Box::pin(async move {
            entry.notify_one();
            gate.notified().await;
            Ok(json!({"ok":true}))
        })
    }))
    .unwrap();
    let task =
        tokio::spawn(async move { handle(&ctx, COMMAND, RUN, &payload(), &mut json!({})).await });
    entered.notified().await;
    assert!(
        !task.is_finished(),
        "success must not precede acknowledgement"
    );
    release.notify_one();
    assert_eq!(task.await.unwrap().unwrap()["message"], SUCCESS_MESSAGE);
}
