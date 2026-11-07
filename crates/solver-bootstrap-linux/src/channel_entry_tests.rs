//! End-to-end transport/supervision fault injection on the same in-memory kernel.
use super::*;
use crate::{
    channel_entry,
    channel_profile::*,
    channel_report::{Decoder, Final, Reason},
};
use std::ffi::CString;

fn drive(model: Model) -> (u8, Report, Model) {
    let mut linux = Linux::new(model);
    let mut budget = Budget::new(linux.boottime_ns().unwrap()).unwrap();
    let (code, report) = channel_entry::drive(
        &mut linux,
        &mut budget,
        binding(),
        c"printf synthetic",
        |_, code, report| (code, report),
    );
    (code, report, linux.kernel)
}
fn success() -> Model {
    Model::new([Wait::Exit(exit(42, 1, 0)), Wait::Empty], &[b"", b""])
}
fn decode(model: &Model) -> Final {
    let mut d = Decoder::new(binding());
    // Actual kernel-written bytes, never Encoder's queued-but-unwritten buffer.
    for part in model.wire.chunks(7) {
        d.feed(part).unwrap();
    }
    d.finish().unwrap()
}
#[test]
fn entry_captures_internal_streams_and_preserves_real_final_status() {
    let mut m = success();
    m.now = 123;
    m.output[0] = vec![b'x'; CHUNK_LIMIT + 19].into();
    m.output[1] = b"AXCI\x00\xffsynthetic-only".to_vec().into();
    let (code, r, m) = drive(m);
    assert_eq!(code, 0);
    assert!(r.no_children);
    let f = decode(&m);
    assert_eq!(f.first_ns, 123);
    assert!(f.last_ns < 123 + CLEANUP_NS);
    assert_eq!(f.stdout.exported as usize, CHUNK_LIMIT + 19);
    assert_eq!(
        f.stdout.digest,
        radishaxiom_digest::digest(&vec![b'x'; CHUNK_LIMIT + 19])
    );
    assert_eq!(f.stderr.exported, 20);
    assert!(f.stdout.eof && f.stderr.eof);
    assert!(!f.stdout.prefix_only && !f.transport_failed);
    assert_eq!(f.selected_exit_code, code);
    assert_eq!(m.calls[0].nr, NR_CLOCK_GETTIME);
    assert_eq!(m.calls.iter().filter(|c| c.nr == NR_PIPE2).count(), 3);
    m.done();
}
#[test]
fn arbitrarily_short_writes_and_eagain_keep_exact_offset_and_hash() {
    let mut m = success();
    m.output[0] = b"synthetic-body".to_vec().into();
    m.write_sizes = [1, errno(11), 2, 3, errno(11), 7, 13, 19].into();
    let (code, _, m) = drive(m);
    assert_eq!(code, 0);
    let f = decode(&m);
    assert_eq!(f.stdout.exported, 14);
    assert_eq!(
        f.stdout.digest,
        radishaxiom_digest::digest(b"synthetic-body")
    );
    m.done();
}
#[test]
fn interrupted_write_keeps_the_error_and_completes_the_same_frame() {
    let mut m = success();
    m.write_sizes = [1, errno(4)].into();
    let (code, r, m) = drive(m);
    assert_eq!(code, 125);
    assert!(r.errors.iter().any(|e| e.errno() == Some(4)));
    let f = decode(&m);
    assert!(f.transport_failed);
    assert_eq!(f.cause, Some(Reason::Transport));
    assert_eq!(f.selected_exit_code, 125);
    m.done();
}
#[test]
fn epipe_after_partial_start_cannot_append_a_final_or_exit_zero() {
    let mut m = success();
    m.write_sizes = [9, errno(32)].into();
    let (code, r, m) = drive(m);
    assert_eq!(code, 125);
    assert!(r.no_children);
    assert_eq!(m.wire.len(), 9);
    let mut d = Decoder::new(binding());
    d.feed(&m.wire).unwrap();
    assert!(d.finish().is_err());
    m.done();
}
#[test]
fn zero_write_is_failure_even_before_clone() {
    let mut m = Model::new([], &[b""]);
    m.write_sizes.push_back(0);
    let (code, r, m) = drive(m);
    assert_eq!(code, 125);
    assert!(!r.clone_attempted);
    assert_eq!(m.clone_count, 0);
    assert!(r.errors.iter().any(|e| e.operation == "channel-write-zero"));
    m.done();
}
#[test]
fn read_eintr_is_not_silently_retried_as_success() {
    let mut m = Model::new([Wait::Exit(exit(42, 2, 9)), Wait::Empty], &[b"", b"42 "]);
    m.read_errno = Some(4);
    let (code, r, m) = drive(m);
    assert_eq!(code, 125);
    assert_eq!(m.kills, vec![42]);
    assert!(r.no_children);
    let f = decode(&m);
    assert!(f.capture_failed);
    assert_eq!(f.cause, Some(Reason::Capture));
    assert!(f.stdout.eof && f.stderr.eof);
    m.done();
}
#[test]
fn read_failure_reports_missing_eof_with_observed_prefix() {
    let mut m = Model::new([Wait::Exit(exit(42, 2, 9)), Wait::Empty], &[b"", b"42 "]);
    m.read_errno = Some(5);
    let (code, _, m) = drive(m);
    assert_eq!(code, 125);
    let f = decode(&m);
    assert!(!f.stdout.eof);
    assert!(f.stdout.prefix_only);
    assert!(f.capture_failed);
    m.done();
}
#[test]
fn n_plus_one_capture_is_a_lower_bound_and_never_extends_stream_cap() {
    for i in 0..2 {
        let cap = if i == 0 { STDOUT_LIMIT } else { STDERR_LIMIT };
        let mut m = success();
        m.output[i] = vec![b'z'; cap + 1].into();
        let (code, _, m) = drive(m);
        assert_eq!(code, 125);
        let f = decode(&m);
        let s = if i == 0 { f.stdout } else { f.stderr };
        assert_eq!(s.seen, cap as u64 + 1);
        assert_eq!(s.exported as usize, cap);
        assert_eq!(s.digest, radishaxiom_digest::digest(&vec![b'z'; cap]));
        assert!(s.prefix_only && !s.eof);
        m.done();
    }
}
#[test]
fn echild_is_not_pipe_eof_and_cleanup_leaves_original_final_reserve() {
    let mut m = success();
    m.never_eof = true;
    let (code, r, m) = drive(m);
    assert_eq!(code, 125);
    assert!(r.no_children);
    let f = decode(&m);
    assert!(!f.stdout.eof && !f.stderr.eof);
    assert!(f.last_ns >= CLEANUP_NS && f.last_ns < TOTAL_NS);
    assert_eq!(m.now, CLEANUP_NS);
    m.done();
}
#[test]
fn permanent_transport_backpressure_still_reaps_and_exits_by_final_deadline() {
    let mut m = success();
    m.write_sizes = vec![errno(11); 3000].into();
    let (code, r, m) = drive(m);
    assert_eq!(code, 125);
    assert!(r.no_children);
    assert!(m.wire.is_empty());
    assert_eq!(m.now, TOTAL_NS);
    m.done();
}
#[test]
fn cancellation_and_work_deadline_survive_transport_failure() {
    for cancel in [false, true] {
        let mut m = Model::new(
            if cancel {
                vec![Wait::Exit(exit(42, 2, 9)), Wait::Empty]
            } else {
                vec![
                    Wait::Advance(WORK_NS),
                    Wait::Exit(exit(42, 2, 9)),
                    Wait::Empty,
                ]
            },
            &[b"", b"42 "],
        );
        // Start is partial; work is then cancelled/deadlined before EPIPE.
        m.write_sizes = [1, errno(11), errno(32)].into();
        if cancel {
            m.pending.push_back(15);
        }
        let (code, r, m) = drive(m);
        assert_eq!(code, if cancel { 143 } else { 124 });
        assert!(r.no_children);
        assert_eq!(m.kills, vec![42]);
        m.done();
    }
}
#[test]
fn every_pipe_setup_failure_closes_all_acquired_owners_without_clone() {
    for n in 1..=3 {
        let mut m = Model::new([], &[b""]);
        m.pipe_fail = Some(n);
        let (code, r, m) = drive(m);
        assert_eq!(code, 125);
        assert!(!r.clone_attempted);
        assert!(r.errors.iter().any(|e| e.errno() == Some(24)));
        m.done();
    }
}
#[test]
fn stdin_close_eintr_consumes_owner_once_and_never_clones() {
    let mut m = Model::new([], &[b""]);
    m.close_errno = Some(4);
    m.close_after = 1;
    // The second close consumes the stdin writer; no retry may target its reuse.
    let (code, r, m) = drive(m);
    assert_eq!(code, 125);
    assert!(!r.clone_attempted);
    assert!(r.errors.iter().any(|e| e.errno() == Some(4)));
    m.done();
}
#[test]
fn poll_eintr_stops_work_but_does_not_hide_real_main_or_echild() {
    let mut m = Model::new(
        [Wait::Running, Wait::Exit(exit(42, 2, 9)), Wait::Empty],
        &[b"", b"42 "],
    );
    m.poll_errno = Some(4);
    let (code, r, m) = drive(m);
    assert_eq!(code, 125);
    assert!(r.no_children);
    assert_eq!(r.main_exit, Some(exit(42, 2, 9)));
    assert_eq!(m.kills, vec![42]);
    assert!(decode(&m).errors.iter().any(|e| e.operation == "ppoll"));
    m.done();
}
#[test]
fn child_dup_stderr_failure_has_no_external_diagnostic_write() {
    let input = Tail {
        argv: 0,
        env: 0,
        work_end: WORK_NS,
        stdio: [3, 4, 5],
    };
    let mut k = TailModel {
        calls: Vec::new(),
        record: Vec::new(),
        fail: Some(NR_DUP3),
    };
    assert!(catch_unwind(AssertUnwindSafe(|| unsafe { tail(&mut k, &input) })).is_err());
    assert_eq!(k.calls, vec![NR_DUP3, NR_EXIT_GROUP]);
    assert!(k.record.is_empty());
}
#[test]
fn raw_terminal_exit_is_reached_after_full_final_and_never_returns() {
    let mut linux = Linux::new(success());
    assert!(
        catch_unwind(AssertUnwindSafe(|| channel_entry::enter(
            &mut linux,
            || Ok((binding(), CString::new("printf synthetic").unwrap()))
        )))
        .is_err()
    );
    assert_eq!(linux.kernel.calls[0].nr, NR_CLOCK_GETTIME);
    assert_eq!(linux.kernel.calls.last().unwrap().nr, NR_EXIT_GROUP);
    assert_eq!(linux.kernel.calls.last().unwrap().args[0], 0);
    assert_eq!(decode(&linux.kernel).selected_exit_code, 0);
    linux.kernel.done();
}
#[test]
fn failed_first_clock_never_constructs_binding_or_report() {
    let mut m = Model::new([], &[]);
    m.fail_nr = Some((NR_CLOCK_GETTIME, errno(5)));
    let mut linux = Linux::new(m);
    assert!(
        catch_unwind(AssertUnwindSafe(|| channel_entry::enter(
            &mut linux,
            || panic!("prepare must be unreachable")
        )))
        .is_err()
    );
    assert_eq!(
        linux.kernel.calls.iter().map(|c| c.nr).collect::<Vec<_>>(),
        vec![NR_CLOCK_GETTIME, NR_EXIT_GROUP]
    );
    assert_eq!(linux.kernel.calls.last().unwrap().args[0], 125);
}

#[test]
fn broken_final_or_expired_clock_after_final_cannot_select_success() {
    for errno in [4, 32] {
        let mut m = success();
        m.final_errno = Some(errno);
        let (code, r, m) = drive(m);
        assert_eq!(code, 125);
        assert!(r.no_children);
        assert!(r.errors.iter().any(|e| e.errno() == Some(errno as u16)));
        let mut d = Decoder::new(binding());
        d.feed(&m.wire).unwrap();
        assert!(d.finish().is_err());
        m.done();
    }
    let mut m = success();
    m.final_time = Some(TOTAL_NS);
    let (code, _, m) = drive(m);
    assert_eq!(code, 125);
    // Complete Final alone cannot authenticate the subsequent runtime exit.
    assert_eq!(decode(&m).selected_exit_code, 0);
    assert_eq!(m.now, TOTAL_NS);
    m.done();
}
#[test]
fn cancellation_after_final_freeze_is_failure_not_a_second_final() {
    let mut m = success();
    m.final_cancel = true;
    let (code, r, m) = drive(m);
    assert_eq!(code, 143);
    assert_eq!(r.cause, Some(Cause::Cancelled(15)));
    let mut d = Decoder::new(binding());
    d.feed(&m.wire).unwrap();
    assert!(d.finish().is_err());
    m.done();
}
#[test]
fn half_chunk_is_never_counted_as_exported_or_followed_by_final() {
    let mut m = success();
    m.output[0] = b"synthetic".to_vec().into();
    m.cut_chunk = true;
    let (code, r, m) = drive(m);
    assert_eq!(code, 125);
    assert!(r.no_children);
    let mut d = Decoder::new(binding());
    d.feed(&m.wire).unwrap();
    assert!(d.finish().is_err());
    assert!(
        !m.calls
            .iter()
            .any(|c| c.nr == NR_CHANNEL_CLONE && c.args[0] != SIGCHLD)
    );
    m.done();
}
#[test]
fn parent_close_failure_after_clone_preserves_child_and_kills_before_reap() {
    let mut m = Model::new([Wait::Exit(exit(42, 2, 9)), Wait::Empty], &[b"", b"42 "]);
    m.close_errno = Some(4);
    m.close_after = 2;
    let (code, r, m) = drive(m);
    assert_eq!(code, 125);
    assert_eq!(r.child_pid, Some(42));
    assert!(r.no_children);
    assert_eq!(m.kills, vec![42]);
    assert!(
        decode(&m)
            .errors
            .iter()
            .any(|e| e.operation == "close" && e.detail == 4)
    );
    m.done();
}

#[test]
fn echild_without_main_reap_is_exportable_as_failure_with_both_facts() {
    let m = Model::new([Wait::Empty, Wait::Empty], &[b"", b"42 "]);
    let (code, r, m) = drive(m);
    assert_eq!(code, 125);
    assert!(r.no_children);
    let f = decode(&m);
    assert!(f.no_children);
    assert!(f.main_exit.is_none());
    assert!(
        f.errors
            .iter()
            .any(|e| e.operation == "channel-init-missing-main-exit")
    );
    assert_eq!(f.selected_exit_code, 125);
    m.done();
}

#[test]
fn emergency_bridge_raw_exits_125_without_clock_io_or_report() {
    let mut linux = Linux::new(Model::new([], &[]));
    let e = catch_unwind(AssertUnwindSafe(|| channel_entry::terminal(&mut linux))).unwrap_err();
    assert_eq!(*e.downcast::<u8>().unwrap(), 125);
    assert_eq!(
        linux.kernel.calls.iter().map(|c| c.nr).collect::<Vec<_>>(),
        vec![NR_EXIT_GROUP]
    );
}
#[test]
fn preparation_elapsed_time_does_not_restart_work_budget() {
    let mut m = Model::new([], &[]);
    m.clock_values = [5, 5 + WORK_NS, 5 + WORK_NS].into();
    let (code, r, m) = drive(m);
    assert_eq!(code, 124);
    assert_eq!(r.cause, Some(Cause::WorkDeadline));
    assert!(!r.clone_attempted);
    assert_eq!(m.clone_count, 0);
    assert_eq!(m.fds.len(), 4); // Unknown inherited fd was never given an owner.
}

#[test]
fn scripted_transport_interoperability_export() {
    // Explicit opt-in retains new bounded fixture bytes. It never runs a host
    // process/collector or touches a real Linux FD. Default tests check in memory.
    let output =
        std::env::var_os("RADISHAXIOM_CHANNEL_SCRIPTED_EXPORT").map(std::path::PathBuf::from);
    if let Some(path) = &output {
        std::fs::create_dir(path).unwrap();
    }
    let mut manifest = Vec::new();
    for (name, complete, expected, final_code) in [
        ("complete", true, 0, Some(0)),
        ("eintr", true, 125, Some(125)),
        ("prefix", true, 125, Some(125)),
        ("missing-main", true, 125, Some(125)),
        ("half-chunk", false, 125, None),
        ("broken-final", false, 125, None),
        ("late-clock", true, 125, Some(0)),
    ] {
        let mut m = if name == "missing-main" {
            Model::new([Wait::Empty, Wait::Empty], &[b"", b"42 "])
        } else {
            success()
        };
        m.output[0] = b"synthetic-only\n".to_vec().into();
        match name {
            "eintr" => m.write_sizes = [1, errno(4)].into(),
            "prefix" => m.output[1] = vec![b'z'; STDERR_LIMIT + 1].into(),
            "half-chunk" => m.cut_chunk = true,
            "broken-final" => m.final_errno = Some(32),
            "late-clock" => m.final_time = Some(TOTAL_NS),
            _ => {}
        }
        let (code, _, m) = drive(m);
        assert_eq!(code, expected);
        let mut d = Decoder::new(binding());
        let decoded = d.feed(&m.wire).and_then(|_| d.finish());
        assert_eq!(decoded.is_ok(), complete);
        if let Ok(f) = decoded {
            assert_eq!(Some(f.selected_exit_code), final_code);
        }
        if let Some(path) = &output {
            use std::io::Write;
            std::fs::OpenOptions::new()
                .write(true)
                .create_new(true)
                .open(path.join(format!("{name}.bin")))
                .unwrap()
                .write_all(&m.wire)
                .unwrap();
        }
        manifest.push(format!("{{\"name\":\"{name}\",\"bytes\":{},\"digest\":\"sha256:{}\",\"complete_final\":{complete},\"scripted_selected_code\":{code},\"final_code\":{}}}",m.wire.len(),radishaxiom_digest::digest_hex(&m.wire),final_code.map_or("null".to_owned(),|c|c.to_string())));
        m.done();
    }
    if let Some(path) = output {
        use std::io::Write;
        let raw = format!(
            "{{\"scope\":\"scripted-kernel-only\",\"runtime_exit_confirmed\":false,\"cases\":[{}]}}",
            manifest.join(",")
        );
        std::fs::OpenOptions::new()
            .write(true)
            .create_new(true)
            .open(path.join("cases.json"))
            .unwrap()
            .write_all(raw.as_bytes())
            .unwrap();
    }
}

#[test]
fn external_stdin_is_never_read_and_need_not_be_a_pipe() {
    let mut m = success();
    m.fd_flags.insert(0, 2); // noninteractive read/write null role
    let (code, _, m) = drive(m);
    assert_eq!(code, 0);
    assert!(!m.calls.iter().any(|c| c.nr == NR_READ && c.args[0] == 0));
    assert!(!m.calls.iter().any(|c| c.nr == NR_FSTAT && c.args[0] == 0));
    assert_eq!(decode(&m).selected_exit_code, 0);
    m.done();
}

#[test]
fn output_poll_disconnect_stops_work_without_starving_exact_reaping() {
    let mut m = Model::new(
        [Wait::Running, Wait::Exit(exit(42, 2, 9)), Wait::Empty],
        &[b"", b"42 "],
    );
    m.poll_disconnect = true;
    let (code, r, m) = drive(m);
    assert_eq!(code, 125);
    assert!(r.no_children);
    assert_eq!(r.cause, Some(Cause::Transport));
    assert_eq!(m.kills, vec![42]);
    assert!(
        r.errors
            .iter()
            .any(|e| e.operation == "channel-output-poll-disconnect")
    );
    assert_eq!(m.calls.iter().filter(|c| c.nr == NR_PPOLL).count(), 1);
    assert!(m.now <= CLEANUP_NS);
    m.done();
}
