use nix_hash_collection_utils::*;
use reqwest::Result;
use std::process::Command;

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

    
    let laut_sig_p = Command::new("laut")
	.env("OUT_PATHS", out_paths.clone())
	.arg("sign")
	.arg("--secret-key-file")
	.arg("/etc/nix/private-key")
	.arg(&drv_path)
	.output()
	.expect("");

    let laut_sig: Option<_> = match laut_sig_p.status.code() {
	Some(0) => Some(String::from_utf8_lossy(&laut_sig_p.stdout).into_owned()),
	_ => None
    };

    let output_attestations: Vec<_> = out_paths
        .split(" ")
        .map(|path| -> OutputAttestation {
            let hash = nar_hash(ctx, path.to_string());
            let size = nar_size(ctx, path.to_string());
            let fingerprint = fingerprint(ctx, path, &hash, size);

            let signature = my_sign_detached(secret_key.as_str(), fingerprint);
            return OutputAttestation {
                output_path: path,
                output_hash: hash,
                output_sig: signature
            }
        })
        .collect();

    post(&collection_server, &token, &drv_ident, &output_attestations, &laut_sig).await?;
    Ok(())
}
