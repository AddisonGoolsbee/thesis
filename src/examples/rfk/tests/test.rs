extern crate expectrl;
extern crate regex;
extern crate vte;
use expectrl::{spawn, Regex};
use regex::escape;
use std::process::{Command, Stdio};
use std::thread;
use std::time::Duration;

#[test]
fn runs_and_starts_successfully() {
    let mut child = Command::new(env!("CARGO_BIN_EXE_robotfindskitten"))
        .stdin(Stdio::null())
        .stdout(Stdio::null())
        .stderr(Stdio::null())
        .spawn()
        .expect("Failed to start robotfindskitten");

    thread::sleep(Duration::from_millis(200));

    let _ = child.kill(); // ensure cleanup
    let status = child.wait().expect("Failed to wait on child");

    assert!(
        status.success() || !status.success(),
        "Program shouldn't crash immediately"
    );
}

#[test]
fn test_movement_keys() -> Result<(), Box<dyn std::error::Error>> {
    let mut p = spawn(env!("CARGO_BIN_EXE_robotfindskitten"))?;

    // Wait for the intro screen to show up
    p.set_expect_timeout(Some(Duration::from_millis(200)));
    p.expect(Regex("Press any key to start"))?;

    // Start the game
    p.send("a")?;
    std::thread::sleep(Duration::from_millis(1));
    p.expect(Regex("robotfindskitten"))?;

    // Move around 
    p.send("j")?;
    p.send("h")?;
    p.send("k")?;
    p.send("l")?;

    Ok(())
}

mod messages_data {
    include!("utils/messages_data.rs");
}

#[test]
fn test_robot_screen_rendering() -> Result<(), Box<dyn std::error::Error>> {
    let messages = messages_data::MESSAGES;
    let combined = std::iter::once("robotfindskitten")
        .chain(messages.iter().cloned())
        .map(|s| escape(s))
        .collect::<Vec<_>>()
        .join("|");

    // we're testing if the robot runs into a bogus entity, which only works about 95% of the time, so this is run 3 times
    for i in 0..3 {
        let mut p = spawn(env!("CARGO_BIN_EXE_robotfindskitten"))?;
        p.set_expect_timeout(Some(Duration::from_millis(200)));
        p.expect(Regex("Press any key to start"))?;

        p.send("a")?;
        std::thread::sleep(Duration::from_millis(1));
        p.expect(Regex("robotfindskitten"))?;

        // terminal spawns with 24 x 80 dimensions, in the exact center. We move right 35 tiles then give up if there's no bump
        for _ in 0..35 {
            p.send("l")?;
            std::thread::sleep(Duration::from_millis(1));
            let m = p.check(Regex(&combined))?;
            if m.get(0).is_some() {
                return Ok(());
            }
        }
        println!("Test {}/3 failed: no bump found", i + 1);
    }
    Err("Couldn't bump into an entity".into())
}
