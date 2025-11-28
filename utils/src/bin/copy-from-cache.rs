use nix_hash_collection_utils::*;
use regex::Regex;
use reqwest::{Client, Result};
use std::collections::HashSet;
use std::env;
use std::process::exit;

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

async fn copy(client: &Client, cache_server: &str, collection_server: &str, token: &str, out_path: &str, drv_hash: &str) -> Result<()> {
        let output = fetch(&client, &cache_server, &out_path).await;
        post(&client, &collection_server, &token, &drv_hash, &Vec::from([output])).await?;
        Ok(())
}

async fn copy_all(client: &Client, cache_server: &str, evaluation: &str, collection_server: &str, token: &str) -> Result<()> {
    let mut failed: HashSet<String> = HashSet::new();
    let mut to_build: Vec<SuggestedRebuild> = Vec::new();
    loop {
        match to_build.pop() {
            Some(candidate) => {
                let drv_hash = parse_drv_hash(&candidate.drv_path);
                match copy(client, cache_server, collection_server, token, &candidate.out_path, drv_hash).await {
                //match copy(client, cache_server, collection_server, token, &candidate.out_path, &candidate.drv_path.clone()).await {
                    Ok(()) =>
                        (),// Continue
                    Err(_) => {
                        failed.insert(candidate.drv_path.clone());
                    },
                };
            }
            None => {
                to_build = suggest(&client, &collection_server, &token, &evaluation)
                    .await?
                    .iter()
                    .filter(|x| !failed.contains(&x.drv_path))
                    .cloned()
                    .collect();
                if to_build.is_empty() {
                    println!("Nothing left to copy!");
                    exit(0)
                }
            }
        }
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

    let client = Client::builder()
        .user_agent("lila/1.0")
        .build()?;

    if args.len() == 2 {
        // The out path to fetch
        let out_path = &args[1];
        // The derivation hash, i.e. the derivation path without the '/nix/store' prefix
        // or '.drv' suffix, under which to file this out path
        let drv_hash = &args[2];

        copy(&client, &cache_server, &collection_server, &token, &out_path, &drv_hash).await?;
    } else {
        let evaluation = read_env_var_or_panic("HASH_COLLECTION_EVALUATION");
        copy_all(&client, &cache_server, &evaluation, &collection_server, &token).await?;
    }

    Ok(())
}
