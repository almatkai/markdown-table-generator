//! Pure, bounded port of Visual-Studio-Coder's MIT Markdown Table Generator.
use std::fmt::{self, Write};

pub const MAX_OUTPUT_BYTES: u64 = 8 * 1024 * 1024;
pub const VALIDATION_MESSAGE: &str =
    "Please enter an integer value greater than zero for both rows and columns.";
pub const SUCCESS_MESSAGE: &str = "Markdown table copied to clipboard!";
pub const SIZE_MESSAGE: &str = "Markdown table exceeds the 8 MiB output limit.";

#[derive(Clone, Copy, Debug, Eq, PartialEq)]
pub enum Error {
    InvalidArguments,
    OutputTooLarge,
    AllocationFailed,
}
impl fmt::Display for Error {
    fn fmt(&self, f: &mut fmt::Formatter<'_>) -> fmt::Result {
        f.write_str(match self {
            Self::InvalidArguments => VALIDATION_MESSAGE,
            Self::OutputTooLarge => SIZE_MESSAGE,
            Self::AllocationFailed => "Could not allocate the markdown table.",
        })
    }
}
impl std::error::Error for Error {}

// ECMAScript WhiteSpace + LineTerminator, deliberately not Rust's is_whitespace
// (which also includes U+0085 and excludes the JavaScript BOM whitespace).
fn js_whitespace(c: char) -> bool {
    matches!(c, '\u{0009}'..='\u{000d}' | '\u{0020}' | '\u{00a0}' | '\u{1680}'
        | '\u{2000}'..='\u{200a}' | '\u{2028}' | '\u{2029}' | '\u{202f}'
        | '\u{205f}' | '\u{3000}' | '\u{feff}')
}

fn parse_dimension(text: &str) -> Result<f64, Error> {
    let text = text.trim_start_matches(js_whitespace);
    let (negative, text) = match text.as_bytes().first() {
        Some(b'-') => (true, &text[1..]),
        Some(b'+') => (false, &text[1..]),
        _ => (false, text),
    };
    let end = text.bytes().take_while(u8::is_ascii_digit).count();
    if end == 0 || negative {
        return Err(Error::InvalidArguments);
    }
    // Radix 10 digit prefix only: 1.9 -> 1, 1e9 -> 1, 0x10 -> 0.
    // Binary64 is needed to distinguish finite huge integers from Infinity.
    // All output-sized integers are exact; finite larger rounded values are
    // rejected by checked sizing before generation, so their exact rounding
    // cannot change generated text. No per-digit big-integer dependency.
    let number: f64 = text[..end].parse().map_err(|_| Error::InvalidArguments)?;
    if !number.is_finite() || number <= 0.0 || number.fract() != 0.0 {
        return Err(Error::InvalidArguments);
    }
    Ok(number)
}

fn digit_sum(n: u64) -> Option<u64> {
    let mut total = n;
    let mut power = 10u64;
    while power <= n {
        total = total.checked_add(n - (power - 1))?;
        let Some(next) = power.checked_mul(10) else {
            break;
        };
        power = next;
    }
    Some(total)
}

/// Exact UTF-8 output size without generating cells; O(log(rows) + log(columns)).
/// Every arithmetic operation is checked, including asymmetric/overflow inputs.
pub fn output_size(rows: u64, columns: u64) -> Result<u64, Error> {
    if rows == 0 || columns == 0 {
        return Err(Error::InvalidArguments);
    }
    let calculate = || -> Option<u64> {
        let dr = digit_sum(rows)?;
        let dc = digit_sum(columns)?;
        4u64.checked_add(16u64.checked_mul(columns)?)?
            .checked_add(dc)?
            .checked_add(2u64.checked_mul(rows)?)?
            .checked_add(9u64.checked_mul(rows)?.checked_mul(columns)?)?
            .checked_add(columns.checked_mul(dr)?)?
            .checked_add(rows.checked_mul(dc)?)
    };
    calculate()
        .filter(|&n| n <= MAX_OUTPUT_BYTES)
        .ok_or(Error::OutputTooLarge)
}

/// Accepts text arguments in upstream rows/columns order. Returns trailing LF.
pub fn generate(rows: &str, columns: &str) -> Result<String, Error> {
    // Validate both before any resource error (matching upstream invalid inputs).
    let rows = parse_dimension(rows);
    let columns = parse_dimension(columns);
    let (rows, columns) = (rows?, columns?);
    // Values outside u64 cannot possibly fit the byte limit; avoid saturating casts.
    if rows >= u64::MAX as f64 || columns >= u64::MAX as f64 {
        return Err(Error::OutputTooLarge);
    }
    let (rows, columns) = (rows as u64, columns as u64);
    let size = output_size(rows, columns)?;
    let mut table = String::new();
    table
        .try_reserve_exact(size as usize)
        .map_err(|_| Error::AllocationFailed)?;
    table.push('|');
    for col in 1..=columns {
        write!(table, " Column {col} |").expect("writing to String cannot fail");
    }
    table.push_str("\n|");
    for _ in 1..=columns {
        table.push_str(" --- |");
    }
    table.push('\n');
    for row in 1..=rows {
        table.push('|');
        for col in 1..=columns {
            write!(table, " Cell {row}-{col} |").expect("writing to String cannot fail");
        }
        table.push('\n');
    }
    debug_assert_eq!(table.len() as u64, size);
    Ok(table)
}
