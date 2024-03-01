use libnixstore::{hash_path, Radix::Base32};
use nix_hash_collection_utils::*;
use regex::Regex;
use reqwest::Result;

fn parse_drv_hash<'a>(drv_path: &'a str) -> &'a str {
    let re = Regex::new(r"\/nix\/store\/(.*)\.drv").unwrap();
    re.captures(drv_path).unwrap().get(1).unwrap().as_str()
}

#[tokio::main]
async fn main() -> Result<()> {
    let token = read_env_var_or_panic("HASH_COLLECTION_TOKEN");
    let collection_server = read_env_var_or_panic("HASH_COLLECTION_SERVER");
    let out_paths = read_env_var_or_panic("OUT_PATHS");
    let drv_path = read_env_var_or_panic("DRV_PATH");
    let drv_ident = parse_drv_hash(&drv_path);

    println!(
        "Uploading hashes of build outputs for derivation {0} to {1}",
        drv_ident, collection_server
    );

    let output_attestations: Vec<_> = out_paths
        .split(" ")
        .map(|path| OutputAttestation {
            output_path: path,
            output_hash: hash_path("sha256", Base32, path).unwrap(),
        })
        .collect();

    post(&collection_server, &token, &drv_ident, &output_attestations).await?;
    Ok(())
}
