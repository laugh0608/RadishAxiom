use radishaxiom_solver_diagnostic_host::e3_wire::*;

fn binding() -> BootstrapBinding {
    BootstrapBinding {
        attempt: [1; 32],
        request: [2; 32],
        policy: [3; 32],
        image: [4; 32],
        nonce: [5; 32],
    }
}
fn frame(message: BootstrapMessage) -> BootstrapFrame {
    BootstrapFrame {
        binding: binding(),
        message,
    }
}
fn sample_messages() -> Vec<BootstrapMessage> {
    vec![
        BootstrapMessage::Ready(Ready {
            linux_ready_ns: 1,
            preparation_deadline_ns: 6_000_000_001,
            boot_digest: [6; 32],
            namespace_digest: [7; 32],
            configuration_digest: [8; 32],
        }),
        BootstrapMessage::StdoutChunk(vec![0, 255, 1, 0, 0, 0, 0, 0]),
        BootstrapMessage::StderrChunk(vec![255, 0, 128]),
        BootstrapMessage::StdoutEof,
        BootstrapMessage::StderrEof,
        BootstrapMessage::ChildExit(ChildExit::Exited(0)),
        BootstrapMessage::Final(Final {
            child_reaped: true,
            only_supervisor: true,
        }),
    ]
}
fn encode_all(messages: &[BootstrapMessage], direction: Direction) -> Vec<u8> {
    let mut encoder = BootstrapEncoder::new(direction);
    let mut bytes = Vec::new();
    for message in messages {
        bytes.extend(encoder.encode(&frame(message.clone())).unwrap());
    }
    bytes
}
fn decode_one(decoder: &mut BootstrapDecoder, bytes: &[u8]) -> BootstrapFrame {
    let step = decoder.poll(bytes).unwrap();
    assert_eq!(step.consumed, bytes.len());
    step.frame.unwrap()
}

#[test]
fn all_types_have_canonical_roundtrips_at_every_split() {
    let mut examples = sample_messages()
        .into_iter()
        .map(|m| (Direction::SupervisorToMac, m))
        .collect::<Vec<_>>();
    examples.extend([
        (
            Direction::MacToSupervisor,
            BootstrapMessage::Arm(Arm {
                deadline_ns: 999,
                query_len: 3,
                query_digest: [9; 32],
            }),
        ),
        (
            Direction::MacToSupervisor,
            BootstrapMessage::QueryChunk(vec![0, 255, 128]),
        ),
        (Direction::MacToSupervisor, BootstrapMessage::QueryEnd),
        (
            Direction::SupervisorToMac,
            BootstrapMessage::ChildExit(ChildExit::Signaled(64)),
        ),
    ]);
    for reason in [
        FailureReason::Protocol,
        FailureReason::Deadline,
        FailureReason::ControlLost,
        FailureReason::OutputLimit,
        FailureReason::Policy,
        FailureReason::Resource,
        FailureReason::Loader,
        FailureReason::Child,
        FailureReason::Observation,
    ] {
        examples.push((
            Direction::SupervisorToMac,
            BootstrapMessage::Failure(reason),
        ));
    }
    for (direction, message) in examples {
        let original = frame(message);
        let bytes = BootstrapEncoder::new(direction).encode(&original).unwrap();
        for split in 0..bytes.len() {
            let mut decoder = BootstrapDecoder::new(direction);
            let partial = decoder.poll(&bytes[..split]).unwrap();
            assert_eq!(partial.consumed, split);
            assert_eq!(partial.frame, None);
            assert!(decoder.buffered_bytes() <= BOOTSTRAP_HEADER_BYTES + BOOTSTRAP_PAYLOAD_LIMIT);
            assert_eq!(decode_one(&mut decoder, &bytes[split..]), original);
        }
    }
}

#[test]
fn concatenated_input_returns_only_one_frame_and_preserves_raw_stream_bytes() {
    let messages = sample_messages();
    let bytes = encode_all(&messages, Direction::SupervisorToMac);
    let mut decoder = BootstrapDecoder::new(Direction::SupervisorToMac);
    let mut offset = 0;
    let mut observed = Vec::new();
    while offset < bytes.len() {
        let step = decoder.poll(&bytes[offset..]).unwrap();
        assert!(step.consumed > 0);
        offset += step.consumed;
        observed.push(step.frame.unwrap().message);
        assert_eq!(decoder.buffered_bytes(), 0);
    }
    assert_eq!(observed, messages);
    assert_eq!(decoder.end_of_input(), Ok(()));
    assert_eq!(decoder.poll(&[]), Err(WireError::Stopped));
}

#[test]
fn one_byte_polls_and_final_byte_truncation_are_distinct() {
    let bytes = encode_all(
        &[BootstrapMessage::StdoutChunk(vec![0; 100])],
        Direction::SupervisorToMac,
    );
    let mut decoder = BootstrapDecoder::new(Direction::SupervisorToMac);
    for byte in &bytes[..bytes.len() - 1] {
        assert_eq!(decoder.poll(&[*byte]).unwrap().frame, None);
    }
    assert_eq!(decoder.end_of_input(), Err(WireError::Truncated));
    assert!(decoder.is_poisoned());
    assert_eq!(decoder.poll(&bytes), Err(WireError::Stopped));
}

#[test]
fn every_nonterminal_truncation_and_physical_eof_poison() {
    let bytes = encode_all(
        &[BootstrapMessage::QueryChunk(vec![1; 32])],
        Direction::MacToSupervisor,
    );
    for split in 0..bytes.len() {
        let mut decoder = BootstrapDecoder::new(Direction::MacToSupervisor);
        decoder.poll(&bytes[..split]).unwrap();
        assert_eq!(
            decoder.end_of_input(),
            Err(if split == 0 {
                WireError::ControlEof
            } else {
                WireError::Truncated
            })
        );
        assert!(decoder.is_poisoned());
    }
    let bytes = encode_all(&[BootstrapMessage::QueryEnd], Direction::MacToSupervisor);
    let mut decoder = BootstrapDecoder::new(Direction::MacToSupervisor);
    decode_one(&mut decoder, &bytes);
    assert_eq!(decoder.end_of_input(), Err(WireError::ControlEof));
}

#[test]
fn header_corruption_rejected_before_payload_allocation() {
    let original = encode_all(
        &[BootstrapMessage::StdoutChunk(vec![1; 16])],
        Direction::SupervisorToMac,
    );
    let corruptions = [
        (0, 0, WireError::Magic),
        (4, 1, WireError::Version),
        (5, 2, WireError::Version),
        (6, 1, WireError::Direction),
        (7, 255, WireError::UnknownKind(255)),
        (8, 1, WireError::Reserved),
    ];
    for (offset, value, expected) in corruptions {
        let mut bytes = original.clone();
        bytes[offset] = value;
        let mut decoder = BootstrapDecoder::new(Direction::SupervisorToMac);
        assert_eq!(decoder.poll(&bytes[..24]), Err(expected));
        assert!(decoder.is_poisoned());
        assert_eq!(decoder.buffered_bytes(), 24);
        assert_eq!(decoder.poll(&original), Err(WireError::Stopped));
    }
    for declared in [0u32, 159, 65_537, u32::MAX] {
        let mut bytes = original.clone();
        bytes[20..24].copy_from_slice(&declared.to_be_bytes());
        let mut decoder = BootstrapDecoder::new(Direction::SupervisorToMac);
        assert_eq!(decoder.poll(&bytes[..24]), Err(WireError::PayloadLength));
        assert_eq!(decoder.buffered_bytes(), 24);
    }
}

#[test]
fn sequence_gaps_replays_and_direction_mismatches_poison() {
    let original = encode_all(
        &[BootstrapMessage::StdoutChunk(vec![0])],
        Direction::SupervisorToMac,
    );
    for sequence in [1u64, u64::MAX] {
        let mut bytes = original.clone();
        bytes[12..20].copy_from_slice(&sequence.to_be_bytes());
        let mut decoder = BootstrapDecoder::new(Direction::SupervisorToMac);
        assert_eq!(
            decoder.poll(&bytes),
            Err(WireError::Sequence {
                expected: 0,
                actual: sequence
            })
        );
    }
    let mut decoder = BootstrapDecoder::new(Direction::SupervisorToMac);
    decode_one(&mut decoder, &original);
    assert_eq!(
        decoder.poll(&original),
        Err(WireError::Sequence {
            expected: 1,
            actual: 0
        })
    );
    let mut bytes = original;
    bytes[7] = 3;
    assert_eq!(
        BootstrapDecoder::new(Direction::SupervisorToMac).poll(&bytes),
        Err(WireError::Direction)
    );
}

#[test]
fn field_domains_and_exact_closed_payload_lengths_reject_extensions() {
    let examples = [
        (
            BootstrapMessage::Ready(Ready {
                linux_ready_ns: 9,
                preparation_deadline_ns: 9,
                boot_digest: [0; 32],
                namespace_digest: [0; 32],
                configuration_digest: [0; 32],
            }),
            WireError::NonCanonical,
        ),
        (
            BootstrapMessage::Arm(Arm {
                deadline_ns: 1,
                query_len: 1_048_577,
                query_digest: [0; 32],
            }),
            WireError::Limit("query"),
        ),
        (
            BootstrapMessage::ChildExit(ChildExit::Signaled(0)),
            WireError::NonCanonical,
        ),
        (
            BootstrapMessage::ChildExit(ChildExit::Signaled(65)),
            WireError::NonCanonical,
        ),
        (
            BootstrapMessage::Final(Final {
                child_reaped: false,
                only_supervisor: true,
            }),
            WireError::NonCanonical,
        ),
    ];
    for (message, expected) in examples {
        let direction = if matches!(message, BootstrapMessage::Arm(_)) {
            Direction::MacToSupervisor
        } else {
            Direction::SupervisorToMac
        };
        let mut encoder = BootstrapEncoder::new(direction);
        assert_eq!(encoder.encode(&frame(message)), Err(expected));
        assert!(encoder.is_poisoned());
    }
    for (message, body_offset, bad) in [
        (BootstrapMessage::ChildExit(ChildExit::Exited(0)), 0, 2),
        (
            BootstrapMessage::Final(Final {
                child_reaped: true,
                only_supervisor: true,
            }),
            1,
            0,
        ),
        (BootstrapMessage::Failure(FailureReason::Protocol), 0, 10),
    ] {
        let mut bytes = encode_all(&[message], Direction::SupervisorToMac);
        bytes[24 + 160 + body_offset] = bad;
        assert_eq!(
            BootstrapDecoder::new(Direction::SupervisorToMac).poll(&bytes),
            Err(WireError::NonCanonical)
        );
    }
    let mut bytes = encode_all(&[BootstrapMessage::QueryEnd], Direction::MacToSupervisor);
    bytes[20..24].copy_from_slice(&161u32.to_be_bytes());
    bytes.push(0);
    assert_eq!(
        BootstrapDecoder::new(Direction::MacToSupervisor).poll(&bytes),
        Err(WireError::PayloadLength)
    );
}

#[test]
fn duplicate_singletons_after_eof_and_after_terminal_fail_closed() {
    for message in [
        sample_messages()[0].clone(),
        BootstrapMessage::StdoutEof,
        BootstrapMessage::StderrEof,
        BootstrapMessage::ChildExit(ChildExit::Exited(0)),
    ] {
        let mut encoder = BootstrapEncoder::new(Direction::SupervisorToMac);
        let first = encoder.encode(&frame(message.clone())).unwrap();
        assert_eq!(encoder.encode(&frame(message)), Err(WireError::Duplicate));
        let mut second = first.clone();
        second[12..20].copy_from_slice(&1u64.to_be_bytes());
        let mut decoder = BootstrapDecoder::new(Direction::SupervisorToMac);
        decode_one(&mut decoder, &first);
        assert_eq!(decoder.poll(&second), Err(WireError::Duplicate));
    }
    for (direction, eof, chunk) in [
        (
            Direction::MacToSupervisor,
            BootstrapMessage::QueryEnd,
            BootstrapMessage::QueryChunk(vec![1]),
        ),
        (
            Direction::SupervisorToMac,
            BootstrapMessage::StdoutEof,
            BootstrapMessage::StdoutChunk(vec![1]),
        ),
        (
            Direction::SupervisorToMac,
            BootstrapMessage::StderrEof,
            BootstrapMessage::StderrChunk(vec![1]),
        ),
    ] {
        let mut encoder = BootstrapEncoder::new(direction);
        let first = encoder.encode(&frame(eof)).unwrap();
        assert_eq!(
            encoder.encode(&frame(chunk.clone())),
            Err(WireError::AfterEof)
        );
        let mut next = BootstrapEncoder::new(direction)
            .encode(&frame(chunk))
            .unwrap();
        next[12..20].copy_from_slice(&1u64.to_be_bytes());
        let mut decoder = BootstrapDecoder::new(direction);
        decode_one(&mut decoder, &first);
        assert_eq!(decoder.poll(&next), Err(WireError::AfterEof));
    }
    for terminal in [
        BootstrapMessage::Final(Final {
            child_reaped: true,
            only_supervisor: true,
        }),
        BootstrapMessage::Failure(FailureReason::Deadline),
    ] {
        let bytes = encode_all(&[terminal], Direction::SupervisorToMac);
        let mut decoder = BootstrapDecoder::new(Direction::SupervisorToMac);
        decode_one(&mut decoder, &bytes);
        assert_eq!(decoder.poll(&bytes), Err(WireError::AfterTerminal));
        assert!(decoder.is_poisoned());
    }
}

#[test]
fn frame_and_cumulative_data_n_and_n_plus_one_checked_before_copy() {
    for (direction, limit, make) in [
        (
            Direction::MacToSupervisor,
            BOOTSTRAP_QUERY_LIMIT,
            BootstrapMessage::QueryChunk as fn(Vec<u8>) -> BootstrapMessage,
        ),
        (
            Direction::SupervisorToMac,
            BOOTSTRAP_STDOUT_LIMIT,
            BootstrapMessage::StdoutChunk as fn(Vec<u8>) -> BootstrapMessage,
        ),
        (
            Direction::SupervisorToMac,
            BOOTSTRAP_STDERR_LIMIT,
            BootstrapMessage::StderrChunk as fn(Vec<u8>) -> BootstrapMessage,
        ),
    ] {
        let mut encoder = BootstrapEncoder::new(direction);
        let mut decoder = BootstrapDecoder::new(direction);
        let mut total = 0;
        while total < limit {
            let len = BOOTSTRAP_CHUNK_LIMIT.min(limit - total);
            let expected = frame(make(vec![0xff; len]));
            let bytes = encoder.encode(&expected).unwrap();
            assert_eq!(decode_one(&mut decoder, &bytes), expected);
            total += len;
        }
        let mut extra = BootstrapEncoder::new(direction)
            .encode(&frame(make(vec![1])))
            .unwrap();
        let frames = limit.div_ceil(BOOTSTRAP_CHUNK_LIMIT);
        extra[12..20].copy_from_slice(&(frames as u64).to_be_bytes());
        let name = match limit {
            BOOTSTRAP_QUERY_LIMIT => "query",
            BOOTSTRAP_STDOUT_LIMIT => "stdout",
            _ => "stderr",
        };
        assert_eq!(
            encoder.encode(&frame(make(vec![1]))),
            Err(WireError::Limit(name))
        );
        assert_eq!(decoder.poll(&extra[..24]), Err(WireError::Limit(name)));
        assert_eq!(decoder.buffered_bytes(), 24);
    }
    let mut encoder = BootstrapEncoder::new(Direction::SupervisorToMac);
    assert!(
        encoder
            .encode(&frame(BootstrapMessage::StdoutChunk(
                vec![0; BOOTSTRAP_CHUNK_LIMIT]
            )))
            .is_ok()
    );
    assert_eq!(
        encoder.encode(&frame(BootstrapMessage::StdoutChunk(vec![
            0;
            BOOTSTRAP_CHUNK_LIMIT
                + 1
        ]))),
        Err(WireError::PayloadLength)
    );
}

#[test]
fn tiny_chunks_exhaust_framing_budget_without_unbounded_output() {
    let mut encoder = BootstrapEncoder::new(Direction::SupervisorToMac);
    let mut decoder = BootstrapDecoder::new(Direction::SupervisorToMac);
    let each_control = BOOTSTRAP_HEADER_BYTES + BOOTSTRAP_BINDING_BYTES;
    let count = BOOTSTRAP_DIRECTION_CONTROL_LIMIT / each_control;
    for _ in 0..count {
        let bytes = encoder
            .encode(&frame(BootstrapMessage::StdoutChunk(vec![1])))
            .unwrap();
        decode_one(&mut decoder, &bytes);
    }
    assert_eq!(decoder.control_bytes(), count * each_control);
    assert_eq!(
        encoder.encode(&frame(BootstrapMessage::StdoutChunk(vec![1]))),
        Err(WireError::Limit("control"))
    );
    let mut extra = encode_all(
        &[BootstrapMessage::StdoutChunk(vec![1])],
        Direction::SupervisorToMac,
    );
    extra[12..20].copy_from_slice(&(count as u64).to_be_bytes());
    assert_eq!(decoder.poll(&extra[..24]), Err(WireError::Limit("control")));
}

#[test]
fn pending_one_frame_buffer_enforces_backpressure_and_partial_consumption() {
    let mut pending = PendingFrameBuffer::new(Direction::SupervisorToMac);
    let first = frame(BootstrapMessage::StdoutChunk(vec![
        255;
        BOOTSTRAP_CHUNK_LIMIT
    ]));
    pending.push(&first).unwrap();
    let expected = pending.remaining().to_vec();
    assert_eq!(
        expected.len(),
        BOOTSTRAP_HEADER_BYTES + BOOTSTRAP_PAYLOAD_LIMIT
    );
    assert!(expected.len() <= BOOTSTRAP_PENDING_LIMIT);
    assert_eq!(pending.push(&first), Err(WireError::Backpressure));
    assert!(!pending.is_poisoned());
    pending.consume(10).unwrap();
    assert_eq!(pending.remaining(), &expected[10..]);
    pending.consume(expected.len() - 10).unwrap();
    assert!(pending.remaining().is_empty());
    pending.push(&frame(BootstrapMessage::StdoutEof)).unwrap();
    assert_eq!(&pending.remaining()[12..20], &1u64.to_be_bytes());
    let mut pending = PendingFrameBuffer::new(Direction::SupervisorToMac);
    assert_eq!(
        pending.push(&frame(BootstrapMessage::StdoutChunk(
            vec![0; BOOTSTRAP_PENDING_LIMIT]
        ))),
        Err(WireError::Limit("pending"))
    );
    assert!(pending.remaining().is_empty());
    assert!(pending.is_poisoned());
    assert_eq!(pending.push(&first), Err(WireError::Stopped));
    assert_eq!(pending.consume(0), Err(WireError::Stopped));
}

#[test]
fn pending_accounting_and_encoding_errors_permanently_stop_writes() {
    let valid = frame(BootstrapMessage::StdoutChunk(vec![1; 20]));
    let mut pending = PendingFrameBuffer::new(Direction::SupervisorToMac);
    pending.push(&valid).unwrap();
    let len = pending.remaining().len();
    pending.consume(1).unwrap();
    assert_eq!(pending.consume(len), Err(WireError::ConsumeBeyondPending));
    assert!(pending.is_poisoned());
    assert!(pending.remaining().is_empty());
    assert_eq!(pending.consume(1), Err(WireError::Stopped));
    assert_eq!(pending.push(&valid), Err(WireError::Stopped));

    let mut pending = PendingFrameBuffer::new(Direction::SupervisorToMac);
    assert_eq!(
        pending.push(&frame(BootstrapMessage::StdoutChunk(vec![
            0;
            BOOTSTRAP_CHUNK_LIMIT
                + 1
        ]))),
        Err(WireError::PayloadLength)
    );
    assert!(pending.is_poisoned());
    assert_eq!(pending.push(&valid), Err(WireError::Stopped));
    assert_eq!(pending.consume(0), Err(WireError::Stopped));
}

#[test]
fn bound_decoder_matches_every_split_and_rejects_each_binding_field_before_body() {
    let original = frame(BootstrapMessage::StdoutChunk(vec![
        0xff;
        BOOTSTRAP_CHUNK_LIMIT
    ]));
    let bytes = BootstrapEncoder::new(Direction::SupervisorToMac)
        .encode(&original)
        .unwrap();
    for split in 0..=BOOTSTRAP_HEADER_BYTES + BOOTSTRAP_BINDING_BYTES {
        let mut decoder = BootstrapDecoder::new_bound(Direction::SupervisorToMac, binding());
        let first = decoder.poll(&bytes[..split]).unwrap();
        assert_eq!(first.consumed, split);
        assert_eq!(first.frame, None);
        assert_eq!(decode_one(&mut decoder, &bytes[split..]), original);
    }
    for field in 0..5 {
        let mut tampered = bytes.clone();
        tampered[BOOTSTRAP_HEADER_BYTES + field * 32] ^= 0xff;
        let mut decoder = BootstrapDecoder::new_bound(Direction::SupervisorToMac, binding());
        assert_eq!(decoder.poll(&tampered), Err(WireError::Binding));
        assert_eq!(
            decoder.buffered_bytes(),
            BOOTSTRAP_HEADER_BYTES + BOOTSTRAP_BINDING_BYTES
        );
        assert!(decoder.is_poisoned());
        assert_eq!(decoder.poll(&bytes), Err(WireError::Stopped));
        assert_eq!(decoder.end_of_input(), Err(WireError::Stopped));
        // Unbound fixture mode is deliberately only a syntax check.
        let decoded = decode_one(
            &mut BootstrapDecoder::new(Direction::SupervisorToMac),
            &tampered,
        );
        assert_ne!(decoded.binding, binding());
        assert_eq!(decoded.message, original.message);
    }
}

#[test]
fn bound_decoder_rejects_binding_switch_after_a_valid_frame() {
    let mut encoder = BootstrapEncoder::new(Direction::SupervisorToMac);
    let first = encoder
        .encode(&frame(BootstrapMessage::StdoutChunk(vec![1])))
        .unwrap();
    let mut changed = frame(BootstrapMessage::StderrChunk(vec![2]));
    changed.binding.nonce[31] ^= 1;
    let second = encoder.encode(&changed).unwrap();
    let mut decoder = BootstrapDecoder::new_bound(Direction::SupervisorToMac, binding());
    decode_one(&mut decoder, &first);
    assert_eq!(decoder.poll(&second), Err(WireError::Binding));
    assert!(decoder.is_poisoned());
    assert_eq!(decoder.poll(&first), Err(WireError::Stopped));
}
