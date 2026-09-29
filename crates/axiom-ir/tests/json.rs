use radishaxiom_ir::json::{
    JsonErrorKind, JsonLimits, MAX_NESTING, ResourceLimit, canonicalize_json,
};

fn limits() -> JsonLimits {
    JsonLimits {
        max_input_bytes: 1024 * 1024,
        max_values: 100_000,
        max_nesting: MAX_NESTING,
    }
}

fn canonical(input: &str) -> String {
    String::from_utf8(canonicalize_json(input.as_bytes(), limits()).unwrap()).unwrap()
}

#[test]
fn independent_canonical_vectors() {
    // 人工推导的期望；不由被测编码器生成。数组顺序和字符串内容均不归一化。
    for (input, expected) in [
        (" \t\r\n true \n", "true"),
        (
            r#" { "z" : false, "a" : ["b", "a", {}, []] } "#,
            r#"{"a":["b","a",{},[]],"z":false}"#,
        ),
        (
            r#"["\u0000","\u0008","\u0009","\u000a","\u000c","\u000d","\u001f"]"#,
            r#"["\u0000","\b","\t","\n","\f","\r","\u001f"]"#,
        ),
        (
            r#"["\u0022","\u005C","\/","\u0041","\u00e9"]"#,
            r#"["\"","\\","/","A","é"]"#,
        ),
        (
            r#"["\uD800\uDC00","\uDBFF\uDFFF"]"#,
            "[\"\u{10000}\",\"\u{10ffff}\"]",
        ),
        (
            "[\"\u{7f}\",\"\u{85}\",\"\u{2028}\",\"\u{2029}\",\"\u{feff}\"]",
            "[\"\u{7f}\",\"\u{85}\",\"\u{2028}\",\"\u{2029}\",\"\u{feff}\"]",
        ),
        (
            r#"{"é":"NFC","e\u0301":"NFD","A":"upper","a":"lower","":"empty"}"#,
            "{\"\":\"empty\",\"A\":\"upper\",\"a\":\"lower\",\"e\u{301}\":\"NFD\",\"é\":\"NFC\"}",
        ),
    ] {
        assert_eq!(canonical(input), expected, "input: {input}");
        assert_eq!(canonical(expected), expected);
        assert!(expected.len() <= input.len());
    }
}

#[test]
fn utf16_order_differs_from_scalar_order_at_every_object_depth() {
    // U+10000 编码为 D800 DC00，必须排在 U+E000 前；Rust 默认字符串排序相反。
    let input = "{\"\u{e000}\":{\"\u{e000}\":true,\"\u{10000}\":false},\"\u{10000}\":[]}";
    let expected = "{\"\u{10000}\":[],\"\u{e000}\":{\"\u{10000}\":false,\"\u{e000}\":true}}";
    assert_eq!(canonical(input), expected);
    assert_eq!(
        canonical(r#"{"\uffff":true,"\ud83d\ude00":false,"\r":"control","1":"digit"}"#),
        "{\"\\r\":\"control\",\"1\":\"digit\",\"😀\":false,\"\u{ffff}\":true}"
    );
}

#[test]
fn rejects_duplicate_decoded_keys_with_second_key_offset() {
    for (input, offset) in [
        (r#"{"a":true,"\u0061":false}"#, 10),
        (r#"{"😀":[],"\uD83D\uDE00":{}}"#, 11),
        (r#"{"outer":{"":true,"":false}}"#, 18),
    ] {
        let error = canonicalize_json(input.as_bytes(), limits()).unwrap_err();
        assert_eq!(error.kind, JsonErrorKind::DuplicateKey, "{input}");
        assert_eq!(error.offset, offset, "{input}");
    }
    assert_eq!(
        canonical(r#"[{"a":true},{"a":false}]"#),
        r#"[{"a":true},{"a":false}]"#
    );
}

#[test]
fn rejects_invalid_grammar_and_forbidden_value_types() {
    for input in [
        "",
        " ",
        "[",
        "{",
        "[true,]",
        "{\"a\":true,}",
        "[,true]",
        "{a:true}",
        "{\"a\" true}",
        "{\"a\":}",
        "[true false]",
        "true false",
        "truex",
        "True",
        "FALSE",
        "//comment\ntrue",
        "/*x*/true",
        "\u{feff}{}",
        "[\u{a0}true]",
        "[\u{b}true]",
        "'text'",
        "\"raw\nnewline\"",
        "\"raw\0nul\"",
        "\"\\x41\"",
        "\"\\u00xz\"",
        "\"\\U0041\"",
        "\"\\é\"",
    ] {
        let error = canonicalize_json(input.as_bytes(), limits()).unwrap_err();
        assert!(
            !matches!(error.kind, JsonErrorKind::ResourceLimit(_)),
            "{input}"
        );
        assert!(error.offset <= input.len());
    }
    for input in [
        "0",
        "-0",
        "123",
        "1.25",
        "1e10",
        "null",
        "[null]",
        "{\"x\":0}",
    ] {
        assert_eq!(
            canonicalize_json(input.as_bytes(), limits())
                .unwrap_err()
                .kind,
            JsonErrorKind::NumberOrNull,
            "{input}"
        );
    }
    // 数学整数字符串此时只是字符串，不能静默转浮点数或提前执行 IR 层校验。
    let text = r#"["9007199254740993123456789","-0","01","1e3"]"#;
    assert_eq!(canonical(text), text);
}

#[test]
fn rejects_invalid_utf8_and_unpaired_surrogates() {
    for input in [
        b"\"\xc0\xaf\"".as_slice(),
        b"\"\xed\xa0\x80\"",
        b"\"\xf4\x90\x80\x80\"",
        b"\"\x80\"",
        b"\"\xe2\x82",
    ] {
        let error = canonicalize_json(input, limits()).unwrap_err();
        assert_eq!(error.kind, JsonErrorKind::InvalidUtf8);
        assert_eq!(error.offset, 1);
    }
    for input in [
        r#""\ud800""#,
        r#""\udfff""#,
        r#""\ud800x""#,
        r#""\ud800\u0041""#,
        r#""\ud800\ud800""#,
        r#"{"\udc00":true}"#,
    ] {
        assert_eq!(
            canonicalize_json(input.as_bytes(), limits())
                .unwrap_err()
                .kind,
            JsonErrorKind::UnpairedSurrogate,
            "{input}"
        );
    }
}

#[test]
fn rejects_all_truncated_prefixes_and_reports_original_byte_offsets() {
    for input in [r#"{"é":["\ud83d\ude00",true,false]}"#, r#""\u0022\\\/""#] {
        assert!(canonicalize_json(input.as_bytes(), limits()).is_ok());
        for end in 0..input.len() {
            assert!(
                canonicalize_json(&input.as_bytes()[..end], limits()).is_err(),
                "prefix {end}"
            );
        }
    }
    let error = canonicalize_json("[\"é\",?]".as_bytes(), limits()).unwrap_err();
    assert_eq!(error.kind, JsonErrorKind::UnexpectedToken);
    assert_eq!(error.offset, 6);
    let error = canonicalize_json(b"[true", limits()).unwrap_err();
    assert_eq!(error.kind, JsonErrorKind::UnexpectedEnd);
    assert_eq!(error.offset, 5);
}

#[test]
fn input_and_value_budgets_have_exact_boundaries() {
    let input = br#"{"a":[true,false]}"#;
    let exact = JsonLimits {
        max_input_bytes: input.len(),
        max_values: 5,
        ..limits()
    };
    assert_eq!(canonicalize_json(input, exact).unwrap(), input);
    let error = canonicalize_json(
        input,
        JsonLimits {
            max_input_bytes: input.len() - 1,
            ..exact
        },
    )
    .unwrap_err();
    assert_eq!(
        error.kind,
        JsonErrorKind::ResourceLimit(ResourceLimit::InputBytes)
    );
    assert_eq!(error.offset, input.len() - 1);
    let error = canonicalize_json(
        input,
        JsonLimits {
            max_values: 4,
            ..exact
        },
    )
    .unwrap_err();
    assert_eq!(
        error.kind,
        JsonErrorKind::ResourceLimit(ResourceLimit::Values)
    );
    assert_eq!(error.offset, 11);
    for input in [b"true".as_slice(), b"[]", b"{}", b"\"\""] {
        assert_eq!(
            canonicalize_json(
                input,
                JsonLimits {
                    max_values: 0,
                    ..limits()
                }
            )
            .unwrap_err()
            .kind,
            JsonErrorKind::ResourceLimit(ResourceLimit::Values)
        );
    }
}

#[test]
fn deep_and_wide_inputs_stop_at_resource_boundaries() {
    for depth in [1, 8, MAX_NESTING] {
        for (open, close) in [("[", "]"), ("{\"x\":", "}")] {
            let input = format!("{}true{}", open.repeat(depth), close.repeat(depth));
            assert_eq!(
                canonicalize_json(
                    input.as_bytes(),
                    JsonLimits {
                        max_nesting: depth,
                        ..limits()
                    }
                )
                .unwrap(),
                input.as_bytes()
            );
            let error = canonicalize_json(
                input.as_bytes(),
                JsonLimits {
                    max_nesting: depth - 1,
                    ..limits()
                },
            )
            .unwrap_err();
            assert_eq!(
                error.kind,
                JsonErrorKind::ResourceLimit(ResourceLimit::Nesting)
            );
        }
    }
    let input = "[".repeat(100_000);
    let error = canonicalize_json(
        input.as_bytes(),
        JsonLimits {
            max_nesting: usize::MAX,
            ..limits()
        },
    )
    .unwrap_err();
    assert_eq!(
        error.kind,
        JsonErrorKind::ResourceLimit(ResourceLimit::Nesting)
    );
    assert_eq!(error.offset, MAX_NESTING);
    let input = format!("[{}true]", "false,".repeat(20_000));
    assert_eq!(
        canonicalize_json(
            input.as_bytes(),
            JsonLimits {
                max_values: 100,
                ..limits()
            }
        )
        .unwrap_err()
        .kind,
        JsonErrorKind::ResourceLimit(ResourceLimit::Values)
    );
    assert_eq!(
        canonicalize_json(
            b"true",
            JsonLimits {
                max_nesting: 0,
                ..limits()
            }
        )
        .unwrap(),
        b"true"
    );
}

#[test]
fn every_unicode_scalar_decodes_from_json_escapes_without_normalization() {
    // 独立 Unicode 恒等关系，覆盖 BMP、所有代理对边界及非字符；不枚举非法 surrogate。
    for scalar in 0..=0x10ffff {
        let Some(ch) = char::from_u32(scalar) else {
            continue;
        };
        let escaped = if scalar <= 0xffff {
            format!("\"\\u{scalar:04x}\"")
        } else {
            let rest = scalar - 0x10000;
            format!(
                "\"\\u{:04x}\\u{:04x}\"",
                0xd800 + rest / 1024,
                0xdc00 + rest % 1024
            )
        };
        if scalar >= 32 && ch != '"' && ch != '\\' {
            assert_eq!(canonical(&escaped), format!("\"{ch}\""), "U+{scalar:04X}");
        }
    }
}

#[test]
fn existing_four_task_candidates_match_committed_canonical_bytes() {
    // 固定清单防止目录漏读变成空测试。correct / wrong 都只检查 JSON 层。
    let cases = [
        ("ax-b01", "correct"),
        ("ax-b01", "wrong-add"),
        ("ax-b01", "wrong-drop-zero"),
        ("ax-b02", "correct"),
        ("ax-b02", "wrong-constant-tier"),
        ("ax-b02", "wrong-region-join"),
        ("ax-b03", "correct"),
        ("ax-b03", "wrong-single-group"),
        ("ax-b03", "wrong-unit-sum"),
        ("ax-b04", "correct"),
        ("ax-b04", "wrong-sensitive-filter"),
        ("ax-b04", "wrong-sensitive-priority"),
    ];
    let root = std::path::Path::new(env!("CARGO_MANIFEST_DIR"))
        .join("../../benchmarks/keyed-finite-table-v0.1");
    for (task, candidate) in cases {
        let stem = root.join(task).join("candidates").join(candidate);
        let pretty = std::fs::read(stem.with_extension("ir.json")).unwrap();
        let expected = std::fs::read(stem.with_extension("ir.jcs")).unwrap();
        assert_eq!(
            canonicalize_json(&pretty, limits()).unwrap(),
            expected,
            "{task}/{candidate}"
        );
        assert_eq!(canonicalize_json(&expected, limits()).unwrap(), expected);
    }
}
