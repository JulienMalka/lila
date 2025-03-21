use nix_hash_collection_utils::*;
use regex::Regex;
use reqwest::Result;
use std::env;

pub fn parse_store_path_hash(store_path: &str) -> &str {
    &store_path[11..43]
}

async fn fetch<'a>(out_path: &'a str) -> (String, OutputAttestation<'a>) {
    let hash = parse_store_path_hash(out_path);
    let response = reqwest::get(format!("https://cache.nixos.org/{0}.narinfo", hash))
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
            output_path: out_path,
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
    let args: Vec<String> = env::args().collect();
    let out_path = &args[1];
    let (drv_ident, output) = fetch(&out_path).await;

    post(&collection_server, &token, &drv_ident, &Vec::from([output]), &None).await?;
    Ok(())
}
