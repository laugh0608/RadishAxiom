use super::*;
use radishaxiom_digest::digest;
fn binding() -> Binding {
    Binding {
        run_id: [1; 32],
        input: [2; 32],
        collector: [3; 32],
    }
}
fn final_value() -> Final {
    let e = Exit {
        pid: 42,
        uid: 65532,
        code: 1,
        status: 0,
    };
    Final {
        binding: binding(),
        cause: None,
        child_pid: Some(42),
        main_exit: Some(e),
        exits: vec![e],
        signals: vec![],
        errors: vec![],
        clone_attempted: true,
        no_children: true,
        overflowed: false,
        stdout: Stream {
            seen: 3,
            exported: 3,
            digest: digest(b"abc"),
            prefix_only: false,
            eof: true,
        },
        stderr: Stream {
            seen: 0,
            exported: 0,
            digest: digest(b""),
            prefix_only: false,
            eof: true,
        },
        first_ns: 100,
        last_ns: 200,
        capture_failed: false,
        transport_failed: false,
        selected_exit_code: 0,
    }
}
fn wire(f: &Final) -> R<Vec<u8>> {
    let mut e = Encoder::new(binding());
    let mut out = e.start()?;
    out.extend(e.chunk(1, b"abc")?);
    out.extend(e.finish(f)?);
    Ok(out)
}
fn decode(raw: &[u8]) -> R<Final> {
    let mut d = Decoder::new(binding());
    d.feed(raw)?;
    d.finish()
}
#[test]
fn full_and_every_partition() {
    let f = final_value();
    let b = wire(&f).unwrap();
    for n in 0..=b.len() {
        let mut d = Decoder::new(binding());
        d.feed(&b[..n]).unwrap();
        d.feed(&b[n..]).unwrap();
        assert_eq!(d.finish().unwrap(), f)
    }
    let mut d = Decoder::new(binding());
    for byte in b {
        d.feed(&[byte]).unwrap()
    }
    assert_eq!(d.finish().unwrap(), f)
}
#[test]
fn every_truncation_and_trailing_byte() {
    let b = wire(&final_value()).unwrap();
    for n in 0..b.len() {
        assert!(decode(&b[..n]).is_err(), "prefix {n}")
    }
    let mut b = b;
    b.push(0);
    assert!(decode(&b).is_err())
}
#[test]
fn header_mutations_are_terminal() {
    let raw = wire(&final_value()).unwrap();
    for offset in [0, 8, 11, 12, 13, 14, 15, 16, 17, 18, 19] {
        let mut b = raw.clone();
        b[offset] ^= 128;
        let mut d = Decoder::new(binding());
        assert!(d.feed(&b).is_err(), "header {offset}");
        assert!(d.feed(&raw).is_err())
    }
}
#[test]
fn wrong_expected_binding_is_rejected() {
    let raw = wire(&final_value()).unwrap();
    for key in 0..3 {
        let mut b = binding();
        match key {
            0 => b.run_id[0] ^= 1,
            1 => b.input[0] ^= 1,
            _ => b.collector[0] ^= 1,
        }
        let mut d = Decoder::new(b);
        assert!(d.feed(&raw).is_err())
    }
}
#[test]
fn producer_rejects_order_duplicates_unknown_stream_and_after_final() {
    let mut e = Encoder::new(binding());
    assert!(e.chunk(1, b"x").is_err());
    assert!(e.start().is_err());
    let mut e = Encoder::new(binding());
    e.start().unwrap();
    assert!(e.start().is_err());
    for stream in [0, 3, 255] {
        let mut e = Encoder::new(binding());
        e.start().unwrap();
        assert!(e.chunk(stream, b"x").is_err())
    }
    let f = final_value();
    let mut e = Encoder::new(binding());
    e.start().unwrap();
    e.chunk(1, b"abc").unwrap();
    e.finish(&f).unwrap();
    assert!(e.chunk(1, b"x").is_err())
}
#[test]
fn chunks_and_stream_budget() {
    for size in [0, CHUNK_LIMIT + 1] {
        let mut e = Encoder::new(binding());
        e.start().unwrap();
        assert!(e.chunk(1, &vec![0; size]).is_err())
    }
    let mut e = Encoder::new(binding());
    e.start().unwrap();
    for _ in 0..STDERR_LIMIT / CHUNK_LIMIT {
        e.chunk(2, &[0; CHUNK_LIMIT]).unwrap();
    }
    assert!(e.chunk(2, b"x").is_err())
}
#[test]
fn frame_count_reserves_final() {
    let mut e = Encoder::new(binding());
    e.start().unwrap();
    for _ in 1..FRAME_LIMIT - 1 {
        e.chunk(1, b"x").unwrap();
    }
    assert!(e.chunk(1, b"x").is_err())
}
#[test]
fn final_hash_counts_and_main_must_match() {
    for change in 0..7 {
        let mut f = final_value();
        match change {
            0 => f.stdout.digest[0] ^= 1,
            1 => f.stdout.exported += 1,
            2 => f.stdout.seen += 1,
            3 => f.main_exit.as_mut().unwrap().pid += 1,
            4 => f.exits.clear(),
            5 => f.child_pid = None,
            _ => f.clone_attempted = false,
        }
        assert!(wire(&f).is_err(), "change {change}")
    }
}
#[test]
fn no_children_eof_and_prefix_are_independent() {
    for k in 0..5 {
        let mut f = final_value();
        match k {
            0 => f.no_children = false,
            1 => f.stdout.eof = false,
            2 => {
                f.stdout.prefix_only = true;
                f.stdout.seen += 1
            }
            3 => f.capture_failed = true,
            _ => f.transport_failed = true,
        }
        assert!(wire(&f).is_err());
        f.selected_exit_code = 125;
        let b = wire(&f).unwrap();
        assert_eq!(decode(&b).unwrap(), f)
    }
}
#[test]
fn cancellation_deadline_and_signal_preserve_main_status() {
    for cause in [
        Reason::Deadline,
        Reason::Cancelled(15),
        Reason::Signal(10),
        Reason::Orphan,
    ] {
        let mut f = final_value();
        f.cause = Some(cause);
        f.selected_exit_code = f.selected_code();
        let b = wire(&f).unwrap();
        let g = decode(&b).unwrap();
        assert_eq!(g.main_exit.unwrap().status, 0);
        assert_ne!(g.selected_exit_code, 0)
    }
}
#[test]
fn exit_signal_and_core_dump_are_not_normal_exit() {
    for code in [2, 3] {
        let mut f = final_value();
        f.main_exit.as_mut().unwrap().code = code;
        f.main_exit.as_mut().unwrap().status = 9;
        f.exits[0] = f.main_exit.unwrap();
        f.selected_exit_code = 137;
        assert_eq!(
            decode(&wire(&f).unwrap()).unwrap().main_exit.unwrap().code,
            code
        )
    }
}
#[test]
fn fault_and_observation_limits() {
    let fault = Fault {
        operation: "waitid-all".into(),
        kind: "errno".into(),
        detail: 4,
    };
    let mut f = final_value();
    f.cause = Some(Reason::Kernel(fault.clone()));
    f.errors = vec![fault; 64];
    f.selected_exit_code = 125;
    assert!(wire(&f).is_ok());
    f.errors.push(f.errors[0].clone());
    assert!(wire(&f).is_err());
    f.errors.truncate(64);
    f.errors[0].operation = "private/path".into();
    assert!(wire(&f).is_err())
}
#[test]
fn clock_overflow_rollback_and_wrong_boundaries() {
    for k in 0..3 {
        let mut f = final_value();
        match k {
            0 => f.first_ns = u64::MAX,
            1 => f.last_ns = f.first_ns - 1,
            _ => f.last_ns = f.first_ns + TOTAL_NS,
        }
        assert!(wire(&f).is_err())
    }
}
#[test]
fn canonical_json_rejects_duplicate_depth_escapes_bool_float_whitespace() {
    for b in [
        b"{\"a\":1,\"a\":2}".as_slice(),
        b"{\"a\": 1}",
        b"1.0",
        b"01",
        b"-1",
        b"\"\\n\"",
        b"null\n",
        b"NaN",
        b"true false",
    ] {
        assert!(parse(b).is_err(), "{b:?}")
    }
    let mut b = vec![b'['; 18];
    b.extend_from_slice(b"0");
    b.extend_from_slice(&[b']'; 18]);
    assert!(parse(&b).is_err());
    let mut f = final_value().json().unwrap();
    if let J::O(ref mut a) = f {
        a[15].1 = J::B(false)
    }
    assert!(Final::from(&f).is_err())
}
#[test]
fn unknown_final_field_and_clock_override_rejected() {
    let mut f = final_value().json().unwrap();
    if let J::O(ref mut a) = f {
        a.push(("accepted".into(), J::B(true)))
    }
    assert!(Final::from(&f).is_err());
    let mut f = final_value().json().unwrap();
    if let J::O(ref mut a) = f
        && let J::O(ref mut c) = a[12].1
    {
        c[1].1 = J::U(1)
    }
    assert!(Final::from(&f).is_err())
}
#[test]
fn body_validation_and_source_binding_never_accept_build() {
    use crate::{channel_inputs, channel_profile};
    let b = channel_inputs::export().unwrap();
    channel_inputs::check(&b).unwrap();
    assert!(channel_inputs::check(&[b.as_slice(), b"\n"].concat()).is_err());
    let j = parse(&b).unwrap();
    let J::O(v) = j else { panic!("object") };
    assert!(
        v.iter()
            .any(|(k, v)| k == "build_ready" && *v == J::B(false))
    );
    channel_profile::validate_collector(channel_profile::COLLECTOR).unwrap();
    for raw in [
        b"".as_slice(),
        b"x",
        b"x\r\n",
        b"\0\n",
        b"\xef\xbb\xbfhi\n",
        b"\xff\n",
    ] {
        assert!(channel_profile::validate_collector(raw).is_err())
    }
    assert!(channel_profile::validate_collector(&vec![b'\n'; 32769]).is_err())
}

#[test]
fn repeated_numeric_main_pid_cannot_hide_an_orphan() {
    let mut f = final_value();
    f.exits.push(f.exits[0]);
    assert!(wire(&f).is_err());
}

#[test]
fn invalid_typed_signals_return_error_without_overflow() {
    let mut f = final_value();
    f.cause = Some(Reason::Cancelled(255));
    assert!(wire(&f).is_err());
    let mut f = final_value();
    f.main_exit.as_mut().unwrap().code = 2;
    f.main_exit.as_mut().unwrap().status = 255;
    f.exits[0] = f.main_exit.unwrap();
    assert!(wire(&f).is_err());
}
