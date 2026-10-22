mod common;
#[path = "common/e3_workflow.rs"]
mod e3_workflow;
use radishaxiom_digest::{Sha256, digest};
use radishaxiom_solver_diagnostic_host::{bootstrap_manifest::*, e3_policy::*, raw_digest};

#[test]
fn old_e3_export_goldens_and_streaming_original_capacity_remain_identical() {
    let artifact = e3_workflow::full_workflow();
    let goldens = [
        (
            &artifact.binding,
            "d04fbc648b6a1d24697a2641b46817155ed30e6ff225354463cb1f0739402189",
        ),
        (
            &artifact.candidate,
            "3acaf8dee140d89b1bd54c0fc566de6a4de44c9c424c0f15be52e3b1b1e5a49f",
        ),
        (
            &artifact.mac_wire,
            "93a08e92724c4188fddaf0426b6a90ddd966a875845c48043a91aaa22846899b",
        ),
        (
            &artifact.query,
            "5ba58e0d9754c3448f299ce4d9be2060c2d91d829253ec3e4a170e0d4d07a85a",
        ),
        (
            &artifact.replay,
            "87038bb9efdd6ee67351ee042e184d858e7ac001d8fa90e2ddb8655c8d752462",
        ),
        (
            &artifact.request,
            "4142ebacee8a61d69485e09050a5def8497c5738bfe773434da3496b6a335a91",
        ),
        (
            &artifact.response,
            "57bd17421375b3c8f08e0d11327e444e1ff2de6d54994ed9b47ca530fcd17ab1",
        ),
        (
            &artifact.stderr,
            "0fc85d148d03fe05e6d58cad8e20dc1dc5d3223d237df4f2349153430243f72a",
        ),
        (
            &artifact.stdout,
            "a247b4f3b8c27b22aed56f9ba173b04084f19a4b0b855a692550e3af48e32796",
        ),
        (
            &artifact.supervisor_wire,
            "8b27ac6e6f481aabe9181f1e4d08366a851a735434cd871478be44d7a52e7468",
        ),
        (
            &artifact.world,
            "a9c7c19884863a92c51d933ee36a4d5073baaca336125d43261d141e4ee2a8b9",
        ),
    ];
    for (bytes, golden) in goldens {
        assert_eq!(raw_digest(bytes), format!("sha256:{golden}"));
    }
    assert_eq!(artifact.query.len(), 962_642);
    for chunk_size in [1, 55, 56, 63, 64, 65, 4096, 65_376] {
        let mut hash = Sha256::new();
        hash.update(&[]).unwrap();
        for chunk in artifact.query.chunks(chunk_size) {
            hash.update(chunk).unwrap();
            hash.update(&[]).unwrap();
        }
        assert_eq!(hash.finalize(), digest(&artifact.query));
    }
    assert_eq!(
        worker_policy().digest(),
        "sha256:2f5ff64bffb3b8cd438049d8f33d6ce86f9d3c72f4d61add5eba7da056a04e8f"
    );
    assert_eq!(
        SupervisorRuntimePolicy::new(BOOTSTRAP_SUPERVISOR_ROLES)
            .unwrap()
            .compile()
            .digest(),
        "sha256:cf0ff9e3b57b8a0b3fa38414082a128922eb09ad9c14f9a5a227327a9572b57e"
    );
}

#[test]
fn offline_export_binds_actual_inputs_and_rejects_each_drift_direction() {
    let original = export_offline_inputs();
    assert_eq!(check_offline_inputs(&original), Ok(()));
    assert_eq!(export_offline_inputs(), original);
    let resources = process_resource_inputs();
    let old = radishaxiom_ir::solver::PROCESS_LIMITS;
    assert_eq!(resources.wire.query_bytes, old.stdin_bytes);
    assert_eq!(resources.wire.stdout_bytes, old.stdout_bytes);
    assert_eq!(resources.wire.stderr_bytes, old.stderr_bytes);
    assert_eq!(resources.cgroup.memory_max, old.working_memory_bytes as u64);
    assert_eq!(resources.wall_clock_ms, old.wall_clock_ms);
    let manifest = std::str::from_utf8(&original.manifest).unwrap();
    for bytes in [
        &original.inputs,
        &original.worker_cbpf,
        &original.supervisor_cbpf,
    ] {
        assert!(manifest.contains(&raw_digest(bytes)));
    }
    assert!(manifest.contains("\"outer_setup_policy\":\"not-established\""));
    assert!(manifest.contains("\"native_build\":\"not-accepted\""));
    assert!(!manifest.contains("final_image"));
    let mut bad = original.clone();
    bad.manifest[0] ^= 1;
    assert_eq!(check_offline_inputs(&bad), Err(InputMismatch::Manifest));
    let mut bad = original.clone();
    bad.inputs[0] ^= 1;
    assert_eq!(check_offline_inputs(&bad), Err(InputMismatch::Resources));
    let mut bad = original.clone();
    bad.worker_cbpf[0] ^= 1;
    assert_eq!(check_offline_inputs(&bad), Err(InputMismatch::WorkerPolicy));
    let mut bad = original;
    bad.supervisor_cbpf[0] ^= 1;
    assert_eq!(
        check_offline_inputs(&bad),
        Err(InputMismatch::SupervisorPolicy)
    );
}
