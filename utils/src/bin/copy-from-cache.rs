use nix_hash_collection_utils::*;
use regex::Regex;
use reqwest::Result;
use std::env;

async fn fetch<'a>(cache_url: &'a str, out_path: &'a str) -> (String, OutputAttestation<'a>) {
    let out_digest = parse_store_path_digest(out_path);
    let out_name = parse_store_path_name(out_path);
    let response = reqwest::get(format!("{0}/{1}.narinfo", cache_url, out_digest))
        .await.expect("Fetching the narinfo")
        .text()
        .await.expect("Fetching the response body");

    if response == "404" {
        panic!("Metadata for [{0}] not found on cache.nixos.org", out_path);
    }

    // TODO Deriver is not populated for static inputs, and may be super useful:
    // the same output may have multiple derivers even for non-FOD derivations.
    // Should we make it optional in the data model / API as well?
    // https://github.com/JulienMalka/nix-hash-collection/issues/25
    let deriver = Regex::new(r"(?m)Deriver: (.*).drv").unwrap()
        .captures(&response)
        .expect(format!("Deriver not found in metadata for [{0}]", out_path).as_str())
        .get(1).unwrap().as_str().to_owned();
    let nar_hash = Regex::new(r"(?m)NarHash: (.*)").unwrap()
        .captures(&response)
        .expect(format!("NarHash not found in metadata for [{0}]", out_path).as_str())
        .get(1).unwrap().as_str().to_owned();
    let sig = Regex::new(r"(?m)Sig: (.*)").unwrap()
        .captures(&response)
        .expect(format!("Sig not found in metadata for [{0}]", out_path).as_str())
        .get(1).unwrap().as_str().to_owned();

    (
        deriver,
        OutputAttestation {
            output_digest: &out_digest,
            output_name: &out_name,
            output_hash: nar_hash,
            output_sig: sig,
        }
    )
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
    let out_path = &args[1];
    let (drv_ident, output) = fetch(&cache_server, &out_path).await;

    post(&collection_server, &token, &drv_ident, &Vec::from([output])).await?;
    Ok(())
}
