use nix_hash_collection_utils::*;
use reqwest::{Client, Result};
use std::collections::HashSet;
use std::io::{self, Write};
use std::process::exit;
use std::process::Command;
use std::sync::mpsc;
use std::sync::mpsc::{Receiver, Sender};
use std::thread;

fn perform_rebuild(s: &SuggestedRebuild) -> std::result::Result<(), String> {
    println!(
        "To rebuild: {} using {}^{}",
        s.out_path, s.drv_path, s.output
    );
    let out = Command::new("nix")
        .args([
            "build",
            format!("{}^{}", s.drv_path, s.output).as_str(),
            "--no-link",
        ])
        .output()
        .expect("Failed to invoke 'nix build'");
    if out.status.success() {
        let out = Command::new("nix")
            .args([
                "build",
                format!("{}^{}", s.drv_path, s.output).as_str(),
                "--rebuild",
                "--no-link",
            ])
            .output()
            .expect("Failed to invoke 'nix build'");
        if out.status.success() {
            Ok(())
        } else {
            io::stdout().write_all(&out.stdout).unwrap();
            io::stdout().write_all(&out.stderr).unwrap();
            Err(format!(
                "'nix build --rebuild' for {} returned status code {}",
                s.drv_path, out.status
            ))
        }
    } else {
        io::stdout().write_all(&out.stdout).unwrap();
        io::stdout().write_all(&out.stderr).unwrap();
        Err(format!(
            "'nix build' for {} returned status code {}",
            s.drv_path, out.status
        ))
    }
}

enum RebuildResult {
    REBUILT,
    FAILED
}

struct Next {
    reply_to: Sender<SuggestedRebuild>,
    previous_result: Option<RebuildResult>,
}

#[tokio::main]
async fn main() -> Result<()> {
    let collection_server = read_env_var_or_panic("HASH_COLLECTION_SERVER");
    let token = read_env_var_or_panic("HASH_COLLECTION_TOKEN");
    let evaluation_id = read_env_var_or_panic("HASH_COLLECTION_EVALUATION");
    let n_builders = read_env_var_or_panic("MAX_CORES").parse::<i32>().unwrap();

    let client = Client::builder().user_agent("lila/1.0").build()?;

    let (tx, rx): (Sender<Next>, Receiver<Next>) = mpsc::channel();

    for _ in 0..n_builders {
        let coordinator = tx.clone();

        thread::spawn(move || {
            let (ltx, lrx) = mpsc::channel();
            let mut previous_result = None;
            loop {
                coordinator
                    .send(Next {
                        reply_to: ltx.clone(),
                        previous_result: previous_result,
                    })
                    .unwrap();
                let to_rebuild = lrx.recv().unwrap();
                match perform_rebuild(&to_rebuild) {
                    Ok(()) => {
                        previous_result = Some(RebuildResult::REBUILT);
                        println!("Rebuilt {}^{}", to_rebuild.drv_path, to_rebuild.output);
                    },
                    Err(str) => {
                        previous_result = Some(RebuildResult::FAILED);
                        println!("Failed to build: {}", str);
                    },
                };
            }
        });
    }

    let mut to_build: Vec<SuggestedRebuild> = Vec::new();
    let mut started = HashSet::new();

    let mut running = n_builders;
    let mut n_rebuilt = 0;
    let mut n_failed = 0;

    // Coordinator loop: gets a `Next` message from the
    // build threads when they're ready for their next rebuild.
    while running != 0 {
        let next = rx.recv().unwrap();
        match next.previous_result {
            None => (),
            Some(RebuildResult::REBUILT) => { n_rebuilt = n_rebuilt + 1; },
            Some(RebuildResult::FAILED) => { n_failed = n_failed + 1; },
        }
        match to_build.pop() {
            Some(candidate) => {
                started.insert(candidate.drv_path.clone());
                next.reply_to.send(candidate).unwrap()
            }
            None => {
                to_build = suggest(&client, &collection_server, &token, &evaluation_id)
                    .await?
                    .iter()
                    .filter(|x| !started.contains(&x.drv_path))
                    .cloned()
                    .collect();
                match to_build.pop() {
                    None => {
                        println!("Nothing left to build, waiting for builds to finish");
                        running = running - 1;
                    }
                    Some(candidate) => {
                        started.insert(candidate.drv_path.clone());
                        next.reply_to.send(candidate).unwrap()
                    }
                }
            }
        }
    }
    println!("All jobs finished: started {}, completed {}, failed {}",
        started.len(),
        n_rebuilt,
        n_failed
        );

    Ok(())
}
