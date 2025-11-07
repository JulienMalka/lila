use nix_hash_collection_utils::*;
use reqwest::{Client, Result};

async fn perform_rebuild(s: SuggestedRebuild) -> Result<()> {
    println!("To rebuild: {} using {}^{}", s.out_path, s.drv_path, s.output);
    Ok(())
}

#[tokio::main]
async fn main() -> Result<()> {
    let collection_server = read_env_var_or_panic("HASH_COLLECTION_SERVER");
    let token = read_env_var_or_panic("HASH_COLLECTION_TOKEN");
    let report = read_env_var_or_panic("HASH_COLLECTION_REPORT");

    let client = Client::builder()
        .user_agent("lila/1.0")
        .build()?;

    let suggested = suggest(&client, &collection_server, &token, &report).await?;
    for item in suggested {
        perform_rebuild(item).await?;
    }

    Ok(())
}
