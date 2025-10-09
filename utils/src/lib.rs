use regex::Regex;
use reqwest::Result;
use serde::{Deserialize, Serialize};
use std::env;
use std::ptr::null;
use std::ptr::null_mut;
use libc::c_char;
use std::ffi::{CStr,CString};

// Should be moved to a standalone wrapper library such as
// https://github.com/nixops4/nixops4/tree/main/rust/nix-util
// when we do that we should also make other improvements such
// as considering to use rust-bindgen etc, for now keep things
// as simple as possible
pub type err = ::std::os::raw::c_int;
#[repr(C)]
#[derive(Debug, Copy, Clone)]
pub struct c_context {
    _unused: [u8; 0],
}
#[repr(C)]
#[derive(Debug, Copy, Clone)]
pub struct Store {
    _unused: [u8; 0],
}
#[repr(C)]
#[derive(Debug, Copy, Clone)]
pub struct StorePath {
    _unused: [u8; 0],
}
#[link(name = "nixstorec")]
extern {
    fn nix_c_context_create() -> *mut c_context;
    fn nix_c_context_free() -> *mut c_context;

    fn nix_libstore_init(context: *mut c_context) -> err;
    fn nix_store_open(
        context: *mut c_context,
        uri: *const ::std::os::raw::c_char,
        params: *mut *mut *const ::std::os::raw::c_char,
    ) -> *mut Store;
    fn nix_store_parse_path(
        context: *mut c_context,
        store: *mut Store,
        path: *const c_char,
    ) -> *mut StorePath;
    fn nix_store_path_free(p: *mut StorePath);
    fn nix_store_free(store: *mut Store);
    fn nix_store_path_nar_hash(store: *mut Store, store_path: *const StorePath) -> *mut c_char;
    fn nix_store_path_nar_size(store: *mut Store, store_path: *const StorePath) -> u64;
    fn nix_store_path_references(store: *mut Store, store_path: *const StorePath) -> *mut *mut c_char;
}
#[link(name = "nixutilc")]
extern {
    fn hash_path(input: *const c_char) -> *mut c_char;
    fn sign_detached(secret_key: *const c_char, data: *const c_char) -> *mut c_char;
}

#[derive(Debug, Copy, Clone)]
pub struct Ctx {
    context: *mut c_context,
    store: *mut Store
}
pub fn nix_init() -> Ctx {
    unsafe {
        let ctx = nix_c_context_create();
        nix_libstore_init(ctx);
        let store = nix_store_open(ctx, null(), null_mut());
        return Ctx { context: ctx, store: store };
    }
}
pub fn nar_hash(ctx: Ctx, path: String) -> String {
    unsafe {
        let cpath = CString::new(path).unwrap();
        let path = nix_store_parse_path(ctx.context, ctx.store, cpath.as_ptr());
        let hash = CStr::from_ptr(nix_store_path_nar_hash(ctx.store, path));
        let res = String::from_utf8_lossy(hash.to_bytes()).to_string();
        nix_store_path_free(path);
        return res;
    }
}
pub fn nar_size(ctx: Ctx, path: String) -> u64 {
    unsafe {
        let cpath = CString::new(path).unwrap();
        let path = nix_store_parse_path(ctx.context, ctx.store, cpath.as_ptr());
        let res = nix_store_path_nar_size(ctx.store, path);
        nix_store_path_free(path);
        return res;
    }
}

fn query_references(ctx: Ctx, path: &str) -> Vec<String> {
    unsafe {
        let cpath = CString::new(path).unwrap();
        let path = nix_store_parse_path(ctx.context, ctx.store, cpath.as_ptr());
        let c_strs = nix_store_path_references(ctx.store, path);
        nix_store_path_free(path);

        let mut result = Vec::new();
        if c_strs.is_null() {
            return result;
        }

        let mut i = 0;
        loop {
            let c_str = *c_strs.add(i);
            if c_str.is_null() {
                break;
            }

            let ref_path = CStr::from_ptr(c_str).to_string_lossy().into_owned();
            result.push(ref_path);
            i += 1;
        }

        return result
    }
}


pub fn my_hash_path(input: String) -> String {
    let cstr = unsafe {
        let instr = CString::new(input).unwrap();
        CStr::from_ptr(hash_path(instr.as_ptr()))
    };
    return String::from_utf8_lossy(cstr.to_bytes()).to_string();
}

pub fn my_sign_detached(secret_key: &str, data: String) -> String {
    let signature_cstr = unsafe {
        let secret_key_cstr = CString::new(secret_key).unwrap();
        let data_cstr = CString::new(data).unwrap();
        // TODO error handling (e.g. invalid key format)
        CStr::from_ptr(sign_detached(secret_key_cstr.as_ptr(), data_cstr.as_ptr()))
    };
    return String::from_utf8_lossy(signature_cstr.to_bytes()).to_string();
}

#[derive(Debug, Serialize, Deserialize)]
pub struct OutputAttestation<'a> {
    pub output_digest: &'a str,
    pub output_name: &'a str,
    pub output_hash: String,
    pub output_sig: String,
}

pub fn read_env_var_or_panic(variable: &str) -> String {
    match env::var(variable) {
        Ok(v) => v,
        Err(_) => panic!("The {} variable is not set", variable),
    }
}

pub fn parse_drv_hash<'a>(drv_path: &'a str) -> &'a str {
    let re = Regex::new(r"\/nix\/store\/(.*)\.drv").unwrap();
    re.captures(drv_path)
        .expect("Derivation path should be of the form /nix/store/???.drv")
        .get(1).unwrap().as_str()
}

pub fn fingerprint(ctx: Ctx, out_path: &str, nar_hash: &str, size: u64) -> String {
    // It is OK to take the references from the store, as those are determined
    // based on the derivation (not the build), and the 'security' part of the
    // fingerprint is the nar_hash anyway, not the other metadata elements:
    let references = query_references(ctx, out_path).join(",");
    let fingerprint = format!("1;{out_path};{nar_hash};{size};{references}").to_string();
    return fingerprint;
}

pub async fn post(collection_server: &str, token: &str, drv_ident: &str, output_attestations: &Vec<OutputAttestation<'_>>) -> Result<()> {
    let client = reqwest::Client::new();
    client
        .post(format!("{0}/attestation/{1}", collection_server, drv_ident))
        .bearer_auth(token)
        .json(&output_attestations)
        .send()
        .await?;
    Ok(())
}

pub fn parse_store_path_digest(store_path: &str) -> &str {
    &store_path[11..43]
}
pub fn parse_store_path_name(store_path: &str) -> &str {
    &store_path[45..]
}
