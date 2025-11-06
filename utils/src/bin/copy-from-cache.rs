use nix_hash_collection_utils::*;
use regex::Regex;
use reqwest::{Client, Result};
use std::env;

async fn fetch<'a>(client: &'a Client, cache_url: &'a str, out_path: &'a str) -> OutputAttestation<'a> {
    let out_digest = parse_store_path_digest(out_path);
    let out_name = parse_store_path_name(out_path);

    let response = client
        .get(format!("{0}/{1}.narinfo", cache_url, out_digest))
        .send()
        .await.expect("Fetching the narinfo")
        .text()
        .await.expect("Fetching the response body");

    if response == "404" {
        panic!("Metadata for [{0}] not found on cache.nixos.org", out_path);
    }

    // Deriver is not always populated, for example not for
    // /nix/store/kbqscm1vj7yfvrnvdn1s9pvm0g5gpbaj-Test-Memory-Cycle-1.06.tar.gz
    // so we take it as a parameter instead. Perhaps we should check against
    // the Deriver in the narinfo? But for FODs outputs may have multiple
    // derivers (for different systems/architectures), so that might not make
    // sense anyway.
    let nar_hash = Regex::new(r"(?m)NarHash: (.*)").unwrap()
        .captures(&response)
        .expect(format!("NarHash not found in metadata for [{0}]", out_path).as_str())
        .get(1).unwrap().as_str().to_owned();
    let sig = Regex::new(r"(?m)Sig: (.*)").unwrap()
        .captures(&response)
        .expect(format!("Sig not found in metadata for [{0}]", out_path).as_str())
        .get(1).unwrap().as_str().to_owned();

    OutputAttestation {
        output_digest: &out_digest,
        output_name: &out_name,
        output_hash: nar_hash,
        output_sig: sig,
    }
}

#[tokio::main]
async fn main() -> Result<()> {
    // TODO maybe move those to a config file?
    let token = read_env_var_or_panic("HASH_COLLECTION_TOKEN");
    let collection_server = read_env_var_or_panic("HASH_COLLECTION_SERVER");
    let cache_server = match env::var("CACHE_URL") {
        Ok(val) => val,
        Err(_) => "https://cache.nixos.org".to_string(),
    };
    let args: Vec<String> = env::args().collect();

    // The out path to fetch
    let out_path = &args[1];
    // The deriver identification, i.e. without '/nix/store', under which to file this out path
    let drv_ident = &args[2];

    let client = Client::builder()
        .user_agent("lila/1.0")
        .build()?;

    let output = fetch(&client, &cache_server, &out_path).await;
    post(&client, &collection_server, &token, &drv_ident, &Vec::from([output])).await?;

    Ok(())
}
