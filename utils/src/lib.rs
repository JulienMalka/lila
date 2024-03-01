use reqwest::Result;
use serde::{Deserialize, Serialize};
use std::env;

#[derive(Debug, Serialize, Deserialize)]
pub struct OutputReport<'a> {
    pub output_path: &'a str,
    pub output_hash: String,
}

pub fn read_env_var_or_panic(variable: &str) -> String {
    match env::var(variable) {
        Ok(v) => v,
        Err(_) => panic!("The {} variable is not set", variable),
    }
}

pub async fn post(collection_server: &str, token: &str, drv_ident: &str, output_reports: &Vec<OutputReport<'_>>) -> Result<()> {
    let client = reqwest::Client::new();
    client
        .post(format!("{0}/report/{1}", collection_server, drv_ident))
        .bearer_auth(token)
        .json(&output_reports)
        .send()
        .await?;
    Ok(())
}
