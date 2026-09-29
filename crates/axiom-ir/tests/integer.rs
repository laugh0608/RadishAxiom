use radishaxiom_ir::integer::Integer;

#[test]
fn canonical_decimal_grammar_preserves_unbounded_text() {
    for text in [
        "0",
        "1",
        "-1",
        "99999999999999999999999999999999999999999999999999",
    ] {
        assert_eq!(Integer::parse(text).unwrap().as_str(), text);
    }
    for text in [
        "", "-", "+1", "-0", "00", "01", "-01", "--1", "1.0", "1e3", " 1", "1\n", "١", "１",
        "1_000",
    ] {
        assert!(Integer::parse(text).is_none(), "{text:?}");
    }
    let huge = "9".repeat(100_000);
    assert_eq!(Integer::parse(&huge).unwrap().as_str(), huge);
}

#[test]
fn order_matches_independent_machine_integer_oracle_in_small_range() {
    for left in -120i64..=120 {
        for right in -120i64..=120 {
            assert_eq!(
                Integer::parse(&left.to_string())
                    .unwrap()
                    .cmp(&Integer::parse(&right.to_string()).unwrap()),
                left.cmp(&right)
            );
        }
    }
}

#[test]
fn order_preserves_precision_beyond_machine_and_float_ranges() {
    // 人工排列，包含负数反序、跨位数、相邻大整数及浮点数不能区分的值。
    let ordered = [
        "-100000000000000000000000000000000000000000000000000000000000",
        "-99999999999999999999999999999999999999999999999999999999999",
        "-9007199254740993",
        "-9007199254740992",
        "-10",
        "-9",
        "-1",
        "0",
        "1",
        "9",
        "10",
        "9007199254740992",
        "9007199254740993",
        "99999999999999999999999999999999999999999999999999999999999",
        "100000000000000000000000000000000000000000000000000000000000",
    ];
    for pair in ordered.windows(2) {
        assert!(Integer::parse(pair[0]).unwrap() < Integer::parse(pair[1]).unwrap());
    }
}
