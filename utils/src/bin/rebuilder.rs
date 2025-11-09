use nix_hash_collection_utils::*;
use reqwest::{Client,Result};
use std::process::Command;
use std::io::{self, Write};

fn perform_rebuild(ctx: Ctx, s: SuggestedRebuild) {
    println!("To rebuild: {} using {}^{}", s.out_path, s.drv_path, s.output);
    let out = Command::new("nix")
        .args(["build", format!("{}^{}", s.drv_path, s.output).as_str(), "--no-link"])
        .output()
        .expect("Failed to invoke 'nix build'");
    println!("{}", out.status);
    io::stdout().write_all(&out.stdout);
    io::stdout().write_all(&out.stderr);
    // TODO add to naughty list when status != 0, eventually: nix-instantiate
    let out = Command::new("nix")
        .args(["build", format!("{}^{}", s.drv_path, s.output).as_str(), "--rebuild", "--no-link"])
        .output()
        .expect("Failed to invoke 'nix build'");
    println!("{}", out.status);
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
    let ctx = nix_init();
    // TODO parallelize, refresh 'suggested' list periodically
    for item in suggested {
        perform_rebuild(ctx, item);
    }

    Ok(())
}
