use radishaxiom_solver_diagnostic_host::transport::{
    CONTROL_DIAGNOSTIC_LIMIT, STDERR_LIMIT, STDOUT_LIMIT, SeparatedStreams, SimulatedEngineFrames,
    StreamKind, TransportError,
};

fn frame(kind: u8, payload: &[u8]) -> Vec<u8> {
    let mut result = vec![kind, 0, 0, 0];
    result.extend_from_slice(&(payload.len() as u32).to_be_bytes());
    result.extend_from_slice(payload);
    result
}

#[test]
fn all_frame_split_positions_and_bytewise_delivery_preserve_two_streams() {
    let mut bytes = frame(1, b"sat\n");
    bytes.extend(frame(2, b"warning\n"));
    bytes.extend(frame(1, b"(model)\n"));
    bytes.extend(frame(2, b""));
    for split in 0..=bytes.len() {
        let mut decoder = SimulatedEngineFrames::new();
        decoder.push(&bytes[..split]).unwrap();
        decoder.push(&bytes[split..]).unwrap();
        decoder.finish().unwrap();
        assert_eq!(
            decoder.streams().stream(StreamKind::Stdout).bytes(),
            b"sat\n(model)\n"
        );
        assert_eq!(
            decoder.streams().stream(StreamKind::Stderr).bytes(),
            b"warning\n"
        );
        assert!(decoder.streams().stream(StreamKind::Stdout).complete());
        assert!(decoder.streams().stream(StreamKind::Stderr).complete());
    }
    let mut decoder = SimulatedEngineFrames::new();
    for byte in bytes {
        decoder.push(&[byte]).unwrap();
    }
    decoder.finish().unwrap();
    assert_eq!(
        decoder.streams().stream(StreamKind::Stdout).bytes(),
        b"sat\n(model)\n"
    );
    assert_eq!(decoder.push(b"x"), Err(TransportError::DecoderStopped));
    assert_eq!(decoder.finish(), Err(TransportError::DecoderStopped));
}

#[test]
fn every_small_frame_partition_is_incremental() {
    // Every subset of boundaries, including splitting each of the eight header
    // bytes, validates invariance under all chunkings of this nonempty frame.
    let bytes = frame(1, b"ab");
    for boundaries in 0u16..(1 << (bytes.len() - 1)) {
        let mut decoder = SimulatedEngineFrames::new();
        let mut start = 0;
        for end in 1..bytes.len() {
            if boundaries & (1 << (end - 1)) != 0 {
                decoder.push(&bytes[start..end]).unwrap();
                start = end;
            }
        }
        decoder.push(&bytes[start..]).unwrap();
        decoder.finish().unwrap();
        assert_eq!(decoder.streams().stream(StreamKind::Stdout).bytes(), b"ab");
    }
}

#[test]
fn separated_cli_bytes_are_never_decoded_as_engine_frames() {
    let bytes = frame(1, b"ordinary solver data");
    let mut streams = SeparatedStreams::new();
    streams.push(StreamKind::Stdout, &bytes).unwrap();
    streams.eof(StreamKind::Stdout).unwrap();
    assert_eq!(streams.stream(StreamKind::Stdout).bytes(), bytes);
}

#[test]
fn frame_headers_reject_unknown_stream_reserved_bits_and_huge_lengths() {
    for stream in [0, 3, 255] {
        let mut decoder = SimulatedEngineFrames::new();
        assert_eq!(
            decoder.push(&frame(stream, b"")),
            Err(TransportError::UnknownStream(stream))
        );
        assert_eq!(decoder.push(b"x"), Err(TransportError::DecoderStopped));
    }
    for index in 1..4 {
        let mut bytes = frame(1, b"x");
        bytes[index] = 1;
        let mut decoder = SimulatedEngineFrames::new();
        assert_eq!(decoder.push(&bytes), Err(TransportError::ReservedHeader));
    }
    for (stream, kind) in [(1, StreamKind::Stdout), (2, StreamKind::Stderr)] {
        let mut bytes = vec![stream, 0, 0, 0];
        bytes.extend_from_slice(&u32::MAX.to_be_bytes());
        let mut decoder = SimulatedEngineFrames::new();
        assert_eq!(
            decoder.push(&bytes),
            Err(TransportError::FrameTooLarge {
                stream: kind,
                declared: u32::MAX
            })
        );
        assert!(decoder.streams().stream(kind).bytes().is_empty());
    }
}

#[test]
fn every_truncated_header_or_payload_is_incomplete() {
    let bytes = frame(1, b"abc");
    for end in 1..bytes.len() {
        let mut decoder = SimulatedEngineFrames::new();
        decoder.push(&bytes[..end]).unwrap();
        assert_eq!(
            decoder.finish(),
            Err(TransportError::TruncatedFrame),
            "prefix {end}"
        );
        assert!(!decoder.streams().stream(StreamKind::Stdout).complete());
    }
}

#[test]
fn both_streams_exact_limit_minus_one_and_first_extra_byte() {
    assert_eq!(CONTROL_DIAGNOSTIC_LIMIT, 65_536);
    for (kind, cap) in [
        (StreamKind::Stdout, STDOUT_LIMIT),
        (StreamKind::Stderr, STDERR_LIMIT),
    ] {
        for size in [cap - 1, cap] {
            let mut streams = SeparatedStreams::new();
            streams.push(kind, &vec![b'x'; size]).unwrap();
            streams.eof(kind).unwrap();
            assert!(streams.stream(kind).complete());
            assert!(!streams.stream(kind).exceeded());
            assert_eq!(streams.stream(kind).observed_bytes(), size as u64);
            assert_eq!(streams.push(kind, b""), Err(TransportError::Closed(kind)));
            assert_eq!(streams.eof(kind), Err(TransportError::Closed(kind)));
        }
        let mut streams = SeparatedStreams::new();
        streams.push(kind, &vec![b'a'; cap - 1]).unwrap();
        assert_eq!(
            streams.push(kind, b"bcdef"),
            Err(TransportError::StreamLimit(kind))
        );
        assert_eq!(streams.stream(kind).bytes().len(), cap);
        assert_eq!(streams.stream(kind).bytes()[cap - 1], b'b');
        assert_eq!(streams.stream(kind).observed_bytes(), cap as u64 + 1);
        assert!(streams.stream(kind).exceeded());
        assert!(!streams.stream(kind).complete());
        assert_eq!(
            streams.push(kind, &[b'z'; 100]),
            Err(TransportError::Closed(kind))
        );
        assert_eq!(streams.stream(kind).observed_bytes(), cap as u64 + 1);
    }
}

#[test]
fn interleaved_frames_exceed_total_limit_without_allocating_declared_length() {
    let mut decoder = SimulatedEngineFrames::new();
    decoder.push(&frame(2, &vec![b'a'; STDERR_LIMIT])).unwrap();
    decoder.push(&frame(1, b"sat\n")).unwrap();
    assert_eq!(
        decoder.push(&frame(2, b"z")),
        Err(TransportError::StreamLimit(StreamKind::Stderr))
    );
    assert_eq!(
        decoder.streams().stream(StreamKind::Stderr).bytes().len(),
        STDERR_LIMIT
    );
    assert_eq!(
        decoder
            .streams()
            .stream(StreamKind::Stderr)
            .observed_bytes(),
        STDERR_LIMIT as u64 + 1
    );
    assert_eq!(
        decoder.streams().stream(StreamKind::Stdout).bytes(),
        b"sat\n"
    );
    assert!(!decoder.streams().stream(StreamKind::Stdout).complete());
    assert_eq!(decoder.finish(), Err(TransportError::DecoderStopped));
}
