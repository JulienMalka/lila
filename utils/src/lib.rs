use libnixstore::query_references;
use regex::Regex;
use reqwest::Result;
use serde::{Deserialize, Serialize};
use std::env;

#[derive(Debug, Serialize, Deserialize)]
pub struct OutputAttestation<'a> {
    pub output_path: &'a str,
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
    re.captures(drv_path).unwrap().get(1).unwrap().as_str()
}

pub fn fingerprint(out_path: &str, nar_hash: &str, size: u64) -> String {
    // It is OK to take the references from the store, as those are determined
    // based on the derivation (not the build), and the 'security' part of the
    // fingerprint is the nar_hash anyway, not the other metadata elements:
    let references = query_references(out_path).expect("Query references").join(",");
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
