//! Export local simulation fixtures for an independent bytes/digest check.
//! Usage: export_simulation_observations .tmp/<new-directory>
#[path = "../tests/common/mod.rs"]
mod common;

use common::*;
use radishaxiom_ir::{
    json::canonicalize_json,
    replay::{ReplayInput, ReplayProfile, ReplayWorldInput, replay_target},
    solver::{ProcessExit, decode_model_world, parse_solver_response},
};
use radishaxiom_solver_diagnostic_host::*;
use std::{
    error::Error,
    fs::{self, OpenOptions},
    io::Write,
    path::{Component, Path},
};

fn write(directory: &Path, name: &str, bytes: &[u8]) -> std::result::Result<(), Box<dyn Error>> {
    let mut file = OpenOptions::new()
        .write(true)
        .create_new(true)
        .open(directory.join(name))?;
    file.write_all(bytes)?;
    Ok(())
}

fn failure_observation(plan: &SimulationPlan<'_>, kind: &str) -> SimulationObservation {
    let mut controller = running(plan);
    let limit = kind == "stdout-limit";
    assert_eq!(
        advance(
            &mut controller,
            16,
            SimulationEventKind::Output {
                stdout: if limit { Vec::new() } else { b"sat\n".to_vec() },
                stderr: b"simulation diagnostic\n".to_vec(),
            }
        )
        .rejection,
        None
    );
    assert_eq!(
        advance(
            &mut controller,
            17,
            SimulationEventKind::StreamsClosed {
                stdout: !limit,
                stderr: true
            }
        )
        .rejection,
        None
    );
    let end = match kind {
        "stdout-limit" => {
            assert_eq!(
                advance(
                    &mut controller,
                    20,
                    SimulationEventKind::Output {
                        stdout: vec![b'x'; STDOUT_LIMIT + 1],
                        stderr: Vec::new(),
                    }
                )
                .rejection,
                None
            );
            21
        }
        "oom-before-deadline" => {
            assert_eq!(
                advance(&mut controller, 20, SimulationEventKind::OomKilled).rejection,
                None
            );
            assert_eq!(
                advance(&mut controller, 6010, SimulationEventKind::DeadlineTick).rejection,
                None
            );
            6011
        }
        "deadline-before-oom" => {
            assert_eq!(
                advance(&mut controller, 6010, SimulationEventKind::DeadlineTick).rejection,
                None
            );
            assert_eq!(
                advance(&mut controller, 6011, SimulationEventKind::OomKilled).rejection,
                None
            );
            6012
        }
        "deadline-with-oom" => {
            // A deadline is recorded before the same-time explicit memory fact.
            assert_eq!(
                advance(&mut controller, 6010, SimulationEventKind::OomKilled).rejection,
                None
            );
            6011
        }
        _ => unreachable!(),
    };
    for (i, event) in [
        SimulationEventKind::Exit(ProcessExit::Exited(137)),
        SimulationEventKind::TreeTerminated,
        SimulationEventKind::Inspected,
        SimulationEventKind::TreeEmpty,
        SimulationEventKind::Cleaned,
    ]
    .into_iter()
    .enumerate()
    {
        assert_eq!(
            advance(&mut controller, end + i as u64, event).rejection,
            None
        );
    }
    controller.finish(end + 5).unwrap()
}

fn main() -> std::result::Result<(), Box<dyn Error>> {
    let args: Vec<_> = std::env::args().skip(1).collect();
    if args.len() != 1 {
        return Err("expected one new .tmp/<directory>".into());
    }
    let relative = Path::new(&args[0]);
    let parts: Vec<_> = relative.components().collect();
    if parts.len() != 2
        || parts[0] != Component::Normal(".tmp".as_ref())
        || !matches!(parts[1], Component::Normal(_))
    {
        return Err("export requires exactly .tmp/<new-directory>".into());
    }
    let directory = root().join(relative);
    fs::create_dir(&directory)?;
    let identity = identity();
    write(&directory, "identity.jcs", identity.canonical_bytes())?;
    let mut rows = Vec::new();
    for (name, kind, case, output, exit, cleanup_failed) in [
        (
            "minimal-sat",
            "minimal",
            minimal(),
            None,
            ProcessExit::Exited(0),
            false,
        ),
        (
            "composite-sat",
            "composite",
            composite(),
            None,
            ProcessExit::Exited(0),
            false,
        ),
        (
            "wrong-add-sat",
            "wrong-add",
            wrong_add(),
            None,
            ProcessExit::Exited(0),
            false,
        ),
        (
            "minimal-unsat",
            "minimal",
            minimal(),
            Some(b"unsat\n".as_slice()),
            ProcessExit::Exited(0),
            false,
        ),
        (
            "minimal-unknown",
            "minimal",
            minimal(),
            Some(b"unknown\n".as_slice()),
            ProcessExit::Exited(0),
            false,
        ),
        (
            "cleanup-failure",
            "minimal",
            minimal(),
            None,
            ProcessExit::Exited(0),
            true,
        ),
        (
            "exit137",
            "minimal",
            minimal(),
            None,
            ProcessExit::Exited(137),
            false,
        ),
        (
            "stdout-limit",
            "stdout-limit",
            minimal(),
            None,
            ProcessExit::Exited(137),
            false,
        ),
        (
            "oom-before-deadline",
            "oom-before-deadline",
            minimal(),
            None,
            ProcessExit::Exited(137),
            false,
        ),
        (
            "deadline-before-oom",
            "deadline-before-oom",
            minimal(),
            None,
            ProcessExit::Exited(137),
            false,
        ),
        (
            "deadline-with-oom",
            "deadline-with-oom",
            minimal(),
            None,
            ProcessExit::Exited(137),
            false,
        ),
    ] {
        let case_directory = directory.join(name);
        fs::create_dir(&case_directory)?;
        let request = &case.request;
        let plan = SimulationPlan::new(request, &identity, host_limits())?;
        let observation = if matches!(
            kind,
            "stdout-limit" | "oom-before-deadline" | "deadline-before-oom" | "deadline-with-oom"
        ) {
            failure_observation(&plan, kind)
        } else {
            let stdout = output
                .map(<[u8]>::to_vec)
                .unwrap_or_else(|| model(request, kind));
            observed(&plan, &stdout, exit, cleanup_failed)
        };
        let stdout = observation.stdout_bytes();
        let stderr = observation.stderr_bytes();
        for (file, bytes) in [
            ("request.jcs", request.canonical_bytes()),
            ("query.smt2", request.stdin_bytes()),
            ("symbols.jcs", request.symbol_bytes()),
            ("layout.jcs", request.layout_bytes()),
            ("plan.jcs", plan.canonical_bytes()),
            ("observation.jcs", observation.canonical_bytes()),
            ("stdout.raw", stdout),
            ("stderr.raw", stderr),
        ] {
            write(&case_directory, file, bytes)?;
        }
        let status = if let Ok(input) = observation.simulation_response_input() {
            let response = parse_solver_response(request, input)?;
            write(&case_directory, "response.jcs", response.canonical_bytes())?;
            if let Some(model) = response.sat_model() {
                let candidate = decode_model_world(request, model)?;
                let replay = replay_target(
                    ReplayProfile::MapFilterV0_1,
                    ReplayInput {
                        document: &case.document,
                        obligations: &case.obligations,
                        obligation_id: request.query().binding().obligation(),
                        generator: &generator(),
                        world: ReplayWorldInput::ModelCandidate {
                            request,
                            model,
                            candidate: &candidate,
                        },
                    },
                    replay_limits(),
                )?;
                write(
                    &case_directory,
                    "candidate.jcs",
                    candidate.canonical_bytes(),
                )?;
                write(&case_directory, "world.jcs", candidate.world_bytes())?;
                write(&case_directory, "replay.jcs", replay.canonical_bytes())?;
            }
            format!("{:?}", response.status())
        } else {
            "rejected-before-P4".to_owned()
        };
        rows.push(format!("{{\"case\":\"{name}\",\"scope\":\"simulation\",\"status\":\"{status}\",\"request_raw_digest\":\"{}\",\"query_raw_digest\":\"{}\",\"query_bytes\":\"{}\",\"symbols\":\"{}\",\"plan_raw_digest\":\"{}\",\"observation_raw_digest\":\"{}\",\"stdout_raw_digest\":\"{}\",\"stderr_raw_digest\":\"{}\"}}",
            request.artifact_digest(), request.query().artifact_digest(), request.stdin_bytes().len(),
            request.query().symbols().len(), plan.artifact_digest(), observation.artifact_digest(),
            raw_digest(stdout), raw_digest(stderr)));
    }
    let manifest = format!(
        "{{\"format\":\"axiom-solver-simulation-export\",\"version\":\"0.1\",\"scope\":\"simulation\",\"real_execution\":\"blocked-E0-E3\",\"identity_raw_digest\":\"{}\",\"cases\":[{}]}}",
        identity.artifact_digest(),
        rows.join(",")
    );
    write(
        &directory,
        "manifest.jcs",
        &canonicalize_json(manifest.as_bytes(), json_limits())?,
    )?;
    println!("simulation-only export: {}", directory.display());
    Ok(())
}
