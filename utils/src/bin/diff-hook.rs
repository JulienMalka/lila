//use libnixstore::{hash_path, query_path_info, sign_string, Radix::Base32};
use nix_hash_collection_utils::*;
use reqwest::Result;

#[tokio::main]
async fn main() -> Result<()> {
    let token = read_env_var_or_panic("HASH_COLLECTION_TOKEN");
    let secret_key = read_env_var_or_panic("HASH_COLLECTION_SECRET_KEY");
    let collection_server = read_env_var_or_panic("HASH_COLLECTION_SERVER");
    let out_path = read_env_var_or_panic("OUT_PATH");
    let rebuild_path = read_env_var_or_panic("REBUILD_PATH");
    let drv_path = read_env_var_or_panic("DRV_PATH");
    let drv_ident = parse_drv_hash(&drv_path);

    let hash = format!("sha256:{0}", my_hash_path(rebuild_path));

    println!(
        "Uploading hash of build output for derivation {0} to {1}: {2}",
        drv_ident, collection_server, hash
    );

    // Creating a signature requires a connection to the daemon, which
    // is not available when the hook is being run?
    let signature = "".to_string();

    let output_attestations: Vec<_> = vec![
        OutputAttestation {
            output_path: &out_path,
            output_hash: hash,
            output_sig: signature
        }
    ];

    post(&collection_server, &token, &drv_ident, &output_attestations).await?;
    Ok(())
}
