use nix_hash_collection_utils::*;
use reqwest::Result;

#[tokio::main]
async fn main() -> Result<()> {
    let ctx = nix_init();
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
            let hash = nar_hash(ctx, path.to_string());
            let size = nar_size(ctx, path.to_string());
            //let fingerprint = fingerprint(path, &hash, size);
            //let signature = sign_string(secret_key.as_str(), &fingerprint).expect("Failed to sign fingerprint");
            let signature = my_sign_detached(secret_key.as_str(), String::from("42"));
            return OutputAttestation {
                output_path: "42",//path,
                output_hash: "42".to_string(),//hash,
                output_sig: signature
            }
        })
        .collect();

    post(&collection_server, &token, &drv_ident, &output_attestations).await?;
    Ok(())
}
