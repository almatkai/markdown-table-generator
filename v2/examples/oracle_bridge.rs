//! JSON-lines test bridge; no OS actions and no production dependencies.
use serde_json::{json, Value};
use std::io::{self, BufRead};
fn main() {
    for line in io::stdin().lock().lines() {
        let value: Value = serde_json::from_str(&line.unwrap()).unwrap();
        let result = tezbar_markdown_table_generator::generate(
            value["rows"].as_str().unwrap(),
            value["columns"].as_str().unwrap(),
        );
        println!(
            "{}",
            match result {
                Ok(table) => json!({"table":table}),
                Err(error) => json!({"error":error.to_string()}),
            }
        );
    }
}
