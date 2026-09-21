//! Pointer, string and error plumbing shared by every entry point.

use std::ffi::{c_char, CStr, CString};

use crate::TS_INVALID_ARGUMENT;

/// ABI version checked by Treescape.jl at load time.
pub const ABI_VERSION: u32 = 1;

#[no_mangle]
pub extern "C" fn ts_abi_version() -> u32 {
    ABI_VERSION
}

/// Release a string returned by any `ts_*` call. Null is a no-op.
#[no_mangle]
pub extern "C" fn ts_string_free(s: *mut c_char) {
    if !s.is_null() {
        // SAFETY: `s` came from `CString::into_raw` in this crate.
        drop(unsafe { CString::from_raw(s) });
    }
}

/// A failed call: status code plus message.
pub struct Failure {
    pub code: i32,
    pub message: String,
}

impl Failure {
    pub fn new(code: i32, message: impl Into<String>) -> Self {
        Self {
            code,
            message: message.into(),
        }
    }

    pub fn invalid(message: impl Into<String>) -> Self {
        Self::new(TS_INVALID_ARGUMENT, message)
    }
}

pub type FfiResult<T> = Result<T, Failure>;

/// Owned C string; interior NULs (impossible in our messages and SVG,
/// but not in user tip names) are replaced so this cannot fail.
pub fn to_c_string(s: &str) -> *mut c_char {
    let cleaned: String = s
        .chars()
        .map(|c| if c == '\0' { '\u{fffd}' } else { c })
        .collect();
    match CString::new(cleaned) {
        Ok(c) => c.into_raw(),
        Err(_) => std::ptr::null_mut(),
    }
}

/// Convert a result into a status code, writing the message to `err`.
pub fn finish(result: FfiResult<()>, err: *mut *mut c_char) -> i32 {
    match result {
        Ok(()) => crate::TS_OK,
        Err(f) => {
            if !err.is_null() {
                // SAFETY: caller passes a valid `char **` or null.
                unsafe { *err = to_c_string(&f.message) };
            }
            f.code
        }
    }
}

/// Borrow a NUL-terminated UTF-8 string argument.
pub fn str_arg<'a>(p: *const c_char, what: &str) -> FfiResult<&'a str> {
    if p.is_null() {
        return Err(Failure::invalid(format!("{what} is a null pointer")));
    }
    // SAFETY: non-null, NUL-terminated per the ABI contract.
    unsafe { CStr::from_ptr(p) }
        .to_str()
        .map_err(|_| Failure::invalid(format!("{what} is not valid UTF-8")))
}

/// The checks `slice::from_raw_parts` needs that a caller can get wrong
/// without the pointer being dangling: non-null, aligned for `T`, and a
/// total size within `isize::MAX` bytes.
fn check_ptr<T>(p: *const T, len: usize, what: &str) -> FfiResult<()> {
    if p.is_null() {
        return Err(Failure::invalid(format!("{what} is a null pointer")));
    }
    if !p.is_aligned() {
        return Err(Failure::invalid(format!("{what} is misaligned")));
    }
    match len.checked_mul(std::mem::size_of::<T>()) {
        Some(bytes) if bytes <= isize::MAX as usize => Ok(()),
        _ => Err(Failure::invalid(format!(
            "{what} length {len} is too large"
        ))),
    }
}

/// Borrow `len` elements; null is allowed only when `len == 0`.
pub fn slice_arg<'a, T>(p: *const T, len: usize, what: &str) -> FfiResult<&'a [T]> {
    if len == 0 {
        return Ok(&[]);
    }
    check_ptr(p, len, what)?;
    // SAFETY: non-null, aligned, size-checked, and `len` initialized
    // elements per the ABI contract.
    Ok(unsafe { std::slice::from_raw_parts(p, len) })
}

/// Mutable output buffer of exactly `len` elements.
pub fn out_slice<'a, T>(p: *mut T, len: usize, what: &str) -> FfiResult<&'a mut [T]> {
    if len == 0 {
        return Ok(&mut []);
    }
    check_ptr(p, len, what)?;
    // SAFETY: non-null, aligned, size-checked, and writable for `len`
    // elements per the ABI contract.
    Ok(unsafe { std::slice::from_raw_parts_mut(p, len) })
}

/// Write a scalar through an out-pointer.
pub fn write_out<T>(p: *mut T, value: T, what: &str) -> FfiResult<()> {
    check_ptr(p, 1, what)?;
    // SAFETY: non-null, aligned and writable per the ABI contract.
    unsafe { p.write(value) };
    Ok(())
}

/// Borrow a handle.
pub fn handle<'a, T>(p: *const T, what: &str) -> FfiResult<&'a T> {
    check_ptr(p, 1, what)?;
    // SAFETY: non-null and aligned; the ABI contract is that non-null
    // handles came from this crate and have not been freed.
    Ok(unsafe { &*p })
}

/// Mutably borrow a handle.
pub fn handle_mut<'a, T>(p: *mut T, what: &str) -> FfiResult<&'a mut T> {
    check_ptr(p, 1, what)?;
    // SAFETY: as for `handle`.
    Ok(unsafe { &mut *p })
}

/// Zip `(values, present)` into a tip-order-aligned optional column.
pub fn column<T: Copy>(
    values: *const T,
    present: *const u8,
    len: usize,
) -> FfiResult<Vec<Option<T>>> {
    let values = slice_arg(values, len, "values")?;
    let present = slice_arg(present, len, "present")?;
    Ok(values
        .iter()
        .zip(present)
        .map(|(&v, &p)| (p != 0).then_some(v))
        .collect())
}
