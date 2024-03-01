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

    let deriver = Regex::new(r"(?m)Deriver: (.*).drv").unwrap()
        .captures(&response).unwrap().get(1).unwrap().as_str().to_owned();
    let nar_hash = Regex::new(r"(?m)NarHash: (.*)").unwrap()
        .captures(&response).unwrap().get(1).unwrap().as_str().to_owned();

    (
        deriver,
        OutputAttestation {
            output_path: out_path,
            output_hash: nar_hash,
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

    post(&collection_server, &token, &drv_ident, &Vec::from([output])).await?;
    Ok(())
}
