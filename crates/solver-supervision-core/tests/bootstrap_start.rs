use radishaxiom_solver_supervision_core::{bootstrap_start::*, wire::WireLimits};
fn limits() -> WireLimits {
    WireLimits {
        query_bytes: 32,
        stdout_bytes: 64,
        stderr_bytes: 16,
    }
}
fn fields() -> StartFields {
    StartFields {
        attempt: [1; 32],
        request: [2; 32],
        query_bytes: 3,
        query_digest: radishaxiom_digest::digest(b"abc"),
        policy_bundle: [3; 32],
        image: [4; 32],
        cli_acceptance: [5; 32],
        configuration: [6; 32],
    }
}
fn start() -> StartDescription {
    StartDescription::new(fields(), limits()).unwrap()
}
#[test]
fn exact_encoding_round_trip_and_wire_binding() {
    let expected = format!(
        concat!(
            "{{\"format\":\"solver-bootstrap-start-v0.1\",\"attempt\":\"{}\",",
            "\"request\":\"sha256:{}\",\"query_bytes\":3,",
            "\"query_digest\":\"sha256:ba7816bf8f01cfea414140de5dae2223b00361a396177a9cb410ff61f20015ad\",",
            "\"policy_bundle\":\"sha256:{}\",\"image\":\"sha256:{}\",",
            "\"cli_acceptance\":\"sha256:{}\",\"configuration\":\"sha256:{}\"}}"
        ),
        "01".repeat(32),
        "02".repeat(32),
        "03".repeat(32),
        "04".repeat(32),
        "05".repeat(32),
        "06".repeat(32)
    );
    assert_eq!(start().canonical_bytes(), expected.as_bytes());
    assert_eq!(
        StartDescription::parse(expected.as_bytes(), limits()).unwrap(),
        start()
    );
    let binding = start().binding([7; 32]);
    assert_eq!(binding.attempt, fields().attempt);
    assert_eq!(binding.request, fields().request);
    assert_eq!(binding.policy, fields().policy_bundle);
    assert_eq!(binding.image, fields().image);
    assert_eq!(binding.nonce, [7; 32]);
    assert_eq!(start().scope(), "external-declarations-only");
    assert_eq!(start().validate_query(b"abc"), Ok(()));
    assert!(matches!(
        start().validate_query(b"ab"),
        Err(StartError::QueryLength { .. })
    ));
    assert_eq!(start().validate_query(b"abd"), Err(StartError::QueryDigest));
}
#[test]
fn query_bounds_and_integer_grammar_are_closed() {
    for count in [1, 32] {
        let mut f = fields();
        f.query_bytes = count;
        assert!(StartDescription::new(f, limits()).is_ok());
    }
    for count in [0, 33, u32::MAX] {
        let mut f = fields();
        f.query_bytes = count;
        assert!(matches!(
            StartDescription::new(f, limits()),
            Err(StartError::QueryLength { .. })
        ));
    }
    let text = String::from_utf8(start().canonical_bytes()).unwrap();
    for value in [
        "0",
        "33",
        "4294967296",
        "03",
        "+3",
        "-3",
        "3.0",
        "3e0",
        "\"3\"",
        "",
    ] {
        let bad = text.replace("\"query_bytes\":3", &format!("\"query_bytes\":{value}"));
        assert!(
            StartDescription::parse(bad.as_bytes(), limits()).is_err(),
            "{value}"
        );
    }
}
#[test]
fn all_truncations_fixed_fields_and_noncanonical_forms_fail() {
    let bytes = start().canonical_bytes();
    for len in 0..bytes.len() {
        assert!(
            StartDescription::parse(&bytes[..len], limits()).is_err(),
            "{len}"
        );
    }
    let text = String::from_utf8(bytes).unwrap();
    let attempt = format!("\"attempt\":\"{}\"", "01".repeat(32));
    let request = format!("\"request\":\"sha256:{}\"", "02".repeat(32));
    let mutations = [
        text.replace("v0.1", "v0.2"),
        format!(" {text}"),
        format!("{text}\n"),
        format!("{text}{{}}"),
        text.replace("\"query_bytes\":3", "\"query_bytes\": 3"),
        text.replace(
            &format!("{attempt},{request}"),
            &format!("{request},{attempt}"),
        ),
        text.replace(&attempt, &format!("{attempt},{attempt}")),
        text.replace(&attempt, "\"unknown\":\"00\""),
        text.replace("\"format\"", "\"for\\u006dat\""),
        text.replace("\"configuration\"", "\"configuration_extra\""),
        text.replace("sha256:", "SHA256:"),
        text.replace("\"attempt\"", "\"request\""),
    ];
    for bad in mutations {
        assert!(
            StartDescription::parse(bad.as_bytes(), limits()).is_err(),
            "{bad}"
        );
    }
    // Every digest/attempt independently rejects uppercase/nonhex and wrong width.
    for key in [
        "attempt",
        "request",
        "query_digest",
        "policy_bundle",
        "image",
        "cli_acceptance",
        "configuration",
    ] {
        let marker = if key == "attempt" {
            format!("\"{key}\":\"")
        } else {
            format!("\"{key}\":\"sha256:")
        };
        let at = text.find(&marker).unwrap() + marker.len();
        for replacement in *b"Ag\\\" " {
            let mut bad = text.as_bytes().to_vec();
            bad[at] = replacement;
            assert!(StartDescription::parse(&bad, limits()).is_err(), "{key}");
        }
        let mut bad = text.as_bytes().to_vec();
        bad.remove(at);
        assert!(StartDescription::parse(&bad, limits()).is_err(), "{key}");
    }
}
#[test]
fn length_and_ascii_are_rejected_before_syntax_or_allocation() {
    assert_eq!(
        StartDescription::parse(&vec![0xff; 4097], limits()),
        Err(StartError::Length {
            actual: 4097,
            maximum: 4096
        })
    );
    assert!(matches!(
        StartDescription::parse(&vec![b' '; 4096], limits()),
        Err(StartError::Syntax { .. })
    ));
    let mut bom = vec![0xef, 0xbb, 0xbf];
    bom.extend(start().canonical_bytes());
    assert_eq!(
        StartDescription::parse(&bom, limits()),
        Err(StartError::NonAscii { offset: 0 })
    );
    for byte in [0, 0x7f, 0x80, 0xff] {
        let mut bad = start().canonical_bytes();
        bad[1] = byte;
        assert!(StartDescription::parse(&bad, limits()).is_err());
    }
}
