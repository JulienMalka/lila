use libnixstore::{query_path_info, query_references, sign_string, Radix::Base32};
use nix_hash_collection_utils::*;
use regex::Regex;
use reqwest::Result;

fn parse_drv_hash<'a>(drv_path: &'a str) -> &'a str {
    let re = Regex::new(r"\/nix\/store\/(.*)\.drv").unwrap();
    re.captures(drv_path).unwrap().get(1).unwrap().as_str()
}

fn fingerprint(out_path: &str, nar_hash: &str, size: u64) -> String {
    let references = query_references(out_path).expect("Query references").join(",");
    let fingerprint = format!("1;{out_path};{nar_hash};{size};{references}").to_string();
    return fingerprint;
}

#[tokio::main]
async fn main() -> Result<()> {
    libnixstore::init();
    let token = read_env_var_or_panic("HASH_COLLECTION_TOKEN");
    let secret_key = read_env_var_or_panic("HASH_COLLECTION_SECRET_KEY");
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
        .map(|path| -> OutputAttestation {
            let info = query_path_info(path, Base32).unwrap();
            let hash = info.narhash;
            let size = info.size;
            let fingerprint = fingerprint(path, &hash, size);
            let signature = sign_string(secret_key.as_str(), &fingerprint).expect("Failed to sign fingerprint");
            return OutputAttestation {
                output_path: path,
                output_hash: hash,
                output_sig: signature
            }
        })
        .collect();

    post(&collection_server, &token, &drv_ident, &output_attestations).await?;
    Ok(())
}
