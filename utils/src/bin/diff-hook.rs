use nix_hash_collection_utils::*;
use reqwest::{Client, Result};

#[tokio::main]
async fn main() -> Result<()> {
    let token = read_env_var_or_panic("HASH_COLLECTION_TOKEN");
    let secret_key = read_env_var_or_panic("HASH_COLLECTION_SECRET_KEY");
    let collection_server = read_env_var_or_panic("HASH_COLLECTION_SERVER");
    let out_path = read_env_var_or_panic("OUT_PATH");
    let rebuild_path = read_env_var_or_panic("REBUILD_PATH");
    let drv_path = read_env_var_or_panic("DRV_PATH");
    let drv_ident = parse_drv_hash(&drv_path);

    let out_digest = parse_store_path_digest(&out_path);
    let out_name = parse_store_path_name(&out_path);

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
            output_digest: &out_digest,
            output_name: &out_name,
            output_hash: hash,
            output_sig: signature
        }
    ];

    let client = Client::builder()
        .user_agent("lila/1.0")
        .build()?;
    post(&client, &collection_server, &token, &drv_ident, &output_attestations).await?;
    Ok(())
}
